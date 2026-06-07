"""
RAG Service — Knowledge Base retrieval.

Architecture:
  - Documents chunked (~2000 chars, 200 overlap)
  - Embeddings via external OpenAI-compatible API (bge-m3, 1024-dim)
  - Vectors stored in Qdrant (HNSW + int8 quantization) with SQLite fallback
  - Hybrid search: dense (Qdrant) + sparse (TF-IDF) + lexical (BM25) + number boost
"""
from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

import httpx
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_base import KnowledgeBase, KBDocument, KBChunk
from app.services import runtime_config

logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────

EMBED_MODEL = settings.embed_model          # bge-m3
EMBED_DIM = 1024                            # bge-m3 dense dimension
CHUNK_SIZE = settings.rag_chunk_size        # 2000 chars
CHUNK_OVERLAP = settings.rag_chunk_overlap  # 200 chars

# ── Vector store routing ────────────────────────────────────────────────────

_USE_QDRANT = settings.vector_store_type.lower() == "qdrant"


def _get_qdrant_store():
    if _USE_QDRANT:
        from app.services.qdrant_store import get_qdrant_store
        return get_qdrant_store()
    return None


# ── Tokenization helpers ────────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"(?<=[。！？\.\!\?])\s*")


def _rag_tokens(text: str) -> list[str]:
    cn = re.findall(r"[一-鿿]{2,}", text or "")
    latin = re.findall(r"[A-Za-z0-9_]{2,}", text or "")
    nums = re.findall(r"\d+(?:\.\d+)?%?", text or "")
    return cn + [t.lower() for t in latin] + nums


def _normalize_scores(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi <= lo:
        return {k: 1.0 if v > 0 else 0.0 for k, v in scores.items()}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}


def _bm25_scores(texts: list[str], query: str) -> dict[int, float]:
    query_terms = _rag_tokens(query)
    if not texts or not query_terms:
        return {}
    docs = [_rag_tokens(text) for text in texts]
    avg_len = sum(len(d) for d in docs) / max(len(docs), 1)
    df = {}
    for doc in docs:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    n = len(docs)
    k1 = 1.5
    b = 0.75
    scores: dict[int, float] = {}
    for idx, doc in enumerate(docs):
        tf = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        doc_len = len(doc) or 1
        score = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            denom = tf[term] + k1 * (1 - b + b * doc_len / max(avg_len, 1))
            score += idf * (tf[term] * (k1 + 1) / denom)
        scores[idx] = score
    return _normalize_scores(scores)


def _lexical_overlap_score(text: str, query: str) -> float:
    q = set(_rag_tokens(query))
    if not q:
        return 0.0
    t = set(_rag_tokens(text))
    return len(q & t) / max(len(q), 1)


def _number_boost(text: str, query: str) -> float:
    q_nums = set(re.findall(r"\d+(?:\.\d+)?%?", query or ""))
    if not q_nums:
        return 0.0
    compact = re.sub(r"\s+", "", text or "")
    matched = sum(1 for n in q_nums if n in compact)
    return min(0.12, 0.04 * matched)


# ── Embedding ──────────────────────────────────────────────────────────────

async def get_embedding(text: str) -> list[float] | None:
    """Call external OpenAI-compatible embed endpoint. Returns None on failure."""
    results = await get_embeddings_batch([text])
    return results[0] if results else None


async def get_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Batch embedding call. Returns list aligned with input; None for failed items."""
    base_url = settings.embed_base_url or settings.default_llm_base_url
    api_key = settings.embed_api_key or settings.default_llm_api_key
    if not base_url or not texts:
        return [None] * len(texts)

    base_url = base_url.rstrip("/")
    url = f"{base_url}/embeddings"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    batch_size = max(1, settings.embed_batch_size)

    results: list[list[float] | None] = [None] * len(texts)
    timeout = max(60, 10 + batch_size * 2)

    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    url,
                    headers=headers,
                    json={
                        "model": EMBED_MODEL,
                        "input": [t[:8000] for t in chunk],
                        "encoding_format": "float",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("data", [])
                # API returns embeddings sorted by index; fill results accordingly
                for item in embeddings:
                    idx = item.get("index")
                    if idx is not None and 0 <= idx < len(chunk):
                        results[start + idx] = [float(x) for x in item["embedding"]]
        except Exception as e:
            logger.warning("Batch embedding API failed for chunk %d-%d: %s", start, start + len(chunk), e)
    return results


def tfidf_embed(texts: list[str], query: str) -> tuple[np.ndarray, np.ndarray]:
    """Fallback TF-IDF vectorisation when embedding API unavailable."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    corpus = texts + [query]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), max_features=4096)
    mat = vec.fit_transform(corpus).toarray()
    return mat[:-1], mat[-1]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ── Chunking ───────────────────────────────────────────────────────────────

