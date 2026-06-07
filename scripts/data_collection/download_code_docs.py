"""Code documentation downloader using wget mirror + HTML extraction.

Downloads official documentation sites for programming languages/frameworks.
Uses wget for recursive mirroring, then extracts text content.

Usage:
    python download_code_docs.py kb_019   # Python docs
    python download_code_docs.py kb_020   # PyTorch docs
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from base import DownloaderBase, html_to_markdown
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.code_docs")


class CodeDocsDownloader(DownloaderBase):
    """Download code documentation using wget mirror."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        downloaded = 0
        base_url = self.config.source_url

        # Strategy 1: Try wget mirror for static docs
        mirror_dir = self.output_dir / "_mirror"
        mirror_dir.mkdir(parents=True, exist_ok=True)

        logger.info("[code_docs] Mirroring %s ...", base_url)
        try:
            result = subprocess.run(
                [
                    "wget", "--mirror", "--convert-links", "--adjust-extension",
                    "--page-requisites", "--no-parent",
                    "--domains", self._extract_domain(base_url),
                    "--timeout=30", "--tries=2",
                    "--user-agent=Mozilla/5.0",
                    "-P", str(mirror_dir),
                    base_url,
                ],
                capture_output=True,
                text=True,
                timeout=600,
            )
            logger.info("[code_docs] wget exit code: %d", result.returncode)
        except subprocess.TimeoutExpired:
            logger.warning("[code_docs] wget timed out for %s", base_url)
        except FileNotFoundError:
            logger.warning("[code_docs] wget not installed, falling back to HTTP fetch")
            # Fallback: fetch landing page only
            self._fetch_landing_page(base_url)
            downloaded += 1
            self.progress.mark_complete()
            return {"kb_id": self.kb_id, "downloaded": downloaded}

        # Convert mirrored HTML files to Markdown
        html_files = list(mirror_dir.rglob("*.html"))
        logger.info("[code_docs] Found %d HTML files in mirror", len(html_files))

        processed = 0
        for html_file in html_files[:500]:  # Limit to first 500 pages
            try:
                html = html_file.read_text(encoding="utf-8", errors="ignore")
                md = html_to_markdown(html)
                if len(md) > 500:
                    rel_path = html_file.relative_to(mirror_dir)
                    md_name = str(rel_path).replace(".html", ".md").replace("/", "_")
                    filename = f"doc_{md_name[:80]}"
                    self.save_text(filename, md, metadata={
                        "source": base_url,
                        "original_file": str(rel_path),
                    })
                    processed += 1
            except Exception as exc:
                logger.debug("[code_docs] Failed to convert %s: %s", html_file, exc)

        downloaded += processed

        # Also fetch landing page if mirror produced nothing
        if processed == 0:
            self._fetch_landing_page(base_url)
            downloaded += 1

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")

    def _fetch_landing_page(self, url: str) -> None:
        """Fetch just the landing page as fallback."""
        try:
            resp = self.fetch(url)
            md = html_to_markdown(resp.text)
            if len(md) > 200:
                self.save_text("doc_index.md", md, metadata={"source": url})
        except Exception as exc:
            logger.error("[code_docs] Landing page failed: %s", exc)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_code_docs.py <kb_id>")
        print("Examples: kb_019 (Python), kb_020 (PyTorch), kb_021 (React)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with CodeDocsDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
