#!/usr/bin/env python3
"""
CommonCrawl WET 批量补充下载器
- 为 L7 多模态层 / L2 关系网络层 / L9 不确定性层 快速补充大规模网页文本语料
- 从 CommonCrawl S3 并行下载 WET 文件，支持断点续传
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/worldview")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/worldview")
LOG_DIR.mkdir(parents=True, exist_ok=True)

CC_BASE = "https://data.commoncrawl.org"

CRAWLS = [
    "CC-MAIN-2024-51",
    "CC-MAIN-2025-08",
    "CC-MAIN-2024-42",
    "CC-MAIN-2024-33",
    "CC-MAIN-2024-26",
    "CC-MAIN-2024-18",
    "CC-MAIN-2024-10",
    "CC-MAIN-2023-50",
]

OUTPUTS = {
    "L7": BASE_DIR / "L7_multimodal" / "cc_image_text",
    "L2": BASE_DIR / "L2_relations" / "commoncrawl_extra",
    "L9": BASE_DIR / "L9_uncertainty" / "commoncrawl_divergence",
    "L3": BASE_DIR / "L3_causal" / "cc_causal",
    "L4": BASE_DIR / "L4_normative" / "cc_regulations",
    "L6": BASE_DIR / "L6_procedural" / "cc_procedural",
    "L8": BASE_DIR / "L8_temporal" / "cc_temporal",
    "L5": BASE_DIR / "L5_cognitive" / "commoncrawl_cognitive",
}

def state_file(layer: str) -> Path:
    return LOG_DIR / f"commoncrawl_bulk_state_{layer}.json"


def load_state(layer: str, output_dir: Path | None = None) -> dict:
    path = state_file(layer)
    state: dict = {"completed": [], "failed": []}
    if path.exists():
        try:
            state = json.loads(path.read_text())
        except Exception:
            pass
    # Seed completed list from files already present on disk
    if output_dir is not None and output_dir.exists():
        existing = [f.name for f in output_dir.iterdir() if f.is_file() and f.stat().st_size > 1000 and f.name not in state["completed"]]
        if existing:
            state["completed"].extend(existing)
            save_state(layer, state)
    return state


def save_state(layer: str, state: dict):
    state_file(layer).write_text(json.dumps(state, indent=2, ensure_ascii=False))


def fetch_paths(crawl: str, max_paths: int = 0) -> list[str]:
    url = f"{CC_BASE}/crawl-data/{crawl}/wet.paths.gz"
    print(f"[CC] 获取路径列表: {crawl}")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = gzip.decompress(resp.read())
            paths = [line.strip().decode("utf-8") for line in data.splitlines() if line.strip()]
            if max_paths > 0:
                paths = paths[:max_paths]
            print(f"[CC] {crawl} 共 {len(paths)} 个 WET 文件")
            return paths
        except Exception as e:
            wait = 5 * (2 ** attempt)
            print(f"  [WARN] 获取失败: {e}, {wait}s 后重试...")
            time.sleep(wait)
    return []


def download_wet(path: str, output_dir: Path, layer: str, state: dict) -> tuple[str, bool, int]:
    filename = path.split("/")[-1]
    output_path = output_dir / filename
    if filename in state["completed"]:
        return filename, True, output_path.stat().st_size if output_path.exists() else 0

    url = f"{CC_BASE}/{path}"
    for attempt in range(3):
        cmd = [
            "curl", "-L", "-C", "-", "-o", str(output_path),
            "--max-time", "300", "-s", url,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=320)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
                if filename not in state["completed"]:
                    state["completed"].append(filename)
                    save_state(layer, state)
                return filename, True, output_path.stat().st_size
        except Exception:
            pass
        time.sleep(2 ** attempt)

    if filename not in state["failed"]:
        state["failed"].append(filename)
        save_state(layer, state)
    return filename, False, 0


def main():
    parser = argparse.ArgumentParser(description="CommonCrawl WET 批量补充下载")
    parser.add_argument("--layer", default="L7", choices=["L7", "L2", "L9", "L3", "L4", "L6", "L8", "L5"], help="目标层")
    parser.add_argument("--crawls", nargs="+", default=None, help="指定 crawl 名称")
    parser.add_argument("--max-files", type=int, default=500, help="每个 crawl 最多下载文件数")
    parser.add_argument("--workers", type=int, default=6, help="并行下载 workers")
    parser.add_argument("--limit-total", type=int, default=0, help="总计最多下载文件数")
    args = parser.parse_args()

    output_dir = OUTPUTS[args.layer]
    output_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(args.layer, output_dir)

    crawls = args.crawls or CRAWLS
    all_paths: list[tuple[str, str]] = []
    for crawl in crawls:
        paths = fetch_paths(crawl, max_paths=args.max_files)
        for p in paths:
            all_paths.append((crawl, p))
        time.sleep(1)

    random.shuffle(all_paths)
    if args.limit_total > 0:
        all_paths = all_paths[:args.limit_total]

    total = len(all_paths)
    print(f"[START] 目标层 {args.layer}, 输出 {output_dir}, 共 {total} 个文件, workers={args.workers}")

    completed = 0
    failed = 0
    total_bytes = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_wet, p, output_dir, args.layer, state): (crawl, p) for crawl, p in all_paths}
        for future in as_completed(futures):
            filename, ok, size = future.result()
            if ok:
                completed += 1
                total_bytes += size
            else:
                failed += 1
            if (completed + failed) % 20 == 0:
                gb = total_bytes / 1024 / 1024 / 1024
                print(f"[PROGRESS] {completed + failed}/{total} | 成功:{completed} 失败:{failed} | {gb:.2f}GB")

    gb = total_bytes / 1024 / 1024 / 1024
    print(f"\n[SUMMARY] 层:{args.layer} | 成功:{completed} | 失败:{failed} | 总量:{gb:.2f}GB")


if __name__ == "__main__":
    main()
