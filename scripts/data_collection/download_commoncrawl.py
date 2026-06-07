"""Common Crawl WET file downloader — web-scale text corpus.

Downloads WET (extracted text) files from Common Crawl S3,
parses WARC records, and saves as Markdown.

Usage:
    python download_commoncrawl.py kb_112
"""
from __future__ import annotations

import gzip
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.commoncrawl")

CC_S3_BASE = "https://data.commoncrawl.org/"
MAX_RECORDS_PER_FILE = 10000  # Safety limit per WET file


class CommonCrawlDownloader(DownloaderBase):
    """Download and process Common Crawl WET files."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()

        wet_url = self.config.extra.get("wet_url")
        max_files = self.config.extra.get("max_files", 10)
        offset = self.config.extra.get("offset", 0)

        if not wet_url:
            return {"kb_id": self.kb_id, "error": "No wet_url configured"}

        # Download the paths file
        paths = self._download_paths(wet_url)
        if not paths:
            return {"kb_id": self.kb_id, "error": "Failed to download paths file"}

        # Process subset of paths
        selected_paths = paths[offset:offset + max_files]
        logger.info("[cc] Processing %d WET files (offset=%d, total_paths=%d)",
                   len(selected_paths), offset, len(paths))

        total_records = 0
        total_chars = 0
        files_processed = 0

        for i, path in enumerate(selected_paths, 1):
            if self.progress.is_file_done(path):
                logger.info("[cc] Skipping already processed: %s", path)
                continue

            try:
                records, chars = self._process_wet_file(path)
                total_records += records
                total_chars += chars
                files_processed += 1
                self.progress.mark_file_done(path, f"wet_{i}", chars)
                logger.info("[cc] WET %d/%d: %s → %d records, %d chars",
                           i, len(selected_paths), path, records, chars)
            except Exception as exc:
                logger.error("[cc] WET failed %s: %s", path, exc)
                self.progress.log_error(path, str(exc))

        self.progress.mark_complete()
        return {
            "kb_id": self.kb_id,
            "files_processed": files_processed,
            "total_records": total_records,
            "total_chars": total_chars,
        }

    def _download_paths(self, wet_url: str) -> list[str]:
        """Download and parse the wet.paths.gz file."""
        if self.progress.is_file_done(wet_url):
            logger.info("[cc] Using cached paths file")
            # Return cached paths - but we don't store them, just re-download
            pass

        logger.info("[cc] Downloading paths file: %s", wet_url)
        try:
            resp = self.fetch(wet_url)
            # Decompress gzip
            data = gzip.decompress(resp.content)
            paths = [line.strip() for line in data.decode("utf-8").strip().split("\n") if line.strip()]
            logger.info("[cc] Loaded %d WET paths", len(paths))
            return paths
        except Exception as exc:
            logger.error("[cc] Paths download failed: %s", exc)
            return []

    def _download_wet_with_curl(self, url: str, dest: Path) -> bool:
        """Download WET file using curl with resume support."""
        for attempt in range(3):
            cmd = [
                "curl", "-L", "-C", "-", "-o", str(dest),
                "--max-time", "600", "--retry", "3",
                "-H", "User-Agent: Mozilla/5.0 (CommonCrawlDownloader/1.0)",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and dest.exists() and dest.stat().st_size > 1000000:
                return True
            logger.warning("[cc] curl download failed (attempt %d): %s", attempt + 1, result.stderr[:200])
        return False

    def _process_wet_file(self, path: str) -> tuple[int, int]:
        """Download and process a single WET file."""
        url = urljoin(CC_S3_BASE, path)
        wet_filename = path.replace("/", "_")
        wet_path = self.output_dir / "_wet_cache" / wet_filename
        wet_path.parent.mkdir(parents=True, exist_ok=True)

        # Download with curl (resume support)
        if not wet_path.exists() or wet_path.stat().st_size < 1000000:
            logger.info("[cc] Downloading WET: %s", url)
            if not self._download_wet_with_curl(url, wet_path):
                raise RuntimeError(f"Failed to download {url}")
        else:
            logger.info("[cc] Using cached WET: %s", wet_path)

        # Process the gzip file
        with gzip.open(wet_path, "rt", encoding="utf-8", errors="ignore") as f:
            records = 0
            total_chars = 0
            doc_counter = 0
            current_record = []
            in_content = False

            for line in f:
                line = line.rstrip("\n")
                if line.startswith("WARC/1.0"):
                    # Save previous record
                    if current_record and in_content:
                        text = "\n".join(current_record).strip()
                        if len(text) > 200:
                            doc_counter += 1
                            filename = f"doc_{doc_counter:06d}.md"
                            md = f"# Common Crawl Record {doc_counter}\n\n{text}"
                            self.save_text(filename, md, metadata={
                                "source": "Common Crawl",
                                "wet_file": path,
                                "record_num": doc_counter,
                            })
                            records += 1
                            total_chars += len(text)

                    current_record = []
                    in_content = False

                elif line.startswith("WARC-Type: conversion"):
                    in_content = True
                    current_record = []

                elif in_content and not line.startswith("WARC-"):
                    current_record.append(line)

                if records >= MAX_RECORDS_PER_FILE:
                    break

            # Save last record
            if current_record and in_content and len("\n".join(current_record).strip()) > 200:
                text = "\n".join(current_record).strip()
                doc_counter += 1
                filename = f"doc_{doc_counter:06d}.md"
                md = f"# Common Crawl Record {doc_counter}\n\n{text}"
                self.save_text(filename, md, metadata={
                    "source": "Common Crawl",
                    "wet_file": path,
                    "record_num": doc_counter,
                })
                records += 1
                total_chars += len(text)

        return records, total_chars


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_commoncrawl.py <kb_id>")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with CommonCrawlDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
