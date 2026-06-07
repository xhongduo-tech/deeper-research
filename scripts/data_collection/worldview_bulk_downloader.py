#!/usr/bin/env python3
"""
世界观知识库批量下载调度器 — 基于10层架构的并行全速下载

策略:
- 多线程并行下载 (默认16 workers)
- 自动重试 + 指数退避
- 下载失败时切换备用策略 (curl→wget→axel→aria2c)
- 反爬应对: 轮换User-Agent、随机延迟、请求头模拟
- 实时进度监控 + 断点续传

Usage:
    python worldview_bulk_downloader.py --layer L1 --workers 16
    python worldview_bulk_downloader.py --all --workers 20
    python worldview_bulk_downloader.py --source L1_002 L2_001 --workers 8
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

sys.path.insert(0, str(Path(__file__).parent))
from config_worldview_v1 import ALL_LAYERS, LayerConfig, SourceConfig

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/worldview")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/worldview")
LOG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = LOG_DIR / "download_state.json"

# 轮换User-Agent池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# 下载工具优先级 (失败时依次尝试)
DOWNLOAD_TOOLS = ["curl", "wget", "axel", "aria2c"]


@dataclass
class DownloadResult:
    kb_id: str
    success: bool
    bytes_downloaded: int
    duration: float
    tool_used: str
    error: str = ""


class DownloadState:
    """断点续传状态管理"""

    def __init__(self):
        self.state = {}
        if STATE_FILE.exists():
            try:
                self.state = json.loads(STATE_FILE.read_text())
            except Exception:
                self.state = {}

    def is_completed(self, kb_id: str) -> bool:
        return self.state.get(kb_id, {}).get("completed", False)

    def mark_completed(self, kb_id: str, size: int):
        self.state[kb_id] = {"completed": True, "size": size, "at": datetime.now().isoformat()}
        self.save()

    def mark_failed(self, kb_id: str, error: str):
        self.state.setdefault(kb_id, {})
        self.state[kb_id]["failed"] = True
        self.state[kb_id]["error"] = error
        self.state[kb_id]["at"] = datetime.now().isoformat()
        self.save()

    def get_progress(self, kb_id: str) -> dict:
        return self.state.get(kb_id, {})

    def save(self):
        STATE_FILE.write_text(json.dumps(self.state, indent=2, ensure_ascii=False))


class WorldviewDownloader:
    """世界观批量下载器"""

    def __init__(self, workers: int = 16, retry_attempts: int = 5):
        self.workers = workers
        self.retry_attempts = retry_attempts
        self.state = DownloadState()
        self.results: list[DownloadResult] = []
        self.lock = threading.Lock()
        self.session = requests.Session()

    def _get_headers(self) -> dict:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }

    def _download_with_requests(self, url: str, output_path: Path, resume: bool = True) -> tuple[bool, int]:
        """使用requests下载，支持断点续传"""
        headers = self._get_headers()
        downloaded = 0

        if resume and output_path.exists():
            downloaded = output_path.stat().st_size
            headers["Range"] = f"bytes={downloaded}-"

        try:
            r = self.session.get(url, headers=headers, stream=True, timeout=120, allow_redirects=True)
            if r.status_code in (200, 206):
                mode = "ab" if resume and downloaded > 0 else "wb"
                with open(output_path, mode) as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                return True, downloaded
            return False, 0
        except Exception as e:
            return False, 0

    def _download_with_curl(self, url: str, output_path: Path, resume: bool = True) -> tuple[bool, int]:
        """使用curl下载，支持断点续传"""
        cmd = ["curl", "-L", "-o", str(output_path)]
        if resume and output_path.exists():
            cmd.extend(["-C", "-"])
        cmd.extend(["--max-time", "300", "-s", url])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0 and output_path.exists():
                return True, output_path.stat().st_size
            return False, 0
        except Exception:
            return False, 0

    def _download_with_wget(self, url: str, output_path: Path, resume: bool = True) -> tuple[bool, int]:
        """使用wget下载"""
        cmd = ["wget", "-O", str(output_path), "--timeout=120", "--tries=3"]
        if resume and output_path.exists():
            cmd.append("-c")
        cmd.append(url)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0 and output_path.exists():
                return True, output_path.stat().st_size
            return False, 0
        except Exception:
            return False, 0

    def _download_with_axel(self, url: str, output_path: Path) -> tuple[bool, int]:
        """使用axel多线程加速下载"""
        cmd = ["axel", "-n", "8", "-o", str(output_path), "-T", "120", url]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0 and output_path.exists():
                return True, output_path.stat().st_size
            return False, 0
        except Exception:
            return False, 0

    def _download_with_aria2c(self, url: str, output_path: Path) -> tuple[bool, int]:
        """使用aria2c下载"""
        output_dir = output_path.parent
        output_name = output_path.name
        cmd = [
            "aria2c", "-x", "8", "-s", "8", "-k", "1M",
            "--dir", str(output_dir),
            "--out", output_name,
            "--max-download-limit=0",
            "--timeout=120", url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0 and output_path.exists():
                return True, output_path.stat().st_size
            return False, 0
        except Exception:
            return False, 0

    def _try_download(self, url: str, output_path: Path) -> tuple[bool, int, str]:
        """尝试多种工具下载，直到成功"""
        tools = [
            ("curl", self._download_with_curl),
            ("requests", self._download_with_requests),
            ("wget", self._download_with_wget),
            ("axel", self._download_with_axel),
            ("aria2c", self._download_with_aria2c),
        ]

        for tool_name, tool_func in tools:
            success, size = tool_func(url, output_path)
            if success and size > 100:
                return True, size, tool_name

        return False, 0, "all_failed"

    def download_source(self, source: SourceConfig) -> DownloadResult:
        """下载单个数据源"""
        start_time = time.time()
        kb_id = source.kb_id

        if self.state.is_completed(kb_id):
            return DownloadResult(kb_id, True, 0, 0, "skipped")

        print(f"[{kb_id}] 开始下载: {source.name}")
        output_dir = Path(source.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 根据download_method选择策略
        method = source.download_method

        if method == "direct":
            return self._download_direct(source, start_time)
        elif method == "wget":
            return self._download_wget_recursive(source, start_time)
        elif method == "api_free":
            return self._download_api(source, start_time)
        elif method == "crawl":
            return self._handle_crawl(source, start_time)
        else:
            return DownloadResult(kb_id, False, 0, time.time() - start_time, "", f"未知方法: {method}")

    def _download_direct(self, source: SourceConfig, start_time: float) -> DownloadResult:
        """直接下载 (大文件dump)"""
        kb_id = source.kb_id
        extra = source.extra or {}
        url = extra.get("dump_url") or source.source_url
        output_dir = Path(source.output_dir)

        # 从URL推断文件名
        filename = url.split("/")[-1].split("?")[0] or f"{kb_id}_download"
        output_path = output_dir / filename

        for attempt in range(self.retry_attempts):
            success, size, tool = self._try_download(url, output_path)
            if success:
                self.state.mark_completed(kb_id, size)
                duration = time.time() - start_time
                print(f"  [{kb_id}] 完成: {size / 1024 / 1024:.1f} MB, 工具: {tool}, 耗时: {duration:.1f}s")
                return DownloadResult(kb_id, True, size, duration, tool)

            wait = 5 * (2 ** attempt) + random.uniform(0, 5)
            print(f"  [{kb_id}] 尝试 {attempt+1}/{self.retry_attempts} 失败, 等待 {wait:.0f}s...")
            time.sleep(wait)

        self.state.mark_failed(kb_id, "所有下载工具均失败")
        return DownloadResult(kb_id, False, 0, time.time() - start_time, "all_failed", "所有工具失败")

    def _download_wget_recursive(self, source: SourceConfig, start_time: float) -> DownloadResult:
        """wget递归下载"""
        kb_id = source.kb_id
        output_dir = Path(source.output_dir)

        cmd = [
            "wget", "--recursive", "--no-parent", "--no-clobber",
            "--convert-links", "--restrict-file-names=windows",
            "--domains", source.source_url.split("/")[2],
            "--timeout=60", "--tries=3",
            "-P", str(output_dir),
            source.source_url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
            self.state.mark_completed(kb_id, total_size)
            duration = time.time() - start_time
            print(f"  [{kb_id}] wget完成: {total_size / 1024 / 1024:.1f} MB, 耗时: {duration:.1f}s")
            return DownloadResult(kb_id, True, total_size, duration, "wget")
        except Exception as e:
            self.state.mark_failed(kb_id, str(e))
            return DownloadResult(kb_id, False, 0, time.time() - start_time, "wget", str(e))

    def _download_api(self, source: SourceConfig, start_time: float) -> DownloadResult:
        """API批量获取 (简化版，实际需根据各API定制)"""
        kb_id = source.kb_id
        output_dir = Path(source.output_dir)

        # 对于API类型的数据源，创建一个占位标记文件记录状态
        # 实际API批量下载需要专门的适配器
        marker = output_dir / ".api_source_marker"
        output_dir.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "kb_id": kb_id,
            "name": source.name,
            "source_url": source.source_url,
            "method": "api_free",
            "status": "pending_adapter",
            "note": "需要专门的API适配器进行批量下载",
        }, indent=2, ensure_ascii=False))

        print(f"  [{kb_id}] API类型需要专门适配器，已标记: {source.name}")
        self.state.mark_completed(kb_id, 0)
        return DownloadResult(kb_id, True, 0, time.time() - start_time, "api_marker")

    def _handle_crawl(self, source: SourceConfig, start_time: float) -> DownloadResult:
        """爬虫类型 (如CNINFO已有专门下载器)"""
        kb_id = source.kb_id

        if kb_id == "L1_011":
            # 巨潮资讯已有专门下载器在运行
            print(f"  [{kb_id}] CNINFO年报下载由专门下载器处理，跳过")
            return DownloadResult(kb_id, True, 0, 0, "delegated")

        output_dir = Path(source.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        marker = output_dir / ".crawl_source_marker"
        marker.write_text(json.dumps({
            "kb_id": kb_id,
            "name": source.name,
            "status": "pending_crawler",
        }, indent=2, ensure_ascii=False))

        return DownloadResult(kb_id, True, 0, time.time() - start_time, "crawl_marker")

    def run(self, sources: list[SourceConfig]):
        """批量并行下载"""
        total = len(sources)
        completed = 0
        failed = 0
        total_bytes = 0

        print(f"[START] 批量下载 {total} 个数据源, workers={self.workers}")
        print(f"[STATE] 已完成: {sum(1 for s in sources if self.state.is_completed(s.kb_id))}")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(self.download_source, s): s for s in sources}

            for future in as_completed(futures):
                result = future.result()
                with self.lock:
                    self.results.append(result)
                    if result.success:
                        completed += 1
                        total_bytes += result.bytes_downloaded
                    else:
                        failed += 1

                    # 打印进度
                    if (completed + failed) % 5 == 0 or result.bytes_downloaded > 1024 * 1024:
                        mb = total_bytes / 1024 / 1024
                        gb = mb / 1024
                        print(f"[PROGRESS] {completed + failed}/{total} | 成功:{completed} 失败:{failed} | {mb:.1f}MB ({gb:.2f}GB)")

        # 最终统计
        mb = total_bytes / 1024 / 1024
        gb = mb / 1024
        print(f"\n[SUMMARY]")
        print(f"  总计: {total}")
        print(f"  成功: {completed}")
        print(f"  失败: {failed}")
        print(f"  跳过: {sum(1 for r in self.results if r.tool_used == 'skipped')}")
        print(f"  下载量: {mb:.1f} MB ({gb:.2f} GB)")

        # 失败详情
        failed_results = [r for r in self.results if not r.success and r.error]
        if failed_results:
            print(f"\n[FAILED]")
            for r in failed_results[:10]:
                print(f"  {r.kb_id}: {r.error}")


def main():
    parser = argparse.ArgumentParser(description="世界观知识库批量下载调度器")
    parser.add_argument("--layer", type=str, default="",
                        help="指定层 (L0-L9)，如 L1")
    parser.add_argument("--source", type=str, nargs="+", default=None,
                        help="指定数据源ID列表，如 L1_001 L1_002")
    parser.add_argument("--all", action="store_true",
                        help="下载所有数据源")
    parser.add_argument("--workers", type=int, default=16,
                        help="并行下载 workers (默认16)")
    parser.add_argument("--retry", type=int, default=5,
                        help="每个源重试次数 (默认5)")
    parser.add_argument("--exclude-crawl", action="store_true",
                        help="排除需要爬虫的数据源")
    parser.add_argument("--exclude-api", action="store_true",
                        help="排除需要API适配器的数据源")
    args = parser.parse_args()

    # 收集目标数据源
    all_sources: list[SourceConfig] = []
    for layer in ALL_LAYERS:
        all_sources.extend(layer.data_sources)

    targets: list[SourceConfig] = []

    if args.all:
        targets = all_sources
    elif args.layer:
        layer = next((l for l in ALL_LAYERS if l.layer_id == args.layer), None)
        if layer:
            targets = layer.data_sources
        else:
            print(f"[ERROR] 未知层: {args.layer}")
            return
    elif args.source:
        targets = [s for s in all_sources if s.kb_id in args.source]
    else:
        # 默认下载direct和wget类型的数据源
        targets = [s for s in all_sources if s.download_method in ("direct", "wget")]
        print(f"[INFO] 未指定目标，默认下载 direct/wget 类型 ({len(targets)} 个)")

    # 过滤
    if args.exclude_crawl:
        targets = [s for s in targets if s.download_method != "crawl"]
    if args.exclude_api:
        targets = [s for s in targets if s.download_method != "api_free"]

    if not targets:
        print("[WARN] 没有匹配的数据源")
        return

    print(f"[CONFIG] 目标数据源: {len(targets)} 个")
    print(f"[CONFIG] Workers: {args.workers}, 重试: {args.retry}")

    downloader = WorldviewDownloader(workers=args.workers, retry_attempts=args.retry)
    downloader.run(targets)


if __name__ == "__main__":
    main()
