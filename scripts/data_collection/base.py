"""Base downloader framework with retry, progress tracking, and HTML→Markdown.

Usage:
    from base import DownloaderBase

    class MyDownloader(DownloaderBase):
        def run(self):
            ...

    dl = MyDownloader(config)
    dl.run()
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# Optional: html → markdown conversion
try:
    import markdownify
    _MARKDOWNIFY_AVAILABLE = True
except ImportError:
    _MARKDOWNIFY_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except ImportError:
    _BS4_AVAILABLE = False

logger = logging.getLogger("data_collection")

# ── HTTP defaults ───────────────────────────────────────────────────────────

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


# ── Retry decorator ─────────────────────────────────────────────────────────

def with_retry(max_retries: int = 3, backoff: float = 2.0, exceptions=(Exception,)):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    wait = backoff * (2 ** attempt) + random.uniform(0, 1)
                    if attempt < max_retries - 1:
                        logger.warning("[retry] %s failed (attempt %d/%d): %s, retry in %.1fs",
                                       fn.__name__, attempt + 1, max_retries, exc, wait)
                        time.sleep(wait)
                    else:
                        logger.error("[retry] %s failed after %d attempts: %s",
                                     fn.__name__, max_retries, exc)
                        raise
        return wrapper
    return decorator


# ── Progress tracker ────────────────────────────────────────────────────────

class ProgressTracker:
    """Persistent progress tracking per knowledge base."""

    def __init__(self, kb_id: str, base_dir: str = "./data/download_progress") -> None:
        self.kb_id = kb_id
        self.path = Path(base_dir) / f"{kb_id}.json"
        self.data: dict[str, Any] = {
            "kb_id": kb_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed": False,
            "files": {},
            "errors": [],
        }
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as exc:
                logger.warning("[progress] Failed to load %s: %s", self.path, exc)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_file_done(self, url: str) -> bool:
        return url in self.data["files"]

    def mark_file_done(self, url: str, local_path: str, size: int = 0) -> None:
        self.data["files"][url] = {
            "path": local_path,
            "size": size,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def log_error(self, url: str, error: str) -> None:
        self.data["errors"].append({
            "url": url,
            "error": str(error),
            "time": datetime.now(timezone.utc).isoformat(),
        })
        self.save()

    def mark_complete(self) -> None:
        self.data["completed"] = True
        self.data["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.save()

    def stats(self) -> dict[str, Any]:
        return {
            "kb_id": self.kb_id,
            "completed": self.data["completed"],
            "files_downloaded": len(self.data["files"]),
            "errors": len(self.data["errors"]),
            "last_updated": self.data.get("completed_at", self.data.get("started_at", "")),
        }


# ── HTML helpers ────────────────────────────────────────────────────────────

def html_to_markdown(html: str, base_url: str = "") -> str:
    """Convert HTML to clean Markdown text."""
    if _MARKDOWNIFY_AVAILABLE:
        md = markdownify.markdownify(html, heading_style="ATX", strip=["script", "style", "nav"])
        return md

    # Fallback: simple text extraction
    if _BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    # Last resort: regex strip tags
    text = re.sub(r"<[^>]+>", "", html)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes. Requires PyPDF2 or pdfplumber."""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    text_parts.append(txt)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                text_parts.append(txt)
        return "\n\n".join(text_parts)
    except ImportError:
        pass

    logger.warning("No PDF parser available. Install pdfplumber or PyPDF2.")
    return ""


from io import BytesIO


# ── Base Downloader ─────────────────────────────────────────────────────────

class DownloaderBase(ABC):
    """Abstract base for all KB downloaders."""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.kb_id = config.kb_id
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.progress = ProgressTracker(self.kb_id)
        self.session = httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    @with_retry(max_retries=3, backoff=2.0)
    def fetch(self, url: str, **kwargs) -> httpx.Response:
        """Fetch URL with retry and polite delay."""
        time.sleep(random.uniform(0.5, 2.0))  # polite delay
        resp = self.session.get(url, **kwargs)
        resp.raise_for_status()
        return resp

    def save_text(self, filename: str, content: str, metadata: dict | None = None) -> Path:
        """Save text content as Markdown with optional YAML frontmatter."""
        filepath = self.output_dir / filename
        if metadata:
            frontmatter = "---\n" + json.dumps(metadata, ensure_ascii=False, indent=2) + "\n---\n\n"
            content = frontmatter + content
        filepath.write_text(content, encoding="utf-8")
        return filepath

    def save_json(self, filename: str, data: dict | list) -> Path:
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filepath

    def save_bytes(self, filename: str, data: bytes) -> Path:
        filepath = self.output_dir / filename
        filepath.write_bytes(data)
        return filepath

    def write_metadata(self, extra: dict | None = None) -> Path:
        """Write metadata.json for the knowledge base."""
        meta = {
            "kb_id": self.kb_id,
            "name": self.config.name,
            "kb_type": self.config.kb_type,
            "description": self.config.description,
            "source_url": self.config.source_url,
            "time_range": self.config.time_range,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            meta.update(extra)
        return self.save_json("metadata.json", meta)

    @abstractmethod
    def run(self) -> dict[str, Any]:
        """Execute the download. Returns summary stats."""
        ...
