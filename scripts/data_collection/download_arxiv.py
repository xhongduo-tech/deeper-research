"""ArXiv bulk downloader using the official (free) API.

Fetches paper metadata + abstracts via arXiv API.
Does NOT download PDFs by default (too large); stores abstract + metadata.

Usage:
    python download_arxiv.py kb_015   # CS/AI/ML papers
    python download_arxiv.py kb_016   # Math/Physics papers
"""
from __future__ import annotations

import logging
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.arxiv")

ARXIV_API_BASE = "https://export.arxiv.org/api/query"
NAMESPACE = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
BATCH_SIZE = 100  # arXiv API max results per request
DELAY_BETWEEN_REQUESTS = 10  # seconds — be polite to arXiv (increased to avoid 429)
MAX_BACKOFF_DELAY = 60  # maximum delay on 429 errors


class ArxivDownloader(DownloaderBase):
    """Download arXiv paper metadata and abstracts."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        categories = self.config.extra.get("categories", ["cs.AI"])
        max_results = self.config.extra.get("max_results", 10000)
        start_year, end_year = self.config.time_range

        date_filter = f"submittedDate:[{start_year}0101 TO {end_year}0630]"
        cat_filter = " OR ".join(f"cat:{c}" for c in categories)
        query = f"({cat_filter}) AND {date_filter}"

        logger.info("[arxiv] Query: %s, max_results=%d", query, max_results)

        downloaded = 0
        total_papers = 0
        start = 0

        while start < max_results:
            batch = self._fetch_batch(query, start, BATCH_SIZE)
            if not batch:
                break

            for paper in batch:
                self._save_paper(paper)
                downloaded += 1

            total_papers += len(batch)
            start += len(batch)
            logger.info("[arxiv] Progress: %d/%d papers", total_papers, max_results)

            if len(batch) < BATCH_SIZE:
                break

            time.sleep(DELAY_BETWEEN_REQUESTS)

        self.progress.mark_complete()
        return {
            "kb_id": self.kb_id,
            "downloaded": downloaded,
            "categories": categories,
        }

    def _fetch_batch(self, query: str, start: int, max_results: int) -> list[dict[str, Any]]:
        """Fetch one batch of results from arXiv API."""
        url = (
            f"{ARXIV_API_BASE}?"
            f"search_query={quote(query)}"
            f"&start={start}&max_results={max_results}"
            f"&sort=submittedDate&sortOrder=descending"
        )

        if self.progress.is_file_done(url):
            logger.debug("[arxiv] Skipping cached batch: start=%d", start)
            return []

        backoff = DELAY_BETWEEN_REQUESTS
        for attempt in range(3):
            try:
                resp = self.fetch(url)
                root = ET.fromstring(resp.text.encode("utf-8"))
                entries = root.findall("atom:entry", NAMESPACE)

                papers = []
                for entry in entries:
                    paper = self._parse_entry(entry)
                    if paper:
                        papers.append(paper)

                self.progress.mark_file_done(url, f"batch_{start}", len(papers))
                return papers
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning("[arxiv] 429 rate limited (start=%d), backing off %ds...", start, backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_DELAY)
                    continue
                logger.error("[arxiv] Batch HTTP error (start=%d): %s", start, exc)
                self.progress.log_error(url, str(exc))
                return []
            except Exception as exc:
                logger.error("[arxiv] Batch failed (start=%d): %s", start, exc)
                self.progress.log_error(url, str(exc))
                return []
        logger.error("[arxiv] Batch failed after retries (start=%d): rate limited", start)
        self.progress.log_error(url, "rate_limited_429")
        return []

    def _parse_entry(self, entry: ET.Element) -> dict[str, Any] | None:
        """Parse a single arXiv entry."""
        try:
            id_elem = entry.find("atom:id", NAMESPACE)
            title_elem = entry.find("atom:title", NAMESPACE)
            summary_elem = entry.find("atom:summary", NAMESPACE)
            published_elem = entry.find("atom:published", NAMESPACE)

            if id_elem is None or title_elem is None or summary_elem is None:
                return None

            authors = entry.findall("atom:author/atom:name", NAMESPACE)
            categories = entry.findall("atom:category", NAMESPACE)

            arxiv_id = id_elem.text.split("/abs/")[-1] if id_elem.text else "unknown"

            return {
                "arxiv_id": arxiv_id,
                "title": (title_elem.text or "").strip().replace("\n", " "),
                "abstract": (summary_elem.text or "").strip(),
                "published": published_elem.text if published_elem is not None else "",
                "authors": [a.text for a in authors if a.text],
                "categories": [c.get("term", "") for c in categories],
                "url": f"https://arxiv.org/abs/{arxiv_id}",
            }
        except Exception as exc:
            logger.debug("[arxiv] Parse error: %s", exc)
            return None

    def _save_paper(self, paper: dict[str, Any]) -> None:
        """Save paper as Markdown file."""
        arxiv_id = paper["arxiv_id"].replace("/", "_")
        filename = f"doc_{arxiv_id}.md"

        content = f"""# {paper['title']}

**arXiv ID:** {paper['arxiv_id']}
**Published:** {paper['published']}
**Authors:** {', '.join(paper['authors'])}
**Categories:** {', '.join(paper['categories'])}
**URL:** {paper['url']}

## Abstract

{paper['abstract']}
"""
        self.save_text(filename, content, metadata={
            "arxiv_id": paper["arxiv_id"],
            "title": paper["title"],
            "published": paper["published"],
            "authors": paper["authors"],
            "categories": paper["categories"],
        })


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_arxiv.py <kb_id>")
        print("Examples: kb_015 (CS/AI/ML), kb_016 (Math/Physics)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with ArxivDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
