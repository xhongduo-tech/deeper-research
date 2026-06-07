"""Book downloader for free/open access sources.

Sources:
- Project Gutenberg (gutenberg.org) — 70,000+ public domain ebooks
- OpenStax (openstax.org) — free college textbooks
- Standard Ebooks (standardebooks.org) — high quality public domain
- ManyBooks (manybooks.net) — free ebooks
- Chinese Text Project (ctext.org) — Chinese classics

Usage:
    python download_books.py kb_062   # Gutenberg English
    python download_books.py kb_064   # OpenStax textbooks
"""
from __future__ import annotations

import logging
import re
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from base import DownloaderBase, html_to_markdown
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.books")

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


# ── Project Gutenberg ─────────────────────────────────────────────────────────

class GutenbergDownloader(DownloaderBase):
    """Download ebooks from Project Gutenberg.

    Gutenberg provides catalog browsing and plain text downloads.
    Files are in the public domain.
    """

    BASE_URL = "https://www.gutenberg.org"
    MIRROR_URL = "https://www.gutenberg.org/files/{ebook_id}/{ebook_id}-0.txt"

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        max_books = self.config.extra.get("max_books", 1000)
        language = self.config.extra.get("language", "en")
        catalog_url = self.config.extra.get("catalog_url",
            f"{self.BASE_URL}/ebooks/search/?sort_order=downloads&query=l.{language}")

        logger.info("[gutenberg] language=%s max_books=%d", language, max_books)

        downloaded = 0
        page = 1

        while downloaded < max_books:
            book_ids = self._fetch_catalog_page(catalog_url, page)
            if not book_ids:
                break

            for book_id in book_ids:
                if downloaded >= max_books:
                    break
                if self.progress.is_file_done(f"gutenberg_{book_id}"):
                    continue

                try:
                    self._download_book(book_id)
                    downloaded += 1
                    if downloaded % 50 == 0:
                        logger.info("[gutenberg] Downloaded %d/%d books", downloaded, max_books)
                except Exception as exc:
                    logger.warning("[gutenberg] Book %s failed: %s", book_id, exc)
                    self.progress.log_error(f"gutenberg_{book_id}", str(exc))

                time.sleep(0.5)

            page += 1
            if page > 50:
                break
            time.sleep(1)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _fetch_catalog_page(self, catalog_url: str, page: int) -> list[str]:
        """Fetch book IDs from a catalog page."""
        url = f"{catalog_url}&start_index={(page - 1) * 25 + 1}"
        try:
            resp = self.fetch(url)
            soup = BeautifulSoup(resp.text, "html.parser")
            links = soup.find_all("li", class_="booklink")
            ids = []
            for link in links:
                a = link.find("a", href=re.compile(r"/ebooks/\d+"))
                if a:
                    match = re.search(r"/ebooks/(\d+)", a.get("href", ""))
                    if match:
                        ids.append(match.group(1))
            return ids
        except Exception as exc:
            logger.warning("[gutenberg] Catalog page %d failed: %s", page, exc)
            return []

    def _download_book(self, ebook_id: str) -> None:
        """Download a single book as plain text."""
        # Try multiple mirror patterns
        urls = [
            f"{self.BASE_URL}/files/{ebook_id}/{ebook_id}-0.txt",
            f"{self.BASE_URL}/files/{ebook_id}/{ebook_id}.txt",
            f"{self.BASE_URL}/ebooks/{ebook_id}.txt.utf-8",
        ]

        for url in urls:
            try:
                resp = self.fetch(url)
                content = resp.text
                if len(content) > 100:
                    break
            except Exception:
                continue
        else:
            raise RuntimeError(f"All mirrors failed for ebook {ebook_id}")

        # Extract title from content
        title = self._extract_title(content) or f"book_{ebook_id}"
        safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip()
        filename = f"doc_{int(ebook_id):05d}_{safe_title}.md"

        # Convert to markdown
        md_content = f"# {title}\n\n**Source:** Project Gutenberg (ebook #{ebook_id})\n**URL:** {self.BASE_URL}/ebooks/{ebook_id}\n\n---\n\n{content}"

        self.save_text(filename, md_content, metadata={
            "source": "Project Gutenberg",
            "ebook_id": ebook_id,
            "title": title,
            "language": self.config.extra.get("language", "en"),
        })
        self.progress.mark_file_done(f"gutenberg_{ebook_id}", filename, len(content))

    def _extract_title(self, content: str) -> str | None:
        """Try to extract title from Gutenberg header."""
        lines = content.split("\n")[:20]
        for line in lines:
            line = line.strip()
            if line.startswith("Title: "):
                return line[7:].strip()
            if line.startswith("Title:"):
                return line[6:].strip()
        return None


