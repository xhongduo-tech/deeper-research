#!/usr/bin/env python3
"""
data_collection/run.py — Unified CLI entry point for DataAgent corpus download.

Usage:
    python run.py crawl --target all [--priority N] [--workers N] [--since YEAR]
    python run.py crawl --target kb_001,kb_002 [--workers N]
    python run.py rss --daemon
    python run.py status
    python run.py setup

Mirrors the CLI expected by ../download.sh.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure config_v2 is importable from this directory
sys.path.insert(0, str(Path(__file__).parent))

from master_scheduler_v2 import run_all, show_status


def _setup_logging(verbose: bool = False):
    log_dir = Path("./data/download_progress")
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)]
    try:
        handlers.append(logging.FileHandler(str(log_dir / "run.log"), encoding="utf-8"))
    except Exception:
        pass
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=handlers,
    )


def _priority_to_categories(priority: int) -> list[str] | None:
    """Map priority level (0-5) to source categories."""
    mapping = {
        0: ["policy", "statistics", "finance", "law"],      # 政府/法律/统计
        1: ["law", "finance"],                               # 法律核心/金融
        2: ["finance", "trade"],                             # 金融企业
        3: ["policy", "trade", "intl", "tech", "news"],     # 政策/国际/行业
        4: ["agri", "realestate", "logistics", "energy"],  # 补充维度
        5: ["news"],                                          # RSS 实时
    }
    # Collect all categories up to and including priority level
    categories = set()
    for p in range(0, min(priority, 5) + 1):
        categories.update(mapping.get(p, []))
    return list(categories) if categories else None


def cmd_crawl(args):
    _setup_logging(args.verbose)
    categories = None
    kb_ids = None
    workers = args.workers or 8
    since = args.since or 2023

    if args.target != "all":
        # Could be comma-separated kb_ids
        if "," in args.target or args.target.startswith("kb_"):
            kb_ids = args.target.split(",")
        else:
            categories = [args.target]

    if args.priority is not None:
        categories = _priority_to_categories(args.priority)
        logging.getLogger("run").info("Priority %d → categories: %s", args.priority, categories)

    # Filter by time range (since year) - passed to scheduler
    logging.getLogger("run").info(
        "Starting crawl: workers=%d, since=%d, target=%s",
        workers, since, args.target,
    )

    run_all(
        filter_category=categories[0] if categories and len(categories) == 1 else None,
        filter_kb_ids=kb_ids,
        skip_completed=not args.no_skip,
        workers=workers,
        since_year=since,
    )


def cmd_rss(args):
    _setup_logging(args.verbose)
    from download_rss import run_rss_daemon
    if args.daemon:
        run_rss_daemon()
    else:
        # One-shot RSS fetch
        from download_rss import RSSDownloader
        dl = RSSDownloader(None)
        dl.run()


def cmd_status(args):
    show_status()


def main():
    parser = argparse.ArgumentParser(description="DataAgent 语料下载编排")
    sub = parser.add_subparsers(dest="command", required=True)

    # crawl
    crawl_p = sub.add_parser("crawl", help="下载语料")
    crawl_p.add_argument("--target", default="all", help="all | 逗号分隔的kb_id | category名")
    crawl_p.add_argument("--priority", type=int, default=None, help="优先级 0-5")
    crawl_p.add_argument("--workers", type=int, default=8, help="并发下载数 (默认8)")
    crawl_p.add_argument("--since", type=int, default=2023, help="只下载该年份之后的数据 (默认2023)")
    crawl_p.add_argument("--no-skip", action="store_true", help="不跳过已完成的KB")
    crawl_p.add_argument("--verbose", action="store_true", help="详细日志")

    # rss
    rss_p = sub.add_parser("rss", help="RSS 增量下载")
    rss_p.add_argument("--daemon", action="store_true", help="守护进程模式")
    rss_p.add_argument("--verbose", action="store_true")

    # status
    status_p = sub.add_parser("status", help="查看下载进度")

    args = parser.parse_args()

    if args.command == "crawl":
        cmd_crawl(args)
    elif args.command == "rss":
        cmd_rss(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