def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, respecting sentence boundaries."""
    sentences = _SENTENCE_RE.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        return [text[:size]] if text else []

    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) <= size:
            current += sent
        else:
            if current:
                chunks.append(current)
            overlap_text = current[-overlap:] if len(current) > overlap else current
            current = overlap_text + sent
    if current:
        chunks.append(current)
    return chunks if chunks else [text[:size]]


# ── Document Ingestion ─────────────────────────────────────────────────────

async def ingest_document(
    db: AsyncSession,
    kb_id: int,
    title: str,
    content: str,
    file_type: str = "text",
    file_size: int = 0,
) -> KBDocument:
    """Add a document to a KB: chunk + embed + store (SQLite + optional Qdrant)."""
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise ValueError(f"Knowledge base {kb_id} not found")

    doc = KBDocument(
        kb_id=kb_id,
        title=title,
        file_type=file_type,
        file_size=file_size,
        content_preview=content[:500],
        status="pending",
    )
    db.add(doc)
    await db.flush()

    chunks = chunk_text(content)
    doc.chunk_count = len(chunks)

    qdrant = _get_qdrant_store()
    qdrant_points: list[dict[str, Any]] = []

    embeddings = await get_embeddings_batch(chunks) if chunks else []

    for i, chunk_text_content in enumerate(chunks):
        embedding = embeddings[i] if i < len(embeddings) else None
        chunk = KBChunk(
            kb_id=kb_id,
            doc_id=doc.id,
            content=chunk_text_content,
            chunk_index=i,
        )
        if embedding:
            chunk.set_embedding(embedding)
        db.add(chunk)
        await db.flush()  # need chunk.id for Qdrant point ID

        if qdrant and embedding:
            qdrant_points.append({
                "id": f"{kb_id}_{doc.id}_{i}",
                "vector": embedding,
                "kb_id": kb_id,
                "doc_id": doc.id,
                "content": chunk_text_content,
                "chunk_index": i,
            })

    if qdrant and qdrant_points:
        qdrant.upsert_chunks(qdrant_points)

    doc.status = "indexed"
    kb.doc_count = (kb.doc_count or 0) + 1
    kb.chunk_count = (kb.chunk_count or 0) + len(chunks)
    kb.total_size = (kb.total_size or 0) + file_size
    kb.embed_model = EMBED_MODEL

    await db.commit()
    await db.refresh(doc)
    return doc


# ── Search ─────────────────────────────────────────────────────────────────

async def search_kb(
    db: AsyncSession,
    kb_ids: list[int],
    query: str,
    top_k: int = 10,
    score_threshold: float = 0.15,
) -> list[dict]:
    """Retrieve top-k relevant chunks from given knowledge bases."""
    if not runtime_config.is_rag_enabled():
        return []
    if not kb_ids or not query.strip():
        return []

    # ── Qdrant path (preferred) ────────────────────────────────────────────
    qdrant = _get_qdrant_store()
    if qdrant and qdrant.is_healthy():
        try:
            return await _search_qdrant(db, qdrant, kb_ids, query, top_k, score_threshold)
        except Exception as exc:
            logger.warning("Qdrant search failed, falling back to SQLite: %s", exc)

    # ── SQLite fallback ────────────────────────────────────────────────────
    return await _search_sqlite(db, kb_ids, query, top_k, score_threshold)


async def _search_qdrant(
    db: AsyncSession,
    qdrant,
    kb_ids: list[int],
    query: str,
    top_k: int,
    score_threshold: float,
) -> list[dict]:
    """Search via Qdrant dense retrieval + SQLite metadata enrichment."""
    query_vec = await get_embedding(query)
    if not query_vec:
        # No embedding available — fall through to SQLite path
        raise RuntimeError("Embedding unavailable")

    # Gather results from all target KBs
    all_results: list[dict] = []
    for kb_id in kb_ids:
        hits = qdrant.search(
            vector=query_vec,
            top_k=top_k * 2,  # oversample for re-ranking
            kb_id=kb_id,
            score_threshold=score_threshold,
        )
        all_results.extend(hits)

    # Sort by Qdrant score and deduplicate by doc_id
    all_results.sort(key=lambda x: x["score"], reverse=True)

    seen_docs: set[int] = set()
    final: list[dict] = []
    for hit in all_results:
        if hit["doc_id"] in seen_docs:
            continue
        seen_docs.add(hit["doc_id"])

        doc = await db.get(KBDocument, hit["doc_id"])
        kb = await db.get(KnowledgeBase, hit["kb_id"])
        source_id = f"KB{hit['kb_id']}-D{hit['doc_id']}-C{hit['chunk_index']}"

        # Apply lexical re-ranking on top of Qdrant score
        lexical = _lexical_overlap_score(hit["content"], query)
        boost = _number_boost(hit["content"], query)
        reranked = min(1.0, hit["score"] * 0.7 + lexical * 0.2 + boost * 0.1)

        final.append({
            "source_id": source_id,
            "chunk_id": hit["id"],
            "doc_id": hit["doc_id"],
            "kb_id": hit["kb_id"],
            "doc_title": doc.title if doc else "Unknown",
            "kb_name": kb.name if kb else "Unknown",
            "content": hit["content"],
            "score": round(reranked, 4),
            "rerank_score": round(reranked, 4),
            "score_parts": {
                "qdrant_score": round(hit["score"], 4),
                "lexical_score": round(lexical, 4),
                "number_boost": round(boost, 4),
            },
            "chunk_index": hit["chunk_index"],
            "provenance": {
                "source_id": source_id,
                "kb_name": kb.name if kb else "Unknown",
                "doc_title": doc.title if doc else "Unknown",
                "chunk_index": hit["chunk_index"],
            },
        })

        if len(final) >= top_k:
            break

    return final


async def _search_sqlite(
    db: AsyncSession,
    kb_ids: list[int],
    query: str,
    top_k: int,
    score_threshold: float,
) -> list[dict]:
    """Legacy SQLite-only search path (dense + sparse + lexical hybrid)."""
    result = await db.execute(
        select(KBChunk).where(KBChunk.kb_id.in_(kb_ids))
    )
    all_chunks: list[KBChunk] = result.scalars().all()
    if not all_chunks:
        return []

    query_vec = await get_embedding(query)

    dense_scores: dict[int, float] = {}
    if query_vec:
        q_arr = np.array(query_vec, dtype=np.float32)
        for idx, chunk in enumerate(all_chunks):
            vec = chunk.get_embedding()
            if vec:
                sim = cosine_similarity(np.array(vec, dtype=np.float32), q_arr)
                dense_scores[idx] = sim
    dense_scores = _normalize_scores(dense_scores)

    sparse_scores: dict[int, float] = {}
    try:
        texts = [c.content for c in all_chunks]
        chunk_vecs, query_arr = tfidf_embed(texts, query)
        for i, chunk in enumerate(all_chunks):
            sparse_scores[i] = cosine_similarity(chunk_vecs[i], query_arr)
        sparse_scores = _normalize_scores(sparse_scores)
    except Exception as exc:
        logger.debug("TF-IDF sparse retrieval unavailable: %s", exc)

    texts = [c.content for c in all_chunks]
    bm25 = _bm25_scores(texts, query)
    scored: list[tuple[float, int, KBChunk, dict]] = []
    for idx, chunk in enumerate(all_chunks):
        dense = dense_scores.get(idx, 0.0)
        sparse = sparse_scores.get(idx, 0.0)
        lexical = bm25.get(idx, 0.0)
        overlap = _lexical_overlap_score(chunk.content, query)
        boost = _number_boost(chunk.content, query)
        if dense_scores:
            final = 0.42 * dense + 0.28 * sparse + 0.22 * lexical + 0.08 * overlap + boost
        else:
            final = 0.42 * sparse + 0.38 * lexical + 0.20 * overlap + boost
        scored.append((min(final, 1.0), idx, chunk, {
            "dense_score": round(dense, 4),
            "sparse_score": round(sparse, 4),
            "lexical_score": round(lexical, 4),
            "overlap_score": round(overlap, 4),
            "number_boost": round(boost, 4),
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    seen_docs: set[int] = set()
    for score, idx, chunk, score_parts in scored[:top_k * 3]:
        if score < score_threshold:
            break
        if chunk.doc_id in seen_docs:
            continue
        seen_docs.add(chunk.doc_id)

        doc = await db.get(KBDocument, chunk.doc_id)
        kb = await db.get(KnowledgeBase, chunk.kb_id)
        source_id = f"KB{chunk.kb_id}-D{chunk.doc_id}-C{chunk.chunk_index}"
        results.append({
            "source_id": source_id,
            "chunk_id": chunk.id,
            "doc_id": chunk.doc_id,
            "kb_id": chunk.kb_id,
            "doc_title": doc.title if doc else "Unknown",
            "kb_name": kb.name if kb else "Unknown",
            "content": chunk.content,
            "score": round(score, 4),
            "rerank_score": round(score, 4),
            "score_parts": score_parts,
            "chunk_index": chunk.chunk_index,
            "provenance": {
                "source_id": source_id,
                "kb_name": kb.name if kb else "Unknown",
                "doc_title": doc.title if doc else "Unknown",
                "chunk_index": chunk.chunk_index,
            },
        })
        if len(results) >= top_k:
            break

    return results


# ── Context formatting ─────────────────────────────────────────────────────

def format_rag_context(results: list[dict], max_chars: int = 4000) -> str:
    """Format retrieval results as a context block for the LLM."""
    if not results:
        return ""
    lines = ["【知识库检索结果】\n"]
    used = 0
    for r in results:
        block = (
            f"来源：[{r.get('source_id', 'KB')}] {r['kb_name']} — {r['doc_title']}（综合相关度 {r['score']:.0%}）\n"
            f"{r['content']}\n"
        )
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


# ── KB CRUD helpers ────────────────────────────────────────────────────────

async def create_kb(
    db: AsyncSession,
    name: str,
    description: str = "",
    scope: str = "personal",
    kb_type: str = "general",
    owner_id: int | None = None,
) -> KnowledgeBase:
    kb = KnowledgeBase(
        name=name,
        description=description,
        scope=scope,
        kb_type=kb_type,
        owner_id=owner_id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def list_kbs(db: AsyncSession, owner_id: int | None = None) -> list[KnowledgeBase]:
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    if owner_id:
        stmt = stmt.where(KnowledgeBase.owner_id == owner_id)
    result = await db.execute(stmt)
    return result.scalars().all()


async def delete_kb(db: AsyncSession, kb_id: int) -> bool:
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        return False
    # Also delete from Qdrant if active
    qdrant = _get_qdrant_store()
    if qdrant:
        try:
            qdrant.delete_by_kb(kb_id)
        except Exception as exc:
            logger.warning("Qdrant delete failed for kb_id=%d: %s", kb_id, exc)
    await db.delete(kb)
    await db.commit()
    return True


async def list_kb_documents(db: AsyncSession, kb_id: int) -> list[KBDocument]:
    result = await db.execute(
        select(KBDocument).where(KBDocument.kb_id == kb_id).order_by(KBDocument.created_at.desc())
    )
    return result.scalars().all()


async def delete_document(db: AsyncSession, doc_id: int) -> bool:
    doc = await db.get(KBDocument, doc_id)
    if not doc:
        return False
    kb = await db.get(KnowledgeBase, doc.kb_id)
    if kb:
        kb.doc_count = max(0, (kb.doc_count or 1) - 1)
        kb.chunk_count = max(0, (kb.chunk_count or doc.chunk_count) - doc.chunk_count)
        kb.total_size = max(0, (kb.total_size or 0) - doc.file_size)
    await db.delete(doc)
    await db.commit()
    return True
