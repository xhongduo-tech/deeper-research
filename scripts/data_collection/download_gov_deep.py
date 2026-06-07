"""Deep government/legal data crawler with PDF and full-text extraction.

Unlike the basic crawler that only saves landing pages, this downloader:
- Discovers PDF/doc links on listing pages
- Downloads full PDFs and extracts text
- Recursively follows pagination
- Handles Chinese government site structures

Usage:
    python download_gov_deep.py kb_001   # Government work reports
    python download_gov_deep.py kb_008   # Constitution & laws
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from base import DownloaderBase, html_to_markdown, extract_text_from_pdf_bytes
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.gov_deep")

# Maximum pages to crawl per KB
MAX_PAGES = 200
# Maximum files to download per KB
MAX_FILES = 500
# File extensions we want to download
TARGET_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".html", ".htm"}


class GovDeepDownloader(DownloaderBase):
    """Deep crawler for Chinese government and legal websites."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()

        start_url = self.config.source_url
        deep_crawl = self.config.extra.get("deep_crawl", False)
        pdf_download = self.config.extra.get("pdf_download", True)
        full_text = self.config.extra.get("full_text", False)
        content_selector = self.config.extra.get("content_selector", "")

        logger.info("[gov_deep] Starting crawl: %s (deep=%s, pdf=%s)",
                   start_url, deep_crawl, pdf_download)

        # Track visited URLs
        visited: set[str] = set()
        to_visit: list[str] = [start_url]
        downloaded = 0
        pages_crawled = 0

        while to_visit and pages_crawled < MAX_PAGES and downloaded < MAX_FILES:
            url = to_visit.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                result = self._process_page(url, content_selector, pdf_download, full_text)
                pages_crawled += 1

                if result.get("downloaded"):
                    downloaded += 1

                # Discover new links
                if deep_crawl and "links" in result:
                    for link in result["links"]:
                        if link not in visited and len(visited) < MAX_PAGES * 2:
                            to_visit.append(link)

                if pages_crawled % 10 == 0:
                    logger.info("[gov_deep] Progress: %d pages, %d files downloaded",
                               pages_crawled, downloaded)

            except Exception as exc:
                logger.warning("[gov_deep] Page failed %s: %s", url, exc)
                self.progress.log_error(url, str(exc))

            time.sleep(1.5)  # Be polite

        self.progress.mark_complete()
        return {
            "kb_id": self.kb_id,
            "pages_crawled": pages_crawled,
            "files_downloaded": downloaded,
            "visited_urls": len(visited),
        }

    def _process_page(self, url: str, content_selector: str, pdf_download: bool, full_text: bool) -> dict[str, Any]:
        """Process a single page: extract content and discover links."""
        resp = self.fetch(url)
        content_type = resp.headers.get("content-type", "").lower()

        # If it's a binary file (PDF, DOC, etc.)
        if "pdf" in content_type:
            return self._handle_pdf(url, resp.content)
        elif "word" in content_type or "msword" in content_type:
            return self._handle_doc(url, resp.content)

        # HTML page
        soup = BeautifulSoup(resp.text, "html.parser")
        result: dict[str, Any] = {"downloaded": False, "links": []}

        # 1. Try to find and download PDF links
        if pdf_download:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(url, href)
                ext = Path(urlparse(full_url).path).suffix.lower()

                if ext in {".pdf", ".doc", ".docx"}:
                    if not self.progress.is_file_done(full_url):
                        try:
                            if ext == ".pdf":
                                file_resp = self.fetch(full_url)
                                self._handle_pdf(full_url, file_resp.content)
                            else:
                                # Save doc files as-is for now
                                file_resp = self.fetch(full_url)
                                self._save_binary(full_url, file_resp.content, ext)
                            result["downloaded"] = True
                        except Exception as exc:
                            logger.warning("[gov_deep] File download failed %s: %s", full_url, exc)
                        time.sleep(1)

        # 2. Extract page content
        if full_text or not result["downloaded"]:
            page_content = self._extract_page_content(soup, url, content_selector)
            if page_content and len(page_content) > 500:
                page_id = self._url_to_id(url)
                filename = f"doc_{page_id}.md"
                self.save_text(filename, page_content, metadata={
                    "source_url": url,
                    "title": self._extract_title(soup),
                })
                self.progress.mark_file_done(url, filename, len(page_content))
                result["downloaded"] = True

        # 3. Discover links for further crawling
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(url, href)

            # Only follow same-domain links
            if urlparse(full_url).netloc != urlparse(url).netloc:
                continue

            # Skip non-HTML links
            ext = Path(urlparse(full_url).path).suffix.lower()
            if ext in {".pdf", ".doc", ".docx", ".zip", ".rar", ".jpg", ".png"}:
                continue

            # Skip anchors and javascript
            if href.startswith(("#", "javascript:", "mailto:")):
                continue

            result["links"].append(full_url)

        return result

    def _handle_pdf(self, url: str, pdf_bytes: bytes) -> dict[str, Any]:
        """Download and extract text from a PDF."""
        text = extract_text_from_pdf_bytes(pdf_bytes)

        if text and len(text) > 100:
            page_id = self._url_to_id(url)
            filename = f"doc_{page_id}.md"

            content = f"# Document\n\n**Source:** {url}\n**Format:** PDF\n\n---\n\n{text}"
            self.save_text(filename, content, metadata={
                "source_url": url,
                "format": "pdf",
            })
            self.progress.mark_file_done(url, filename, len(text))
            return {"downloaded": True}
        else:
            # Save raw PDF if text extraction fails
            page_id = self._url_to_id(url)
            self.save_bytes(f"doc_{page_id}.pdf", pdf_bytes)
            self.progress.mark_file_done(url, f"doc_{page_id}.pdf", len(pdf_bytes))
            return {"downloaded": True}

    def _handle_doc(self, url: str, doc_bytes: bytes) -> dict[str, Any]:
        """Save a Word document."""
        page_id = self._url_to_id(url)
        self.save_bytes(f"doc_{page_id}.doc", doc_bytes)
        self.progress.mark_file_done(url, f"doc_{page_id}.doc", len(doc_bytes))
        return {"downloaded": True}

    def _save_binary(self, url: str, data: bytes, ext: str) -> None:
        """Save a binary file."""
        page_id = self._url_to_id(url)
        self.save_bytes(f"doc_{page_id}{ext}", data)
        self.progress.mark_file_done(url, f"doc_{page_id}{ext}", len(data))

    def _extract_page_content(self, soup: BeautifulSoup, url: str, content_selector: str) -> str:
        """Extract meaningful content from an HTML page."""
        # Remove noise
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Try content selector first
        if content_selector:
            content_elem = soup.select_one(content_selector)
            if content_elem:
                return html_to_markdown(str(content_elem))

        # Try common Chinese government site content areas
        selectors = [
            ".pages_content",
            ".content",
            "#content",
            ".article-content",
            ".TRS_Editor",
            ".detail-content",
            ".Custom_UnionStyle",
            "article",
            ".main",
            "#main",
        ]

        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                text = elem.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return html_to_markdown(str(elem))

        # Fallback: body text
        body = soup.find("body")
        if body:
            return html_to_markdown(str(body))

        return ""

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title."""
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return "Untitled"

    def _url_to_id(self, url: str) -> str:
        """Convert URL to safe file ID."""
        parsed = urlparse(url)
        path = parsed.path.strip("/").replace("/", "_")
        if not path:
            path = "index"
        # Truncate and sanitize
        safe = re.sub(r"[^\w\-]", "_", path)[:80]
        # Add hash for uniqueness
        import hashlib
        h = hashlib.md5(url.encode()).hexdigest()[:8]
        return f"{safe}_{h}"


def get_downloader(config):
    """Return a GovDeepDownloader instance for the given config."""
    return GovDeepDownloader(config)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_gov_deep.py <kb_id>")
        print("Examples: kb_001 (gov reports), kb_008 (laws)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with GovDeepCrawler(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
