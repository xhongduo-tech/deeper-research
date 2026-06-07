"""RSS news downloader — 财经/科技/政治新闻聚合.

Fetches RSS feeds and converts entries to Markdown documents.
Requires: feedparser

Usage:
    python download_rss.py kb_012   # 财经新闻
    python download_rss.py kb_013   # 科技新闻
"""
from __future__ import annotations

import hashlib
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from base import DownloaderBase, html_to_markdown
from config_v2 import get_source_by_id

logger = logging.getLogger("data_collection.rss")

try:
    import feedparser
    _FEEDPARSER_AVAILABLE = True
except ImportError:
    _FEEDPARSER_AVAILABLE = False
    logger.warning("feedparser not installed. RSS downloads unavailable. "
                   "Install: pip install feedparser")


class RSSDownloader(DownloaderBase):
    """Download news articles from RSS feeds."""

    def run(self) -> dict[str, Any]:
        self.write_metadata()
        rss_urls = self.config.extra.get("rss_urls", [])
        if not rss_urls:
            logger.error("[rss] No RSS URLs configured for %s", self.kb_id)
            return {"kb_id": self.kb_id, "downloaded": 0, "error": "No RSS URLs"}

        if not _FEEDPARSER_AVAILABLE:
            return {"kb_id": self.kb_id, "downloaded": 0, "error": "feedparser not installed"}

        downloaded = 0
        for feed_url in rss_urls:
            try:
                count = self._process_feed(feed_url)
                downloaded += count
            except Exception as exc:
                logger.error("[rss] Feed failed %s: %s", feed_url, exc)
                self.progress.log_error(feed_url, str(exc))

        self.progress.mark_complete()
        return {"kb_id": self.kb_id, "downloaded": downloaded, "feeds": len(rss_urls)}

    def _process_feed(self, feed_url: str) -> int:
        """Process a single RSS feed. Returns count of new articles."""
        logger.info("[rss] Fetching feed: %s", feed_url)

        # feedparser can fetch directly, but let's use our session for consistency
        resp = self.fetch(feed_url)
        feed = feedparser.parse(resp.content)

        if feed.bozo and hasattr(feed, "bozo_exception"):
            logger.warning("[rss] Feed parse warning: %s", feed.bozo_exception)

        downloaded = 0
        for entry in feed.entries:
            link = entry.get("link", "")
            if not link or self.progress.is_file_done(link):
                continue

            title = entry.get("title", "Untitled").strip()
            published = entry.get("published", entry.get("updated", ""))
            summary = entry.get("summary", entry.get("description", ""))

            # Try to fetch full article content
            content = summary
            try:
                article_resp = self.fetch(link)
                content = html_to_markdown(article_resp.text)
                if len(content) < len(summary):
                    content = summary
            except Exception:
                pass  # Use summary as fallback

            # Generate safe filename
            url_hash = hashlib.md5(link.encode()).hexdigest()[:8]
            safe_title = "".join(c if c.isalnum() or c in "_- " else "_" for c in title)[:40]
            filename = f"doc_{url_hash}_{safe_title}.md"

            md_content = f"""# {title}

**Source:** {feed_url}
**Published:** {published}
**URL:** {link}

{content}
"""
            self.save_text(filename, md_content, metadata={
                "title": title,
                "published": published,
                "source_url": link,
                "feed_url": feed_url,
            })
            self.progress.mark_file_done(link, str(self.output_dir / filename), len(md_content))
            downloaded += 1

        logger.info("[rss] Feed %s: %d new articles", feed_url, downloaded)
        return downloaded


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python download_rss.py <kb_id>")
        print("Examples: kb_012 (财经新闻), kb_013 (科技新闻), kb_014 (政治时事)")
        sys.exit(1)

    kb_id = sys.argv[1]
    config = get_source_by_id(kb_id)
    if not config:
        print(f"Unknown KB: {kb_id}")
        sys.exit(1)

    with RSSDownloader(config) as dl:
        result = dl.run()
        print(result)


if __name__ == "__main__":
    main()
