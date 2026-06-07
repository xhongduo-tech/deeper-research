#!/usr/bin/env python3
"""
WET (.warc.wet.gz) streaming embedder for worldview knowledge base.

Streams CommonCrawl WET files directly from data/worldview/L*/ without
writing intermediate files. Extracts conversion records, filters by quality,
chunks, embeds via Ollama bge-m3, and writes to SQLite + Qdrant.

Usage:
    python wet_bulk_embedder.py --layer-dir /Users/xuhongduo/Projects/deep-research/data/worldview/L7_multimodal/cc_image_text --workers 4
    python wet_bulk_embedder.py --layer-dir data/worldview/L9_uncertainty/commoncrawl_divergence --max-records 3000 --workers 3
"""
from __future__ import annotations

import asyncio
import gzip
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow importing from backend
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.knowledge_base import KnowledgeBase, KBDocument, KBChunk
from app.services.qdrant_store import get_qdrant_store

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────

CHUNK_SIZE = getattr(settings, "rag_chunk_size", 2000)
CHUNK_OVERLAP = getattr(settings, "rag_chunk_overlap", 200)
EMBED_BATCH_SIZE = int(os.environ.get("WET_EMBED_BATCH_SIZE", getattr(settings, "embed_batch_size", 512)))
EMBED_MAX_RETRIES = getattr(settings, "embed_max_retries", 3)
EMBED_RETRY_DELAY = getattr(settings, "embed_retry_delay", 2.0)
EMBED_TIMEOUT = float(os.environ.get("EMBED_REQUEST_TIMEOUT", getattr(settings, "embed_request_timeout", 360)))
EMBED_QPS_LIMIT = getattr(settings, "embed_qps_limit", 20)

# Simple quality filter defaults
MIN_RECORD_CHARS = 400
MAX_RECORD_CHARS = 8000
MAX_RECORDS_PER_FILE = 2000

_SENTENCE_RE = re.compile(r"(?<=[。！？\.\!\?])\s*")


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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
            if chunks and overlap > 0:
                prev = chunks[-1]
                overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                current = overlap_text + sent
            else:
                current = sent

    if current:
        chunks.append(current)
    return chunks


def _is_quality_record(text: str) -> bool:
    if not text:
        return False
    if len(text) < MIN_RECORD_CHARS or len(text) > MAX_RECORD_CHARS:
        return False
    # Require some word-like tokens
    if len(re.findall(r"[一-鿿]", text)) < 5 and len(re.findall(r"[a-zA-Z]{3,}", text)) < 3:
        return False
    return True


class EmbeddingClient:
    """Rate-limited OpenAI-compatible embedding client."""

    def __init__(self) -> None:
        import httpx
        base = (settings.embed_base_url or settings.default_llm_base_url or "http://localhost:11434").rstrip("/")
        # Avoid double /v1 if the base URL already includes it
        if base.endswith("/v1"):
            base = base[:-3]
        self.base_url = base
        self.api_key = settings.embed_api_key or settings.default_llm_api_key
        self.model = settings.embed_model
        self.semaphore = asyncio.Semaphore(EMBED_QPS_LIMIT)
        self.client = httpx.AsyncClient(
            base_url=self.base_url.rstrip("/"),
            timeout=httpx.Timeout(EMBED_TIMEOUT),
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
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
                    logger.warning("[embed] Attempt %d/%d failed (%s), retrying in %.1fs",
                                   attempt + 1, EMBED_MAX_RETRIES, exc, wait)
                    if attempt < EMBED_MAX_RETRIES - 1:
                        await asyncio.sleep(wait)
                    else:
                        raise
        raise RuntimeError("embed should not reach here")  # pragma: no cover

    async def close(self) -> None:
        await self.client.aclose()


class ProgressTracker:
    def __init__(self, path: str) -> None:
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
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def is_file_done(self, file_path: str, content_hash: str) -> bool:
        entry = self.data["files"].get(file_path)
        return entry is not None and entry.get("hash") == content_hash

    def mark_file_done(self, file_path: str, content_hash: str, chunk_count: int) -> None:
        self.data["files"][file_path] = {
            "hash": content_hash,
            "chunk_count": chunk_count,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        self.data["chunks_ingested"] = self.data.get("chunks_ingested", 0) + chunk_count
        self.save()

    def stats(self) -> dict[str, Any]:
        files = self.data["files"]
        return {
            "files_processed": len(files),
            "chunks_ingested": self.data.get("chunks_ingested", 0),
        }


async def _get_or_create_kb(db: AsyncSession, name: str, description: str, kb_type: str) -> KnowledgeBase:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == name))
    kb = result.scalar_one_or_none()
    if kb is None:
        kb = KnowledgeBase(
            name=name,
            description=description,
            kb_type=kb_type,
            scope="corp",
            embed_model=settings.embed_model,
        )
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        logger.info("[wet] Created KB '%s' (id=%d)", name, kb.id)
    return kb


