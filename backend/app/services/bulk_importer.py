"""Bulk import pipeline for knowledge base expansion.

Scans a directory tree, chunks documents, calls external embedding API,
and writes to PostgreSQL + Qdrant.

Features:
  - Resume from checkpoint (JSON progress file)
  - Incremental detection (file content hash)
  - Rate-limited embedding (respects 5 QPS external API)
  - Error retry with exponential backoff
  - Dual-write: PostgreSQL metadata + Qdrant vectors

Directory structure expected:
  kb_sources/
    kb_001_政府工作报告/
      metadata.json      # {"name": "...", "kb_type": "policy", "source_keys": [...]}
      doc_001.md         # document content
      doc_002.txt
    kb_002_统计数据/
      metadata.json
      ...

Usage:
  from app.services.bulk_importer import BulkImporter
  importer = BulkImporter()
  await importer.run("./data/kb_sources")
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.knowledge_base import KnowledgeBase, KBDocument, KBChunk

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────

CHUNK_SIZE = settings.rag_chunk_size        # 2000 chars
CHUNK_OVERLAP = settings.rag_chunk_overlap  # 200 chars
EMBED_BATCH_SIZE = settings.embed_batch_size  # 64
EMBED_MAX_RETRIES = settings.embed_max_retries  # 3
EMBED_RETRY_DELAY = settings.embed_retry_delay  # 2.0s
EMBED_TIMEOUT = settings.embed_request_timeout  # 60s
EMBED_QPS_LIMIT = getattr(settings, "embed_qps_limit", 20)  # configurable, default 20


# ── Sentence-boundary chunking ──────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[。！？\.\!\?])\s*")


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks respecting sentence boundaries."""
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]
    if not sentences:
        return []

    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 <= chunk_size:
            current = f"{current}{sent}" if not current else f"{current} {sent}"
        else:
            if current:
                chunks.append(current)
            # Start new chunk with overlap from previous chunk's tail
            if chunks and overlap > 0:
                prev = chunks[-1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                current = overlap_text + sent
            else:
                current = sent

    if current:
        chunks.append(current)

    return chunks


# ── Embedding client ────────────────────────────────────────────────────────

class EmbeddingClient:
    """Rate-limited OpenAI-compatible embedding client."""

    def __init__(self) -> None:
        self.base_url = settings.embed_base_url or settings.default_llm_base_url
        self.api_key = settings.embed_api_key or settings.default_llm_api_key
        self.model = settings.embed_model  # bge-m3
        self.semaphore = asyncio.Semaphore(EMBED_QPS_LIMIT)
        self.client = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=httpx.Timeout(EMBED_TIMEOUT),
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts with rate limiting and retry."""
        async with self.semaphore:
            for attempt in range(EMBED_MAX_RETRIES):
                try:
                    resp = await self.client.post(
                        "/v1/embeddings",
                        json={
                            "model": self.model,
                            "input": texts,
                            "encoding_format": "float",
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    embeddings = sorted(data["data"], key=lambda x: x["index"])
                    return [e["embedding"] for e in embeddings]
                except Exception as exc:
                    wait = EMBED_RETRY_DELAY * (2 ** attempt)
                    logger.warning(
                        "[embed] Attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, EMBED_MAX_RETRIES, exc, wait,
                    )
                    if attempt < EMBED_MAX_RETRIES - 1:
                        await asyncio.sleep(wait)
                    else:
                        raise

        raise RuntimeError("embed should not reach here")  # pragma: no cover

    async def close(self) -> None:
        await self.client.aclose()


# ── Progress tracker ────────────────────────────────────────────────────────

class ProgressTracker:
    """Persistent progress tracking for resume capability."""

    def __init__(self, path: str = "./data/bulk_import_progress.json") -> None:
        self.path = Path(path)
        self.data: dict[str, Any] = {"version": 1, "files": {}, "chunks_ingested": 0}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as exc:
                logger.warning("[progress] Failed to load progress file: %s", exc)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_file_done(self, file_path: str, content_hash: str) -> bool:
        entry = self.data["files"].get(file_path)
        return entry is not None and entry.get("hash") == content_hash

    def mark_file_done(self, file_path: str, content_hash: str, chunk_count: int) -> None:
        self.data["files"][file_path] = {
            "hash": content_hash,
            "chunk_count": chunk_count,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        self.data["chunks_ingested"] += chunk_count
        self.save()

    def stats(self) -> dict[str, Any]:
        files = self.data["files"]
        return {
            "files_processed": len(files),
            "chunks_ingested": self.data.get("chunks_ingested", 0),
            "last_updated": max(
                (f.get("ingested_at", "") for f in files.values()), default="",
            ),
        }


# ── Bulk Importer ───────────────────────────────────────────────────────────

class BulkImporter:
    """Orchestrates the full import pipeline."""

    def __init__(
        self,
        progress_path: str = "./data/bulk_import_progress.json",
        db_session_factory = async_session,
    ) -> None:
        self.progress = ProgressTracker(progress_path)
        self.db_session_factory = db_session_factory
        self.embed_client = EmbeddingClient()
        self._qdrant_store: Any | None = None

    async def _get_qdrant(self):
        """Lazy-load Qdrant store."""
        if self._qdrant_store is None:
            from app.services.qdrant_store import get_qdrant_store
            self._qdrant_store = get_qdrant_store()
        return self._qdrant_store

    async def run(self, source_dir: str | Path, max_workers: int = 4) -> dict[str, Any]:
        """Run the full import pipeline over source_dir with parallel KB processing."""
        source_dir = Path(source_dir)
        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        kb_dirs = [d for d in source_dir.iterdir() if d.is_dir()]
        logger.info("[importer] Found %d knowledge base directories (workers=%d)", len(kb_dirs), max_workers)

        total_files = 0
        total_chunks = 0
        start_time = time.time()
        sem = asyncio.Semaphore(max_workers)

        async def _process_one(kb_dir: Path) -> tuple[int, int]:
            async with sem:
                kb_name = kb_dir.name
                logger.info("[importer] Processing KB: %s", kb_name)
                try:
                    return await self._process_kb(kb_dir)
                except Exception as exc:
                    logger.error("[importer] Failed to process KB %s: %s", kb_name, exc, exc_info=True)
                    return 0, 0

        results = await asyncio.gather(*[_process_one(d) for d in sorted(kb_dirs)])
        for files_processed, chunks_ingested in results:
            total_files += files_processed
            total_chunks += chunks_ingested

        await self.embed_client.close()

        elapsed = time.time() - start_time
        logger.info(
            "[importer] Done. Files: %d, Chunks: %d, Time: %.1fs",
            total_files, total_chunks, elapsed,
        )
        return {
            "kb_count": len(kb_dirs),
            "files_processed": total_files,
            "chunks_ingested": total_chunks,
            "elapsed_seconds": elapsed,
        }

    async def _process_kb(self, kb_dir: Path) -> tuple[int, int]:
        """Process a single knowledge base directory."""
        # Load metadata
        meta_path = kb_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        else:
            metadata = {
                "name": kb_dir.name,
                "kb_type": "general",
                "source_keys": [],
                "description": "",
            }

        # Find all document files
        doc_files = sorted(
            f for f in kb_dir.iterdir()
            if f.is_file() and f.suffix.lower() in (".md", ".txt", ".markdown")
        )

        files_processed = 0
        chunks_ingested = 0

        # db session must span all document processing for this KB
        async with self.db_session_factory() as db:
            kb = await self._get_or_create_kb(db, metadata)
            kb_id = kb.id

            for doc_file in doc_files:
                try:
                    file_chunks = await self._process_document(db, kb_id, doc_file)
                    files_processed += 1
                    chunks_ingested += file_chunks
                except Exception as exc:
                    logger.error(
                        "[importer] Failed to process document %s: %s", doc_file.name, exc,
                    )

        return files_processed, chunks_ingested

    async def _get_or_create_kb(
        self, db: AsyncSession, metadata: dict[str, Any]
    ) -> KnowledgeBase:
        """Get existing KB or create new one."""
        name = metadata.get("name", "Untitled")
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == name))
        kb = result.scalar_one_or_none()

        if kb is None:
            kb = KnowledgeBase(
                name=name,
                description=metadata.get("description", ""),
                kb_type=metadata.get("kb_type", "general"),
                scope="corp",
                embed_model=settings.embed_model,
            )
            db.add(kb)
            await db.commit()
            await db.refresh(kb)
            logger.info("[importer] Created KB '%s' (id=%d)", name, kb.id)
        else:
            logger.info("[importer] Using existing KB '%s' (id=%d)", name, kb.id)

        return kb

    async def _process_document(self, db: AsyncSession, kb_id: int, doc_file: Path) -> int:
        """Process a single document file. Returns chunk count."""
        content = doc_file.read_text(encoding="utf-8")
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        file_path = str(doc_file.resolve())

        # Check if already processed (incremental)
        if self.progress.is_file_done(file_path, content_hash):
            logger.debug("[importer] Skipping already-ingested file: %s", doc_file.name)
            return 0

        # Chunk the content
        chunks = _chunk_text(content)
        if not chunks:
            logger.warning("[importer] No chunks extracted from %s", doc_file.name)
            return 0

        # Create document record
        doc = KBDocument(
            kb_id=kb_id,
            title=doc_file.stem,
            file_type=doc_file.suffix.lstrip("."),
            file_size=len(content.encode("utf-8")),
            content_preview=content[:500],
            chunk_count=len(chunks),
            status="indexed",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # Embed chunks in batches
        qdrant = await self._get_qdrant()
        all_embeddings: list[list[float]] = []
        for i in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch = chunks[i : i + EMBED_BATCH_SIZE]
            embeddings = await self.embed_client.embed(batch)
            all_embeddings.extend(embeddings)

        # Prepare chunk records and Qdrant points
        chunk_records: list[KBChunk] = []
        qdrant_points: list[dict[str, Any]] = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
            chunk_id = int(hashlib.md5(f"{kb_id}_{doc.id}_{idx}".encode()).hexdigest()[:16], 16)
            chunk_records.append(
                KBChunk(
                    kb_id=kb_id,
                    doc_id=doc.id,
                    content=chunk_text,
                    chunk_index=idx,
                    embedding_json=json.dumps(embedding),
                )
            )
            qdrant_points.append({
                "id": chunk_id,
                "vector": embedding,
                "kb_id": kb_id,
                "doc_id": doc.id,
                "content": chunk_text,
                "chunk_index": idx,
            })

        # Write to PostgreSQL
        db.add_all(chunk_records)
        await db.commit()

        # Write to Qdrant (run sync method in thread pool to avoid blocking)
        await asyncio.to_thread(qdrant.upsert_chunks, qdrant_points)

        # Update KB stats
        kb = await db.get(KnowledgeBase, kb_id)
        if kb:
            kb.doc_count = (kb.doc_count or 0) + 1
            kb.chunk_count = (kb.chunk_count or 0) + len(chunks)
            kb.total_size = (kb.total_size or 0) + doc.file_size
            kb.updated_at = datetime.now(timezone.utc)
            await db.commit()

        # Mark progress
        self.progress.mark_file_done(file_path, content_hash, len(chunks))

        logger.info(
            "[importer] Ingested '%s' → %d chunks (KB=%d, Doc=%d)",
            doc_file.name, len(chunks), kb_id, doc.id,
        )
        return len(chunks)


# ── CLI 入口 ─────────────────────────────────────────────────────────────────
# 用法:
#   python -m app.services.bulk_importer --source ./data/kb_sources
#   python -m app.services.bulk_importer --source ./data/kb_sources --progress ./data/bulk_import_progress.json
def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="DataAgent 批量入库：扫描 kb_sources/ 目录树 → 分块 → BGE-M3 embedding → PostgreSQL + Qdrant"
    )
    parser.add_argument(
        "--source", default=str(settings.kb_data_path),
        help="语料源目录（kb_sources/，默认取 settings.kb_data_path）",
    )
    parser.add_argument(
        "--progress", default="./data/bulk_import_progress.json",
        help="断点续传进度文件路径",
    )
    parser.add_argument(
        "--workers", type=int, default=4,
        help="并发处理 KB 数量（默认 4）",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    async def _run() -> None:
        importer = BulkImporter(progress_path=args.progress)
        summary = await importer.run(args.source, max_workers=args.workers)
        print("\n" + "=" * 50)
        print(f"入库完成：")
        print(f"  知识库目录: {summary['kb_count']}")
        print(f"  处理文档:   {summary['files_processed']}")
        print(f"  写入切片:   {summary['chunks_ingested']}")
        print(f"  耗时:       {summary['elapsed_seconds']:.0f}s")
        print("=" * 50)

    asyncio.run(_run())


if __name__ == "__main__":
    _main()