# ── OpenStax ──────────────────────────────────────────────────────────────────

class OpenStaxDownloader(DownloaderBase):
    """Download free textbooks from OpenStax.

    OpenStax provides free, peer-reviewed textbooks in PDF and web formats.
    All content is under CC-BY license.
    """

    BASE_URL = "https://openstax.org"

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        subjects = self.config.extra.get("subjects", ["math", "science", "business"])

        downloaded = 0
        for subject in subjects:
            try:
                count = self._download_subject(subject)
                downloaded += count
                logger.info("[openstax] Subject '%s': %d books", subject, count)
            except Exception as exc:
                logger.error("[openstax] Subject '%s' failed: %s", subject, exc)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _download_subject(self, subject: str) -> int:
        """Download all books for a subject."""
        url = f"{self.BASE_URL}/subjects/{subject}"
        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        books = []
        for link in soup.find_all("a", href=re.compile(r"/details/books/")):
            href = link.get("href", "")
            if href and href not in [b["href"] for b in books]:
                title = link.get_text(strip=True)
                books.append({"href": href, "title": title})

        downloaded = 0
        for book in books:
            book_id = book["href"].split("/")[-1]
            if self.progress.is_file_done(f"openstax_{book_id}"):
                continue

            try:
                self._download_book(book)
                downloaded += 1
            except Exception as exc:
                logger.warning("[openstax] Book %s failed: %s", book_id, exc)
            time.sleep(1)

        return downloaded

    def _download_book(self, book: dict) -> None:
        """Download a single OpenStax book."""
        book_id = book["href"].split("/")[-1]
        url = f"{self.BASE_URL}{book['href']}"

        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find PDF link
        pdf_link = None
        for a in soup.find_all("a", href=True):
            if ".pdf" in a["href"].lower():
                pdf_link = urljoin(url, a["href"])
                break

        # Also try to get the web content
        content_sections = soup.find_all("section")
        web_content = "\n\n".join(
            html_to_markdown(str(sec)) for sec in content_sections[:20]
        )

        safe_title = re.sub(r'[^\w\s-]', '', book.get("title", book_id))[:60].strip()
        filename = f"doc_{book_id}_{safe_title}.md"

        content = f"# {book.get('title', book_id)}\n\n"
        content += f"**Source:** OpenStax\n**URL:** {url}\n"
        if pdf_link:
            content += f"**PDF:** {pdf_link}\n"
        content += f"\n---\n\n{web_content}"

        self.save_text(filename, content, metadata={
            "source": "OpenStax",
            "book_id": book_id,
            "title": book.get("title", ""),
            "pdf_url": pdf_link,
        })
        self.progress.mark_file_done(f"openstax_{book_id}", filename, len(content))


# ── Standard Ebooks ───────────────────────────────────────────────────────────