async def _process_wet_file(
    db: AsyncSession,
    kb_id: int,
    wet_path: Path,
    embed_client: EmbeddingClient,
    max_records: int,
) -> tuple[int, int]:
    """Stream a single WET file, extract records, chunk, embed, store."""
    file_path = str(wet_path.resolve())
    content_hash = hashlib.sha256(wet_path.name.encode()).hexdigest()[:16]

    # Check doc-level duplicate by title (WET filename)
    result = await db.execute(
        select(KBDocument).where(KBDocument.kb_id == kb_id, KBDocument.title == wet_path.name)
    )
    if result.scalar_one_or_none():
        logger.debug("[wet] Skipping already-ingested WET: %s", wet_path.name)
        return 0, 0

    records: list[str] = []
    total_chars = 0
    try:
        with gzip.open(wet_path, "rt", encoding="utf-8", errors="ignore") as f:
            current: list[str] = []
            in_conversion = False
            header_done = False
            for line in f:
                line = line.rstrip("\n")
                if line.startswith("WARC/1.0"):
                    if current and in_conversion and header_done:
                        text = "\n".join(current).strip()
                        if _is_quality_record(text):
                            records.append(text)
                            total_chars += len(text)
                    current = []
                    in_conversion = False
                    header_done = False
                elif line.startswith("WARC-Type: conversion"):
                    in_conversion = True
                    current = []
                    header_done = False
                elif in_conversion and not header_done:
                    if line == "":
                        header_done = True
                        current = []
                    # else still in headers, skip
                elif in_conversion and header_done and not line.startswith("WARC-"):
                    current.append(line)

                if len(records) >= max_records:
                    break

            if current and in_conversion and header_done:
                text = "\n".join(current).strip()
                if _is_quality_record(text):
                    records.append(text)
                    total_chars += len(text)
    except Exception as exc:
        logger.error("[wet] Failed to parse %s: %s", wet_path.name, exc)
        return 0, 0

    if not records:
        logger.warning("[wet] No quality records in %s", wet_path.name)
        return 0, 0

    # Create one document per WET file
    doc = KBDocument(
        kb_id=kb_id,
        title=wet_path.name,
        file_type="warc.wet.gz",
        file_size=wet_path.stat().st_size,
        content_preview=records[0][:500] if records else "",
        chunk_count=0,  # updated later
        status="indexing",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Chunk all records
    all_chunks: list[str] = []
    for rec in records:
        all_chunks.extend(_chunk_text(rec))

    if not all_chunks:
        doc.status = "empty"
        await db.commit()
        return 0, 0

    # Embed in batches
    qdrant = get_qdrant_store()
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_chunks), EMBED_BATCH_SIZE):
        batch = all_chunks[i : i + EMBED_BATCH_SIZE]
        embeddings = await embed_client.embed(batch)
        all_embeddings.extend(embeddings)

    # Build chunk records and Qdrant points
    chunk_records: list[KBChunk] = []
    qdrant_points: list[dict[str, Any]] = []
    for idx, (chunk_text, embedding) in enumerate(zip(all_chunks, all_embeddings)):
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

    db.add_all(chunk_records)
    doc.status = "indexed"
    doc.chunk_count = len(all_chunks)
    await db.commit()

    await asyncio.to_thread(qdrant.upsert_chunks, qdrant_points)

    logger.info(
        "[wet] Ingested '%s' → %d records → %d chunks (KB=%d, Doc=%d)",
        wet_path.name, len(records), len(all_chunks), kb_id, doc.id,
    )
    return len(all_chunks), doc.file_size


async def _process_wet_file_wrapper(
    wet_path: Path,
    kb_id: int,
    embed_client: EmbeddingClient,
    max_records: int,
    progress: ProgressTracker,
    sem: asyncio.Semaphore,
) -> tuple[int, int]:
    async with sem:
        file_path = str(wet_path.resolve())
        content_hash = hashlib.sha256(wet_path.name.encode()).hexdigest()[:16]
        if progress.is_file_done(file_path, content_hash):
            return 0, 0

        try:
            async with async_session() as db:
                chunks, file_size = await _process_wet_file(db, kb_id, wet_path, embed_client, max_records)
                progress.mark_file_done(file_path, content_hash, chunks)
                return chunks, file_size
        except Exception as exc:
            logger.error("[wet] Failed WET file %s: %s", wet_path.name, exc, exc_info=True)
            return 0, 0


