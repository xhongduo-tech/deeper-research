"""Wikipedia dump downloader — massive free text corpus.

Downloads Wikipedia XML dumps and converts them to chunked Markdown.
Chinese dump: ~3GB compressed, ~10GB text
English dump: ~20GB compressed, ~80GB text

Usage:
    python download_wikipedia.py kb_086   # Chinese Wikipedia
    python download_wikipedia.py kb_087   # English Wikipedia
"""
from __future__ import annotations

import bz2
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from base import DownloaderBase
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.wikipedia")

# Chunk size for splitting large articles
CHUNK_SIZE = 8000
MAX_ARTICLES = 1000000  # Safety limit


class WikipediaDownloader(DownloaderBase):
    """Download and process Wikipedia XML dumps."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()

        dump_url = self.config.extra.get("dump_url_pattern")
        if not dump_url:
            # Try to construct from known patterns
            if "zhwiki" in self.kb_id:
                dump_url = "https://dumps.wikimedia.org/zhwiki/latest/zhwiki-latest-pages-articles.xml.bz2"
            elif "enwiki" in self.kb_id:
                dump_url = "https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2"
            else:
                raise ValueError("No dump URL configured")

        logger.info("[wikipedia] Dump URL: %s", dump_url)

        # Download the dump file
        dump_path = self._download_dump(dump_url)
        if not dump_path:
            return {"kb_id": self.kb_id, "error": "Failed to download dump"}

        # Process the XML
        articles = self._process_dump(dump_path)

        self.progress.mark_complete()
        return {
            "kb_id": self.kb_id,
            "articles_processed": articles,
            "dump_file": str(dump_path),
        }

    def _download_dump(self, url: str) -> Path | None:
        """Download the bz2 dump file."""
        filename = Path(urlparse(url).path).name
        dump_path = self.output_dir / filename

        if dump_path.exists() and dump_path.stat().st_size > 1000000:
            logger.info("[wikipedia] Using existing dump: %s (%s MB)",
                       dump_path, dump_path.stat().st_size // 1024 // 1024)
            return dump_path

        logger.info("[wikipedia] Downloading dump... (this may take a while)")

        try:
            with self.session.stream("GET", url, timeout=httpx.Timeout(600.0)) as resp:
                resp.raise_for_status()
                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(dump_path, "wb") as f:
                    for chunk in resp.iter_bytes(chunk_size=8192 * 16):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0 and downloaded % (50 * 1024 * 1024) == 0:
                            pct = downloaded / total_size * 100
                            logger.info("[wikipedia] Downloaded: %.1f%% (%d MB / %d MB)",
                                       pct, downloaded // 1024 // 1024, total_size // 1024 // 1024)

            logger.info("[wikipedia] Download complete: %s MB", dump_path.stat().st_size // 1024 // 1024)
            return dump_path
        except Exception as exc:
            logger.error("[wikipedia] Download failed: %s", exc)
            if dump_path.exists():
                dump_path.unlink()
            return None

    def _process_dump(self, dump_path: Path) -> int:
        """Process the bz2 XML dump and convert articles to Markdown."""
        logger.info("[wikipedia] Processing dump (this may take a while)...")

        articles = 0
        skipped = 0
        doc_counter = 0

        # Open bz2 file
        with bz2.open(dump_path, "rt", encoding="utf-8", errors="ignore") as f:
            # Use iterparse to handle large files
            context = ET.iterparse(f, events=("start", "end"))
            context = iter(context)
            event, root = next(context)

            # Detect namespace from root element, e.g. {http://...}mediawiki
            namespace = ""
            if root.tag.startswith("{"):
                namespace = root.tag.split("}")[0][1:]
                logger.info("[wikipedia] Detected namespace: %s", namespace)

            ns_prefix = f"{{{namespace}}}" if namespace else ""

            current_page = {}
            in_page = False
            current_tag = None

            for event, elem in context:
                tag = elem.tag.replace(ns_prefix, "")

                if event == "start":
                    if tag == "page":
                        in_page = True
                        current_page = {}
                    current_tag = tag

                elif event == "end":
                    if tag == "title":
                        current_page["title"] = elem.text or ""
                    elif tag == "text":
                        current_page["text"] = elem.text or ""
                    elif tag == "page":
                        # Process completed page
                        if self._is_valid_article(current_page):
                            try:
                                chunks = self._article_to_chunks(current_page)
                                for i, chunk in enumerate(chunks):
                                    doc_counter += 1
                                    filename = f"doc_{doc_counter:06d}.md"
                                    self.save_text(filename, chunk, metadata={
                                        "title": current_page.get("title", ""),
                                        "source": "Wikipedia",
                                        "chunk_index": i,
                                        "total_chunks": len(chunks),
                                    })
                                articles += 1
                                if articles % 1000 == 0:
                                    logger.info("[wikipedia] Processed %d articles (%d chunks)", articles, doc_counter)
                            except Exception as exc:
                                logger.warning("[wikipedia] Article failed: %s", exc)
                                skipped += 1
                        else:
                            skipped += 1

                        in_page = False
                        current_page = {}

                        # Clear element to save memory
                        root.clear()

                        if articles >= MAX_ARTICLES:
                            logger.info("[wikipedia] Reached max articles limit")
                            break

        logger.info("[wikipedia] Done: %d articles, %d chunks, %d skipped", articles, doc_counter, skipped)
        return articles

    def _is_valid_article(self, page: dict) -> bool:
        """Check if a page is a valid article (not redirect, template, etc.)."""
        title = page.get("title", "")
        text = page.get("text", "")

        if not title or not text:
            return False

        # Skip special pages
        if any(title.startswith(p) for p in ["File:", "Template:", "Category:", "Wikipedia:",
                                               "Portal:", "Draft:", "Module:", "MediaWiki:",
                                               "Help:", "Talk:", "User:", "Special:"]):
            return False

        # Skip very short articles
        if len(text) < 200:
            return False

        # Skip redirects
        if text.strip().startswith("#REDIRECT") or text.strip().startswith("#重定向"):
            return False

        return True

    def _article_to_chunks(self, page: dict) -> list[str]:
        """Convert wiki markup to Markdown and split into chunks."""
        title = page.get("title", "")
        text = page.get("text", "")

        # Basic wiki to markdown conversion
        md = self._wikitext_to_markdown(text)

        # Split into chunks
        chunks = []
        current_chunk = f"# {title}\n\n"

        for paragraph in md.split("\n\n"):
            if len(current_chunk) + len(paragraph) > CHUNK_SIZE:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"
            else:
                current_chunk += paragraph + "\n\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks if chunks else [f"# {title}\n\n{md}"]

    def _wikitext_to_markdown(self, text: str) -> str:
        """Convert basic wikitext to Markdown."""
        # Remove templates
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)

        # Convert headers
        text = re.sub(r"^====(.+?)====$", r"#### \1", text, flags=re.MULTILINE)
        text = re.sub(r"^===(.+?)===$", r"### \1", text, flags=re.MULTILINE)
        text = re.sub(r"^==(.+?)==$", r"## \1", text, flags=re.MULTILINE)
        text = re.sub(r"^=(.+?)=$", r"# \1", text, flags=re.MULTILINE)

        # Convert bold/italic
        text = re.sub(r"'''(.+?)'''", r"**\1**", text)
        text = re.sub(r"''(.+?)''", r"*\1*", text)

        # Convert links [[target|text]] → [text](target)
        def link_repl(match):
            parts = match.group(1).split("|", 1)
            if len(parts) == 2:
                target, label = parts
            else:
                target = label = parts[0]
            return f"[{label}](https://zh.wikipedia.org/wiki/{target.replace(' ', '_')})"

        text = re.sub(r"\[\[(.+?)\]\]", link_repl, text)

        # Remove remaining wiki markup
        text = re.sub(r"\[https?://[^\s\]]+\s+([^\]]+)\]", r"[\1](url)", text)
        text = re.sub(r"\[https?://[^\s\]]+\]", "", text)
        text = re.sub(r"\[\w+:[^\]]+\]", "", text)

        # Remove HTML comments
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

        # Clean up
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_wikipedia.py <kb_id>")
        print("Examples: kb_086 (Chinese), kb_087 (English)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with WikipediaDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
