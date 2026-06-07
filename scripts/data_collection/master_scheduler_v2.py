"""Master scheduler V2 — orchestrates all KB downloads with progress tracking.

Runs all downloaders sequentially (polite to external servers),
persists progress, and generates a summary report.

Usage:
    python master_scheduler_v2.py              # Run all pending downloads
    python master_scheduler_v2.py --category academic  # Run only academic
    python master_scheduler_v2.py --kb kb_062,kb_064   # Run specific KBs
    python master_scheduler_v2.py --status     # Show current status
    python master_scheduler_v2.py --books      # Run all book KBs
    python master_scheduler_v2.py --wikipedia  # Run Wikipedia dumps
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config_v2 import ALL_SOURCES, get_source_by_id

logger = logging.getLogger("data_collection.master")

# Map download methods and kb_types to downloader modules
CATEGORY_MODULES = {
    "gov": "download_gov_deep",
    "finance": "download_gov_deep",
    "statistics": "download_gov_deep",
    "law": "download_gov_deep",
    "news": "download_rss",
    "academic": "download_arxiv",
    "code": "download_git",
    "math": "download_arxiv",
    "intl": "download_gov_deep",
    "tech": "download_gov_deep",
    "trade": "download_gov_deep",
    "policy": "download_gov_deep",
    "book": "download_books",
    "general": "download_wikipedia",
}

METHOD_MODULES = {
    "crawl": "download_gov_deep",
    "rss": "download_rss",
    "api_free": "download_arxiv",
    "git": "download_git",
    "wget": "download_code_docs",
    "direct": "download_wikipedia",
}

# KB-specific module overrides
KB_MODULE_OVERRIDES = {
    "kb_017": "download_pubmed",
    "kb_019": "download_code_docs",
    "kb_020": "download_code_docs",
    "kb_021": "download_code_docs",
    "kb_022": "download_code_docs",
    "kb_023": "download_code_docs",
    "kb_024": "download_code_docs",
    "kb_026": "download_code_docs",
    "kb_027": "download_code_docs",
    "kb_048": "download_code_docs",
    "kb_049": "download_code_docs",
    "kb_050": "download_code_docs",
    "kb_051": "download_code_docs",
    "kb_052": "download_code_docs",
    "kb_053": "download_code_docs",
    "kb_054": "download_code_docs",
    "kb_055": "download_code_docs",
    "kb_056": "download_code_docs",
    "kb_028": "download_gov_deep",
    "kb_029": "download_gov_deep",
    "kb_030": "download_gov_deep",
    "kb_059": "download_gov_deep",
    "kb_060": "download_gov_deep",
    "kb_061": "download_gov_deep",
    "kb_062": "download_books",
    "kb_063": "download_books",
    "kb_064": "download_books",
    "kb_065": "download_git",
    "kb_066": "download_gov_deep",
    "kb_067": "download_books",
    "kb_068": "download_books",
    "kb_069": "download_books",
    "kb_070": "download_gov_deep",
    "kb_071": "download_gov_deep",
    "kb_072": "download_gov_deep",
    "kb_073": "download_gov_deep",
    "kb_074": "download_gov_deep",
    "kb_075": "download_gov_deep",
    "kb_076": "download_gov_deep",
    "kb_077": "download_gov_deep",
    "kb_078": "download_gov_deep",
    "kb_079": "download_gov_deep",
    "kb_080": "download_gov_deep",
    "kb_081": "download_gov_deep",
    "kb_082": "download_gov_deep",
    "kb_083": "download_gov_deep",
    "kb_084": "download_gov_deep",
    "kb_085": "download_gov_deep",
    "kb_086": "download_wikipedia",
    "kb_087": "download_wikipedia",
    "kb_088": "download_wikipedia",
    "kb_089": "download_gov_deep",
    "kb_090": "download_gov_deep",
    "kb_099": "download_wikipedia",
    "kb_100": "download_wikipedia",
    "kb_101": "download_wikipedia",
    "kb_102": "download_wikipedia",
    "kb_103": "download_wikipedia",
    "kb_104": "download_wikipedia",
    "kb_105": "download_wikipedia",
    "kb_106": "download_wikipedia",
    "kb_107": "download_wikipedia",
    "kb_108": "download_wikipedia",
    "kb_109": "download_wikipedia",
    "kb_110": "download_wikipedia",
    "kb_111": "download_wikipedia",
    "kb_112": "download_commoncrawl",
    "kb_113": "download_commoncrawl",
    "kb_114": "download_commoncrawl",
    "kb_115": "download_commoncrawl",
    "kb_116": "download_commoncrawl",
    "kb_117": "download_commoncrawl",
    "kb_118": "download_commoncrawl",
    "kb_119": "download_commoncrawl",
    "kb_120": "download_commoncrawl",
    "kb_121": "download_commoncrawl",
    "kb_122": "download_commoncrawl",
    "kb_123": "download_commoncrawl",
    "kb_124": "download_commoncrawl",
    "kb_125": "download_git",
    "kb_126": "download_git",
    "kb_127": "download_git",
    "kb_128": "download_git",
    "kb_129": "download_git",
    "kb_130": "download_git",
    "kb_131": "download_git",
    "kb_132": "download_git",
    "kb_133": "download_git",
    "kb_134": "download_git",
    "kb_135": "download_arxiv",
    "kb_136": "download_arxiv",
    "kb_137": "download_arxiv",
    "kb_138": "download_arxiv",
    "kb_139": "download_arxiv",
    "kb_140": "download_arxiv",
    "kb_141": "download_arxiv",
    "kb_142": "download_arxiv",
    "kb_143": "download_arxiv",
    "kb_144": "download_arxiv",
    "kb_145": "download_books",
    "kb_146": "download_books",
    "kb_147": "download_books",
    "kb_148": "download_books",
    "kb_149": "download_books",
    "kb_150": "download_books",
    "kb_151": "download_books",
    "kb_152": "download_books",
    "kb_091": "download_books",
    "kb_092": "download_code_docs",
    "kb_093": "download_code_docs",
    "kb_094": "download_gov_deep",
    "kb_095": "download_gov_deep",
    "kb_096": "download_gov_deep",
    "kb_097": "download_gov_deep",
    "kb_098": "download_pubmed",
}


def _resolve_module(source) -> str:
    if source.kb_id in KB_MODULE_OVERRIDES:
        return KB_MODULE_OVERRIDES[source.kb_id]
    if source.kb_type in CATEGORY_MODULES:
        return CATEGORY_MODULES[source.kb_type]
    return METHOD_MODULES.get(source.download_method, "download_gov_deep")


def _run_single(source) -> dict[str, Any]:
    module_name = _resolve_module(source)
    try:
        module = importlib.import_module(module_name)

        # Try module-specific get_downloader function first
        if hasattr(module, "get_downloader"):
            dl = module.get_downloader(source)
            return dl.run()

        # Fallback: find first Downloader class
        downloader_class = None
        for attr_name in dir(module):
            if attr_name.endswith("Downloader") and attr_name != "DownloaderBase":
                downloader_class = getattr(module, attr_name)
                break
        if downloader_class is None:
            return {"kb_id": source.kb_id, "error": f"No downloader in {module_name}"}

        with downloader_class(source) as dl:
            return dl.run()
    except Exception as exc:
        logger.error("[master] %s crashed: %s", source.kb_id, exc)
        traceback.print_exc()
        return {"kb_id": source.kb_id, "error": str(exc)}


def _filter_by_since(source, since_year: int | None) -> bool:
    """Return True if source time_range overlaps with since_year."""
    if since_year is None:
        return True
    start_year, end_year = getattr(source, "time_range", (2020, 2026))
    return end_year >= since_year


def run_all(filter_category: str | None = None, filter_kb_ids: list[str] | None = None,
            skip_completed: bool = True, filter_type: str | None = None,
            workers: int = 8, since_year: int | None = None) -> dict[str, Any]:
    sources = [s for s in ALL_SOURCES]
    if filter_kb_ids:
        sources = [s for s in sources if s.kb_id in filter_kb_ids]
    if filter_category:
        sources = [s for s in sources if s.kb_type == filter_category]
    if filter_type:
        sources = [s for s in sources if s.download_method == filter_type]
    if since_year is not None:
        sources = [s for s in sources if _filter_by_since(s, since_year)]

    total = len(sources)
    success = 0
    failed = 0
    skipped = 0
    results = []

    logger.info("=" * 60)
    logger.info("MASTER SCHEDULER V2 START — %d KBs queued (workers=%d, since=%s)", total, workers, since_year)
    logger.info("=" * 60)

    def _process_source(args):
        idx, source = args
        # Check if already completed
        progress_path = Path("./data/download_progress") / f"{source.kb_id}.json"
        if skip_completed and progress_path.exists():
            try:
                with open(progress_path) as f:
                    data = json.load(f)
                if data.get("completed"):
                    return {"kb_id": source.kb_id, "skipped": True}
            except Exception:
                pass

        logger.info("[%d/%d] Processing %s — %s", idx, total, source.kb_id, source.name)
        start = time.time()
        result = _run_single(source)
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 1)
        logger.info("  -> %s (%s): %.1fs", "SUCCESS" if "error" not in result else "FAILED", source.kb_id, elapsed)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_results = list(executor.map(_process_source, enumerate(sources, 1)))

    for result in future_results:
        if result.get("skipped"):
            skipped += 1
            continue
        results.append(result)
        if "error" in result:
            failed += 1
        else:
            success += 1

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }

    summary_path = Path("./data/download_progress/master_summary_v2.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info("=" * 60)
    logger.info("MASTER SCHEDULER V2 DONE")
    logger.info("  Total: %d | Success: %d | Failed: %d | Skipped: %d", total, success, failed, skipped)
    logger.info("  Summary saved to: %s", summary_path)
    logger.info("=" * 60)
    return summary


def show_status() -> None:
    sources = ALL_SOURCES
    progress_dir = Path("./data/download_progress")

    completed = 0
    pending = 0
    errors = 0

    print("\n" + "=" * 70)
    print("DOWNLOAD STATUS V2")
    print("=" * 70)

    for source in sources:
        progress_path = progress_dir / f"{source.kb_id}.json"
        if progress_path.exists():
            try:
                with open(progress_path) as f:
                    data = json.load(f)
                if data.get("completed"):
                    status = "DONE"
                    completed += 1
                else:
                    status = f"PARTIAL ({len(data.get('files', {}))} files)"
                    pending += 1
                if data.get("errors"):
                    errors += len(data["errors"])
            except Exception:
                status = "CORRUPT"
                pending += 1
        else:
            status = "PENDING"
            pending += 1

        print(f"  {source.kb_id:8s} | {status:30s} | {source.name}")

    print("-" * 70)
    print(f"  Total: {len(sources)} | Completed: {completed} | Pending: {pending} | Errors: {errors}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="DataAgent Master Download Scheduler V2")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--kb", help="Comma-separated KB IDs")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--no-skip", action="store_true", help="Don't skip completed KBs")
    parser.add_argument("--books", action="store_true", help="Run all book KBs")
    parser.add_argument("--wikipedia", action="store_true", help="Run Wikipedia dumps")
    parser.add_argument("--academic", action="store_true", help="Run all academic KBs")
    parser.add_argument("--code", action="store_true", help="Run all code KBs")
    parser.add_argument("--gov", action="store_true", help="Run all government KBs")
    parser.add_argument("--method", help="Filter by download method")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent download workers (default 8)")
    parser.add_argument("--since", type=int, default=2023, help="Only download data from this year onward (default 2023)")
    args = parser.parse_args()

    log_dir = Path("./data/download_progress")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_dir / "master_v2.log"), encoding="utf-8"),
        ],
    )

    if args.status:
        show_status()
        return

    kb_ids = None
    category = None
    method = None

    if args.books:
        kb_ids = [s.kb_id for s in ALL_SOURCES if s.kb_type == "book"]
    elif args.wikipedia:
        kb_ids = [s.kb_id for s in ALL_SOURCES if s.download_method == "direct"]
    elif args.academic:
        kb_ids = [s.kb_id for s in ALL_SOURCES if s.kb_type == "academic"]
    elif args.code:
        kb_ids = [s.kb_id for s in ALL_SOURCES if s.kb_type == "code"]
    elif args.gov:
        kb_ids = [s.kb_id for s in ALL_SOURCES if s.kb_type in ("policy", "law", "statistics", "finance", "trade")]
    elif args.kb:
        kb_ids = args.kb.split(",")

    if args.category:
        category = args.category
    if args.method:
        method = args.method

    run_all(
        filter_category=category,
        filter_kb_ids=kb_ids,
        skip_completed=not args.no_skip,
        filter_type=method,
        workers=args.workers,
        since_year=args.since,
    )


if __name__ == "__main__":
    main()
