"""PubMed biomedical paper downloader using free E-utilities API.

Fetches paper abstracts and metadata via NCBI E-utilities.
No API key required (but be polite with rate limits).

Usage:
    python download_pubmed.py kb_017
"""
from __future__ import annotations

import json
import logging
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.pubmed")

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
BATCH_SIZE = 100  # Max IDs per efetch request
DELAY = 0.35  # NCBI recommends ~3 requests/second


class PubMedDownloader(DownloaderBase):
    """Download PubMed paper metadata and abstracts."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        search_terms = self.config.extra.get("search_terms", ["machine learning"])
        max_results = self.config.extra.get("max_results", 20000)
        start_year, end_year = self.config.time_range

        downloaded = 0
        for term in search_terms:
            logger.info("[pubmed] Searching: %s", term)
            try:
                pmids = self._search_pmids(term, start_year, end_year, max_results // len(search_terms))
                logger.info("[pubmed] Found %d PMIDs for '%s'", len(pmids), term)

                for i in range(0, len(pmids), BATCH_SIZE):
                    batch = pmids[i:i + BATCH_SIZE]
                    papers = self._fetch_details(batch)
                    for paper in papers:
                        self._save_paper(paper)
                        downloaded += 1
                    time.sleep(DELAY)
            except Exception as exc:
                logger.error("[pubmed] Search '%s' failed: %s", term, exc)
                self.progress.log_error(term, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _search_pmids(self, term: str, start_year: int, end_year: int, max_results: int) -> list[str]:
        """Search PubMed and return list of PMIDs."""
        query = f"({term}) AND ({start_year}:{end_year}[PDAT])"
        url = f"{NCBI_BASE}/esearch.fcgi?db=pubmed&{urlencode({'term': query, 'retmax': max_results, 'retmode': 'json'})}"

        resp = self.fetch(url)
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])

    def _fetch_details(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Fetch details for a batch of PMIDs."""
        if not pmids:
            return []

        url = f"{NCBI_BASE}/efetch.fcgi?db=pubmed&id={','.join(pmids)}&retmode=xml"
        resp = self.fetch(url)

        root = ET.fromstring(resp.content)
        papers = []
        for article in root.findall(".//PubmedArticle"):
            paper = self._parse_article(article)
            if paper:
                papers.append(paper)
        return papers

    def _parse_article(self, article: ET.Element) -> dict[str, Any] | None:
        """Parse a single PubMed article XML."""
        try:
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            title_elem = article.find(".//ArticleTitle")
            title = (title_elem.text or "").strip() if title_elem is not None else ""

            abstract_elems = article.findall(".//AbstractText")
            abstract = " ".join((e.text or "") for e in abstract_elems if e.text)

            year_elem = article.find(".//PubDate/Year")
            year = year_elem.text if year_elem is not None else ""

            authors = []
            for author in article.findall(".//Author"):
                last = author.find("LastName")
                first = author.find("ForeName")
                if last is not None:
                    name = last.text or ""
                    if first is not None:
                        name = f"{first.text} {name}"
                    authors.append(name)

            keywords = [k.text for k in article.findall(".//Keyword") if k.text]

            return {
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "authors": authors,
                "keywords": keywords,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        except Exception as exc:
            logger.debug("[pubmed] Parse error: %s", exc)
            return None

    def _save_paper(self, paper: dict[str, Any]) -> None:
        """Save paper as Markdown."""
        filename = f"doc_pmid{paper['pmid']}.md"
        content = f"""# {paper['title']}

**PMID:** {paper['pmid']}
**Year:** {paper['year']}
**Authors:** {', '.join(paper['authors'])}
**Keywords:** {', '.join(paper['keywords'])}
**URL:** {paper['url']}

## Abstract

{paper['abstract']}
"""
        self.save_text(filename, content, metadata={
            "pmid": paper["pmid"],
            "title": paper["title"],
            "year": paper["year"],
        })


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_pubmed.py <kb_id>")
        print("Example: kb_017 (PubMed biomedical)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with PubMedDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
