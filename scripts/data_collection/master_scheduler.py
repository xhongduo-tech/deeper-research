"""Master scheduler — orchestrates all KB downloads with progress tracking.

Runs all downloaders sequentially (polite to external servers),
persists progress, and generates a summary report.

Usage:
    python master_scheduler.py              # Run all pending downloads
    python master_scheduler.py --category academic  # Run only academic
    python master_scheduler.py --status     # Show current status
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PHASE1_SOURCES, get_source_by_id

logger = logging.getLogger("data_collection.master")

CATEGORY_MODULES = {
    "gov": "download_gov",
    "finance": "download_finance",
    "statistics": "download_gov",
    "law": "download_gov",
    "news": "download_rss",
    "academic": "download_arxiv",
    "code": "download_git",
    "math": "download_gov",
    "intl": "download_gov",
    "tech": "download_gov",
    "trade": "download_gov",
    "policy": "download_gov",
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
}

def _resolve_module(source) -> str:
    if source.kb_id in KB_MODULE_OVERRIDES:
        return KB_MODULE_OVERRIDES[source.kb_id]
    if source.kb_type in CATEGORY_MODULES:
        return CATEGORY_MODULES[source.kb_type]
    method_map = {"crawl": "download_gov", "rss": "download_rss", "api_free": "download_arxiv", "git": "download_git"}
    return method_map.get(source.download_method, "download_gov")


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


def run_all(filter_category: str | None = None, filter_kb_ids: list[str] | None = None, skip_completed: bool = True) -> dict[str, Any]:
    sources = [s for s in PHASE1_SOURCES]
    if filter_kb_ids:
        sources = [s for s in sources if s.kb_id in filter_kb_ids]
    if filter_category:
        sources = [s for s in sources if s.kb_type == filter_category]

    total = len(sources)
    success = 0
    failed = 0
    skipped = 0
    results = []

    logger.info("=" * 60)
    logger.info("MASTER SCHEDULER START — %d KBs queued", total)
    logger.info("=" * 60)

    for idx, source in enumerate(sources, 1):
        logger.info("")
        logger.info("[%d/%d] Processing %s — %s", idx, total, source.kb_id, source.name)

        # Check if already completed
        progress_path = Path(f"./data/download_progress/{source.kb_id}.json")
        if skip_completed and progress_path.exists():
            try:
                with open(progress_path) as f:
                    data = json.load(f)
                if data.get("completed"):
                    logger.info("  -> Already completed, skipping")
                    skipped += 1
                    continue
            except Exception:
                pass

        start = time.time()
        result = _run_single(source)
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 1)
        results.append(result)

        if "error" in result:
            failed += 1
            logger.error("  -> FAILED (%s): %s", source.kb_id, result.get("error"))
        else:
            success += 1
            logger.info("  -> SUCCESS (%s): %s in %.1fs", source.kb_id, result, elapsed)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }

    summary_path = Path("./data/download_progress/master_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("")
    logger.info("=" * 60)
    logger.info("MASTER SCHEDULER DONE")
    logger.info("  Total: %d | Success: %d | Failed: %d | Skipped: %d", total, success, failed, skipped)
    logger.info("  Summary saved to: %s", summary_path)
    logger.info("=" * 60)
    return summary


def show_status() -> None:
    sources = PHASE1_SOURCES
    progress_dir = Path("./data/download_progress")

    completed = 0
    pending = 0
    errors = 0

    print("\n" + "=" * 70)
    print("DOWNLOAD STATUS")
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

        print(f"  {source.kb_id:8s} | {status:20s} | {source.name}")

    print("-" * 70)
    print(f"  Total: {len(sources)} | Completed: {completed} | Pending: {pending} | Errors: {errors}")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="DataAgent Master Download Scheduler")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--kb", help="Comma-separated KB IDs")
    parser.add_argument("--status", action="store_true", help="Show status only")
    parser.add_argument("--no-skip", action="store_true", help="Don't skip completed KBs")
    args = parser.parse_args()

    log_dir = Path("./data/download_progress")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(str(log_dir / "master.log"), encoding="utf-8"),
        ],
    )

    if args.status:
        show_status()
        return

    kb_ids = args.kb.split(",") if args.kb else None
    run_all(filter_category=args.category, filter_kb_ids=kb_ids, skip_completed=not args.no_skip)


if __name__ == "__main__":
    main()