class StandardEbooksDownloader(DownloaderBase):
    """Download high-quality public domain ebooks from Standard Ebooks."""

    BASE_URL = "https://standardebooks.org"

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        max_books = self.config.extra.get("max_books", 1000)

        downloaded = 0
        page = 1

        while downloaded < max_books:
            url = f"{self.BASE_URL}/ebooks/?page={page}"
            try:
                resp = self.fetch(url)
                soup = BeautifulSoup(resp.text, "html.parser")
                books = soup.find_all("li", class_="ebook")

                if not books:
                    break

                for book in books:
                    if downloaded >= max_books:
                        break

                    link = book.find("a", href=re.compile(r"/ebooks/[^/]+"))
                    if not link:
                        continue

                    book_href = link.get("href", "")
                    book_id = book_href.strip("/").split("/")[-1]

                    if self.progress.is_file_done(f"se_{book_id}"):
                        continue

                    try:
                        self._download_book(book_href, book_id)
                        downloaded += 1
                    except Exception as exc:
                        logger.warning("[se] Book %s failed: %s", book_id, exc)

                    time.sleep(0.5)

                page += 1
                time.sleep(1)
            except Exception as exc:
                logger.error("[se] Page %d failed: %s", page, exc)
                break

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _download_book(self, href: str, book_id: str) -> None:
        """Download a Standard Ebooks entry."""
        url = f"{self.BASE_URL}{href}"
        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Get metadata
        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else book_id

        author_elem = soup.find("p", class_="author")
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"

        # Get description
        desc_elem = soup.find("article", id="description")
        description = html_to_markdown(str(desc_elem)) if desc_elem else ""

        # Get plain text link
        text_url = f"{self.BASE_URL}{href}/text/plain-text"
        try:
            text_resp = self.fetch(text_url)
            full_text = text_resp.text
        except Exception:
            full_text = description

        safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip()
        filename = f"doc_{book_id}_{safe_title}.md"

        content = f"# {title}\n\n"
        content += f"**Author:** {author}\n"
        content += f"**Source:** Standard Ebooks\n"
        content += f"**URL:** {url}\n\n---\n\n"
        content += full_text

        self.save_text(filename, content, metadata={
            "source": "Standard Ebooks",
            "book_id": book_id,
            "title": title,
            "author": author,
        })
        self.progress.mark_file_done(f"se_{book_id}", filename, len(content))


# ── Chinese Text Project ──────────────────────────────────────────────────────

class ChineseTextDownloader(DownloaderBase):
    """Download Chinese classics from Chinese Text Project (ctext.org)."""

    BASE_URL = "https://ctext.org"

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        max_texts = self.config.extra.get("max_texts", 2000)

        downloaded = 0
        # Start from the main texts page
        url = f"{self.BASE_URL}/texts-zhs"
        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find all text links
        text_links = []
        for a in soup.find_all("a", href=re.compile(r"/[^/]+/zhs$")):
            href = a.get("href", "")
            if href and href not in [t["href"] for t in text_links]:
                text_links.append({"href": href, "title": a.get_text(strip=True)})

        logger.info("[ctext] Found %d texts", len(text_links))

        for text in text_links[:max_texts]:
            text_id = text["href"].strip("/").split("/")[0]
            if self.progress.is_file_done(f"ctext_{text_id}"):
                continue

            try:
                self._download_text(text)
                downloaded += 1
                if downloaded % 100 == 0:
                    logger.info("[ctext] Downloaded %d texts", downloaded)
            except Exception as exc:
                logger.warning("[ctext] Text %s failed: %s", text_id, exc)
            time.sleep(0.5)

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _download_text(self, text: dict) -> None:
        """Download a single Chinese classic."""
        url = f"{self.BASE_URL}{text['href']}"
        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract text content
        content_div = soup.find("div", class_="ctext") or soup.find("div", id="content")
        if content_div:
            paragraphs = content_div.find_all("p")
            text_content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            text_content = soup.get_text(separator="\n\n", strip=True)

        text_id = text["href"].strip("/").split("/")[0]
        safe_title = re.sub(r'[^\w\s-]', '', text.get("title", text_id))[:60].strip()
        filename = f"doc_{text_id}_{safe_title}.md"

        content = f"# {text.get('title', text_id)}\n\n"
        content += f"**Source:** Chinese Text Project\n"
        content += f"**URL:** {url}\n\n---\n\n{text_content}"

        self.save_text(filename, content, metadata={
            "source": "Chinese Text Project",
            "text_id": text_id,
            "title": text.get("title", ""),
        })
        self.progress.mark_file_done(f"ctext_{text_id}", filename, len(content))