async def run_layer(
    layer_dir: str | Path,
    embed_client: EmbeddingClient,
    global_sem: asyncio.Semaphore,
    max_records: int = MAX_RECORDS_PER_FILE,
    progress_path: str | None = None,
    progress_suffix: str = "",
) -> dict[str, Any]:
    layer_dir = Path(layer_dir)
    if not layer_dir.exists():
        raise FileNotFoundError(f"Layer directory not found: {layer_dir}")

    layer_name = layer_dir.name
    parent_name = layer_dir.parent.name
    kb_name = f"{parent_name}_{layer_name}"
    kb_desc = f"Auto-ingested WET corpus for {parent_name}/{layer_name}"
    kb_type = "web_corpus"

    if progress_path is None:
        suffix = f"_{progress_suffix}" if progress_suffix else ""
        progress_path = f"/Users/xuhongduo/Projects/deep-research/data/wet_embed_progress_{kb_name}{suffix}.json"

    progress = ProgressTracker(progress_path)

    # Get or create KB once
    async with async_session() as db:
        kb = await _get_or_create_kb(db, kb_name, kb_desc, kb_type)
        kb_id = kb.id

    wet_files = sorted(layer_dir.rglob("*.warc.wet.gz"))
    logger.info("[wet] Found %d WET files in %s (KB=%d)", len(wet_files), layer_dir, kb_id)

    if not wet_files:
        return {"kb_id": kb_id, "files_found": 0, "chunks_ingested": 0}

    start_time = time.time()
    total_chunks = 0
    total_files = 0
    total_size = 0

    tasks = [_process_wet_file_wrapper(w, kb_id, embed_client, max_records, progress, global_sem) for w in wet_files]
    for coro in asyncio.as_completed(tasks):
        chunks, file_size = await coro
        total_chunks += chunks
        if chunks > 0:
            total_files += 1
            total_size += file_size

    # Batch-update KB stats once at the end
    if total_files > 0:
        async with async_session() as db:
            kb = await db.get(KnowledgeBase, kb_id)
            if kb:
                kb.doc_count = (kb.doc_count or 0) + total_files
                kb.chunk_count = (kb.chunk_count or 0) + total_chunks
                kb.total_size = (kb.total_size or 0) + total_size
                kb.updated_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info("[wet] Updated KB '%s' stats: +%d docs, +%d chunks", kb_name, total_files, total_chunks)

    elapsed = time.time() - start_time

    logger.info(
        "[wet] Layer %s done. Files: %d, Chunks: %d, Time: %.1fs",
        kb_name, total_files, total_chunks, elapsed,
    )
    return {
        "kb_id": kb_id,
        "files_found": len(wet_files),
        "chunks_ingested": total_chunks,
        "elapsed_seconds": elapsed,
    }


async def run_multi_layer(
    layer_dirs: list[str | Path],
    max_workers: int = 4,
    max_records: int = 500,
    progress_suffix: str = "",
) -> dict[str, Any]:
    """Process multiple layer dirs with one shared embedding client.

    Workers are divided evenly across layers so every layer makes progress.
    The shared embedding client serializes embedding calls through its own
    QPS semaphore, which prevents Ollama overload regardless of parse concurrency.
    """
    embed_client = EmbeddingClient()
    workers_per_layer = max(1, max_workers // len(layer_dirs)) if layer_dirs else 1

    start_time = time.time()
    results: list[dict[str, Any]] = []

    async def _run_one(layer_dir: str | Path) -> dict[str, Any] | None:
        layer_sem = asyncio.Semaphore(workers_per_layer)
        try:
            return await run_layer(layer_dir, embed_client, layer_sem, max_records, progress_suffix=progress_suffix)
        except Exception as exc:
            logger.error("[wet] Layer %s failed: %s", layer_dir, exc)
            return None

    tasks = [_run_one(d) for d in layer_dirs]
    for coro in asyncio.as_completed(tasks):
        result = await coro
        if result is not None:
            results.append(result)
            logger.info(
                "[wet] Layer KB=%s progress: %d files, %d chunks",
                result.get("kb_id"), result["files_found"], result["chunks_ingested"],
            )

    await embed_client.close()
    elapsed = time.time() - start_time

    total_chunks = sum(r["chunks_ingested"] for r in results)
    total_files = sum(r["files_found"] for r in results)
    logger.info(
        "[wet] All layers done. Files: %d, Chunks: %d, Time: %.1fs",
        total_files, total_chunks, elapsed,
    )
    return {
        "layers": len(layer_dirs),
        "files_found": total_files,
        "chunks_ingested": total_chunks,
        "elapsed_seconds": elapsed,
        "layer_results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="WET streaming embedder for worldview")
    parser.add_argument("--layer-dir", action="append", required=True,
                        help="Directory containing .warc.wet.gz files ( repeatable)")
    parser.add_argument("--workers", type=int, default=4, help="Global concurrent WET streams")
    parser.add_argument("--max-records", type=int, default=500,
                        help="Max conversion records per WET file")
    parser.add_argument("--progress-suffix", default="",
                        help="Suffix for progress file names (allows parallel embedders on same layer)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    summary = asyncio.run(run_multi_layer(
        args.layer_dir,
        max_workers=args.workers,
        max_records=args.max_records,
        progress_suffix=args.progress_suffix,
    ))
    print("\n" + "=" * 50)
    print("WET embedding summary:")
    print(f"  Layers:       {summary['layers']}")
    print(f"  Files found:  {summary['files_found']}")
    print(f"  Chunks:       {summary['chunks_ingested']}")
    print(f"  Time:         {summary['elapsed_seconds']:.1f}s")
    print("=" * 50)


if __name__ == "__main__":
    import argparse
    main()
