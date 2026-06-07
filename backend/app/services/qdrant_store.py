"""Qdrant vector store adapter for DataAgent Studio.

Features:
  - Collection management with HNSW indexing
  - Scalar Quantization (int8) to reduce storage by ~4x
  - Batch upsert for high-throughput embedding ingestion
  - Snapshot backup/restore for offline packaging
  - Hybrid search: dense + sparse (if available)

Requires: qdrant-client>=1.9.0
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy import to avoid hard dependency when SQLite mode is used
try:
    from qdrant_client import QdrantClient, models
    from qdrant_client.http.models import Distance, VectorParams, ScalarQuantization, ScalarType
    _QDRANT_AVAILABLE = True
except ImportError:  # pragma: no cover
    _QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore[misc, assignment]
    models = None  # type: ignore[misc, assignment]
    Distance = VectorParams = ScalarQuantizationConfig = ScalarType = None  # type: ignore[misc, assignment]

EMBED_DIM = 1024  # bge-m3 dense dimension
COLLECTION_NAME = settings.qdrant_collection


class QdrantStore:
    """High-level wrapper around Qdrant for KB chunk storage."""

    def __init__(self) -> None:
        if not _QDRANT_AVAILABLE:
            raise ImportError("qdrant-client is not installed. Run: pip install qdrant-client")

        self.client: QdrantClient = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            prefer_grpc=False,  # HTTP is simpler for air-gapped
        )
        self._collection_ensured = False

    # ── Collection lifecycle ────────────────────────────────────────────────

    def ensure_collection(self, vector_size: int = EMBED_DIM) -> None:
        """Create collection if it doesn't exist, with HNSW + int8 quantization."""
        if self._collection_ensured:
            return

        collections = self.client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)

        if exists:
            logger.info("[qdrant] Collection '%s' already exists", COLLECTION_NAME)
            self._collection_ensured = True
            return

        # Scalar Quantization (int8): 4x storage reduction, <3% accuracy loss
        # Reference: https://qdrant.tech/documentation/guides/quantization/
        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
                on_disk=True,  # store vectors on disk, not memory
            ),
            quantization_config=ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=False,
                ),
            ),
            hnsw_config=models.HnswConfigDiff(
                m=16,
                ef_construct=100,
                full_scan_threshold=10000,
                on_disk=True,
            ),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=10000,  # start indexing after 10k vectors
            ),
        )
        logger.info("[qdrant] Created collection '%s' (dim=%d, int8 quantized)", COLLECTION_NAME, vector_size)
        self._collection_ensured = True

    def delete_collection(self) -> None:
        """Drop the entire collection (dangerous — use with care)."""
        self.client.delete_collection(COLLECTION_NAME)
        logger.warning("[qdrant] Deleted collection '%s'", COLLECTION_NAME)
        self._collection_ensured = False

    # ── Point operations ────────────────────────────────────────────────────

    def upsert_chunks(
        self,
        chunks: list[dict[str, Any]],
        batch_size: int = 128,
    ) -> int:
        """Upsert chunks into Qdrant.

        Each chunk dict must have:
          - id: str | int (unique point ID)
          - vector: list[float] (1024-dim for bge-m3)
          - kb_id: int
          - doc_id: int
          - content: str
          - chunk_index: int
        """
        self.ensure_collection()
        total = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            points = []
            for c in batch:
                vec = c["vector"]
                if isinstance(vec, np.ndarray):
                    vec = vec.tolist()
                points.append(
                    models.PointStruct(
                        id=c["id"],
                        vector=vec,
                        payload={
                            "kb_id": c["kb_id"],
                            "doc_id": c["doc_id"],
                            "content": c["content"],
                            "chunk_index": c.get("chunk_index", 0),
                        },
                    )
                )

            self.client.upsert(collection_name=COLLECTION_NAME, points=points, wait=False)
            total += len(batch)

        logger.info("[qdrant] Upserted %d chunks", total)
        return total

    def search(
        self,
        vector: list[float] | np.ndarray,
        top_k: int = 10,
        kb_id: int | None = None,
        score_threshold: float | None = None,
    ) -> list[dict[str, Any]]:
        """Search Qdrant by vector similarity.

        Returns list of dicts with: id, score, kb_id, doc_id, content, chunk_index
        """
        self.ensure_collection()

        if isinstance(vector, np.ndarray):
            vector = vector.tolist()

        # Build filter for kb_id if specified
        query_filter = None
        if kb_id is not None:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="kb_id", match=models.MatchValue(value=kb_id))]
            )

        results = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            {
                "id": r.id,
                "score": r.score,
                "kb_id": r.payload.get("kb_id"),
                "doc_id": r.payload.get("doc_id"),
                "content": r.payload.get("content"),
                "chunk_index": r.payload.get("chunk_index", 0),
            }
            for r in results
        ]

    def delete_by_kb(self, kb_id: int) -> int:
        """Delete all chunks belonging to a knowledge base."""
        self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.Filter(
                must=[models.FieldCondition(key="kb_id", match=models.MatchValue(value=kb_id))]
            ),
        )
        logger.info("[qdrant] Deleted all chunks for kb_id=%d", kb_id)
        return 0  # Qdrant does not return deletion count in this API

    def count(self) -> int:
        """Return total number of vectors in the collection."""
        return self.client.count(collection_name=COLLECTION_NAME).count

    # ── Snapshot ────────────────────────────────────────────────────────────

    def create_snapshot(self) -> str:
        """Create a snapshot of the collection for offline packaging.

        Returns the snapshot file name (e.g. 'kb_chunks-20240604-123456.snapshot')
        """
        snapshot_info = self.client.create_snapshot(collection_name=COLLECTION_NAME)
        logger.info("[qdrant] Snapshot created: %s", snapshot_info.name)
        return snapshot_info.name

    def list_snapshots(self) -> list[str]:
        """List all available snapshots."""
        snapshots = self.client.list_snapshots(collection_name=COLLECTION_NAME)
        return [s.name for s in snapshots]

    def recover_snapshot(self, snapshot_name: str) -> None:
        """Recover collection from a snapshot."""
        self.client.recover_snapshot(
            collection_name=COLLECTION_NAME,
            location=snapshot_name,  # local path or URL
        )
        logger.info("[qdrant] Recovered from snapshot: %s", snapshot_name)

    # ── Health check ────────────────────────────────────────────────────────

    def is_healthy(self) -> bool:
        try:
            self.client.health_check()
            return True
        except Exception:
            return False


# ── Singleton instance (lazy) ───────────────────────────────────────────────

_qdrant_store: QdrantStore | None = None


def get_qdrant_store() -> QdrantStore:
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantStore()
    return _qdrant_store
