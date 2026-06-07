#!/usr/bin/env python3
"""
修复失败的 worldview 下载 — 使用替代URL和策略
"""
from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path("/Users/xuhongduo/Projects/deep-research/data/worldview")
LOG_DIR = Path("/Users/xuhongduo/Projects/deep-research/logs/worldview")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 失败的下载及其修复策略
RETRY_CONFIG = {
    "L0_003": {
        "name": "DBpedia本体",
        "output_dir": BASE_DIR / "L0_meta" / "dbpedia_ontology",
        "strategy": "wget_mirror",
        "urls": [
            "https://downloads.dbpedia.org/current/core-i18n/en/labels_en.ttl.bz2",
            "https://dbpedia.org/data/3.9/labels_en.ttl.bz2",
        ],
    },
    "L0_004": {
        "name": "WordNet词汇本体",
        "output_dir": BASE_DIR / "L0_meta" / "wordnet",
        "strategy": "wget_direct",
        "urls": [
            "https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz",
            "https://github.com/globalwordnet/english-wordnet/releases/download/2024-edition/english-wordnet-2024.xml.gz",
        ],
    },
    "L1_009": {
        "name": "CIA世界概况",
        "output_dir": BASE_DIR / "L1_facts" / "cia_factbook",
        "strategy": "wget_recursive",
        "urls": [
            "https://www.cia.gov/the-world-factbook/",
        ],
    },
    "L2_002": {
        "name": "DBpedia关系图谱",
        "output_dir": BASE_DIR / "L2_relations" / "dbpedia_relations",
        "strategy": "wget_mirror",
        "urls": [
            "https://downloads.dbpedia.org/current/core-i18n/en/mappingbased_objects_en.ttl.bz2",
        ],
    },
    "L2_006": {
        "name": "CommonCrawl网页链接图",
        "output_dir": BASE_DIR / "L2_relations" / "commoncrawl_links",
        "strategy": "wget_direct",
        "urls": [
            "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-08/wat.paths.gz",
            "https://data.commoncrawl.org/crawl-data/CC-MAIN-2024-51/wat.paths.gz",
        ],
    },
}


def wget_download(url: str, output_dir: Path, timeout: int = 300, extra_args: list[str] | None = None) -> bool:
    """使用 wget 下载，带重试"""
    output_dir.mkdir(parents=True, exist_ok=True)
    args = [
        "wget", url,
        "--timeout", str(timeout),
        "--tries", "3",
        "-c",  # 断点续传
        "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "-P", str(output_dir),
    ]
    if extra_args:
        args.extend(extra_args)

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {url}")
        return False
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return False


def wget_recursive(url: str, output_dir: Path, domains: list[str], timeout: int = 600) -> bool:
    """递归 wget 下载"""
    output_dir.mkdir(parents=True, exist_ok=True)
    args = [
        "wget", "--recursive", "--no-parent", "--no-clobber",
        "--convert-links", "--restrict-file-names=windows",
        "--domains", ",".join(domains),
        "--timeout", "60", "--tries", "3",
        "--user-agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "-P", str(output_dir),
        url,
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] {url}")
        return False


def download_with_strategy(kb_id: str, config: dict) -> dict:
    """使用指定策略下载"""
    print(f"\n[RETRY] {kb_id} {config['name']}")
    output_dir = config["output_dir"]
    strategy = config["strategy"]
    results = {"kb_id": kb_id, "success": False, "urls_tried": []}

    for url in config["urls"]:
        print(f"  尝试: {url}")
        if strategy == "wget_direct":
            success = wget_download(url, output_dir, timeout=300)
        elif strategy == "wget_mirror":
            success = wget_download(url, output_dir, timeout=600)
        elif strategy == "wget_recursive":
            success = wget_recursive(url, output_dir, domains=["cia.gov"], timeout=900)
        else:
            success = wget_download(url, output_dir)

        results["urls_tried"].append({"url": url, "success": success})
        if success:
            results["success"] = True
            # 检查实际文件大小
            total_size = sum(
                f.stat().st_size for f in output_dir.rglob("*") if f.is_file()
            )
            print(f"  [OK] 下载成功，目录大小: {total_size / 1024 / 1024:.1f} MB")
            break
        else:
            print(f"  [FAIL] 下载失败，等待 10s 后重试...")
            time.sleep(10)

    return results


def main():
    state_file = LOG_DIR / "retry_state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {}

    for kb_id, config in RETRY_CONFIG.items():
        if kb_id in state and state[kb_id].get("success"):
            print(f"[SKIP] {kb_id} 已成功")
            continue

        result = download_with_strategy(kb_id, config)
        state[kb_id] = result
        state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

        # 礼貌间隔
        time.sleep(5)

    print("\n[SUMMARY] 重试结果:")
    for kb_id, result in state.items():
        status = "OK" if result.get("success") else "FAIL"
        print(f"  {kb_id}: {status}")


if __name__ == "__main__":
    main()