# ── ManyBooks ─────────────────────────────────────────────────────────────────

class ManyBooksDownloader(DownloaderBase):
    """Download free ebooks from ManyBooks.net."""

    BASE_URL = "https://manybooks.net"

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        max_books = self.config.extra.get("max_books", 2000)

        downloaded = 0
        page = 1

        while downloaded < max_books:
            url = f"{self.BASE_URL}/search-book?field_genre[value]=All&page={page}"
            try:
                resp = self.fetch(url)
                soup = BeautifulSoup(resp.text, "html.parser")
                books = soup.find_all("div", class_="book")

                if not books:
                    break

                for book in books:
                    if downloaded >= max_books:
                        break

                    link = book.find("a", href=re.compile(r"/titles/[^/]+"))
                    if not link:
                        continue

                    book_href = link.get("href", "")
                    book_id = book_href.split("/")[-1]

                    if self.progress.is_file_done(f"mb_{book_id}"):
                        continue

                    try:
                        self._download_book(book_href, book_id)
                        downloaded += 1
                    except Exception as exc:
                        logger.warning("[manybooks] Book %s failed: %s", book_id, exc)

                    time.sleep(0.3)

                page += 1
                time.sleep(1)
            except Exception as exc:
                logger.error("[manybooks] Page %d failed: %s", page, exc)
                break

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded}

    def _download_book(self, href: str, book_id: str) -> None:
        """Download a ManyBooks entry."""
        url = f"{self.BASE_URL}{href}"
        resp = self.fetch(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        title_elem = soup.find("h1")
        title = title_elem.get_text(strip=True) if title_elem else book_id

        author_elem = soup.find("div", class_="field-author")
        author = author_elem.get_text(strip=True) if author_elem else "Unknown"

        desc_elem = soup.find("div", class_="field-body")
        description = html_to_markdown(str(desc_elem)) if desc_elem else ""

        safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip()
        filename = f"doc_{book_id}_{safe_title}.md"

        content = f"# {title}\n\n"
        content += f"**Author:** {author}\n"
        content += f"**Source:** ManyBooks.net\n"
        content += f"**URL:** {url}\n\n---\n\n{description}"

        self.save_text(filename, content, metadata={
            "source": "ManyBooks",
            "book_id": book_id,
            "title": title,
            "author": author,
        })
        self.progress.mark_file_done(f"mb_{book_id}", filename, len(content))


# ── Dispatcher ────────────────────────────────────────────────────────────────

DOWNLOADER_MAP = {
    "kb_062": GutenbergDownloader,
    "kb_063": GutenbergDownloader,
    "kb_064": OpenStaxDownloader,
    "kb_067": ManyBooksDownloader,
    "kb_068": GutenbergDownloader,  # LibriVox uses Gutenberg texts
    "kb_069": StandardEbooksDownloader,
    "kb_091": ChineseTextDownloader,
}


def get_downloader(config) -> DownloaderBase:
    """Get the appropriate downloader for a book KB."""
    dl_class = DOWNLOADER_MAP.get(config.kb_id)
    if dl_class is None:
        # Default to Gutenberg for unknown book KBs
        dl_class = GutenbergDownloader
    return dl_class(config)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_books.py <kb_id>")
        print("Examples: kb_062 (Gutenberg EN), kb_063 (Gutenberg ZH), kb_064 (OpenStax)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    dl = get_downloader(config)
    with dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
