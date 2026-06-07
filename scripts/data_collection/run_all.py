"""Unified scheduler for all data collection scripts.

Runs downloaders in parallel (per category) with progress tracking.
Resume capability via JSON progress files.

Usage:
    # Download everything
    python run_all.py

    # Download specific categories
    python run_all.py --category gov,finance,academic

    # Download specific KBs
    python run_all.py --kb kb_001,kb_015,kb_025

    # Resume incomplete downloads
    python run_all.py --resume

    # Dry run (show what would be downloaded)
    python run_all.py --dry-run
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import PHASE1_SOURCES, get_source_by_id

logger = logging.getLogger("data_collection.scheduler")


# Map download method → module name
METHOD_MODULES = {
    "crawl": "download_gov",
    "rss": "download_rss",
    "api_free": "download_arxiv",
    "git": "download_git",
}

# Category-specific overrides
CATEGORY_MODULES = {
    "gov": "download_gov",
    "finance": "download_gov",
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


def _resolve_module(source) -> str:
    """Determine which download module to use for a source."""
    # Category override takes precedence
    if source.kb_type in CATEGORY_MODULES:
        return CATEGORY_MODULES[source.kb_type]
    # Fall back to download_method mapping
    return METHOD_MODULES.get(source.download_method, "download_gov")


def _run_single(source) -> dict[str, Any]:
    """Run a single KB downloader."""
    module_name = _resolve_module(source)
    try:
        module = importlib.import_module(module_name)
        downloader_class = getattr(module, f"{module_name.replace('download_', '').capitalize()}Downloader", None)
        if downloader_class is None:
            # Try generic class names
            for attr_name in dir(module):
                if attr_name.endswith("Downloader") and attr_name != "DownloaderBase":
                    downloader_class = getattr(module, attr_name)
                    break

        if downloader_class is None:
            return {"kb_id": source.kb_id, "error": f"No downloader class found in {module_name}"}

        with downloader_class(source) as dl:
            return dl.run()
    except Exception as exc:
        logger.error("[scheduler] Failed %s: %s", source.kb_id, exc)
        return {"kb_id": source.kb_id, "error": str(exc)}


def run(
    categories: list[str] | None = None,
    kb_ids: list[str] | None = None,
    resume: bool = False,
    dry_run: bool = False,
    max_workers: int = 3,
) -> dict[str, Any]:
    """Run downloaders matching filters."""

    # Filter sources
    sources = PHASE1_SOURCES[:]
    if kb_ids:
        sources = [s for s in sources if s.kb_id in kb_ids]
    if categories:
        sources = [s for s in sources if s.kb_type in categories]

    if not sources:
        logger.warning("No sources match the given filters")
        return {"total": 0, "success": 0, "failed": 0, "results": []}

    logger.info("[scheduler] %d KBs to download", len(sources))

    if dry_run:
        for s in sources:
            print(f"  {s.kb_id}: {s.name} ({s.download_method}) → {s.output_dir}")
        return {"total": len(sources), "dry_run": True}

    results = []
    success = 0
    failed = 0

    # Run with limited parallelism (be polite to servers)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(_run_single, s): s for s in sources}
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                result = future.result(timeout=3600)
                results.append(result)
                if "error" in result:
                    failed += 1
                else:
                    success += 1
                logger.info("[scheduler] %s: %s", source.kb_id, result)
            except Exception as exc:
                logger.error("[scheduler] %s crashed: %s", source.kb_id, exc)
                results.append({"kb_id": source.kb_id, "error": str(exc)})
                failed += 1

    summary = {
        "total": len(sources),
        "success": success,
        "failed": failed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }

    # Save summary
    summary_path = Path("./data/download_progress/summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    logger.info("[scheduler] Done. Success: %d, Failed: %d", success, failed)
    return summary


def main():
    parser = argparse.ArgumentParser(description="DataAgent KB bulk downloader")
    parser.add_argument("--category", help="Comma-separated categories (gov,finance,academic,...)")
    parser.add_argument("--kb", help="Comma-separated KB IDs (kb_001,kb_015,...)")
    parser.add_argument("--resume", action="store_true", help="Resume incomplete downloads")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers (default: 3)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    categories = args.category.split(",") if args.category else None
    kb_ids = args.kb.split(",") if args.kb else None

    result = run(
        categories=categories,
        kb_ids=kb_ids,
        resume=args.resume,
        dry_run=args.dry_run,
        max_workers=args.workers,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
