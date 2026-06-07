"""Semantic evidence retrieval for report generation.

Replaces heuristic keyword matching with embedding-based retrieval
using the local nomic-embed-text model via Ollama.
"""
from __future__ import annotations

import logging
import math
import re

import numpy as np

from app.services.rag_service import cosine_similarity, get_embedding

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 80
DEFAULT_TOP_K = 12
DEFAULT_MAX_TOTAL_CHARS = 7000


def _semantic_chunks(text: str, size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into chunks respecting paragraph/sentence boundaries."""
    if not text:
        return []

    # First split by paragraphs
    paragraphs = re.split(r"\n\s*\n|\n(?=【)", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= size:
            chunks.append(para)
            continue

        # Long paragraph: split by sentences
        sentences = re.split(r"(?<=[。！？\.\!\?])\s*", para)
        sentences = [s.strip() for s in sentences if s.strip()]

        buf = ""
        for sent in sentences:
            if len(buf) + len(sent) > size and buf:
                chunks.append(buf.strip())
                # Carry over overlap
                if overlap > 0:
                    overlap_sentences = []
                    overlap_len = 0
                    for prev in reversed(buf.split("\n")):
                        if overlap_len + len(prev) > overlap:
                            break
                        overlap_sentences.insert(0, prev)
                        overlap_len += len(prev) + 1
                    buf = "\n".join(overlap_sentences) + ("\n" if overlap_sentences else "") + sent
                else:
                    buf = sent
            else:
                buf = (buf + "\n" + sent).strip() if buf else sent

        if buf.strip():
            chunks.append(buf.strip())

    return chunks


def _source_name(text: str) -> str:
    """Extract source name from evidence text prefix like 【名称】内容."""
    m = re.match(r"【([^】]+)】", text)
    return m.group(1) if m else "参考材料"


class SemanticEvidenceRetriever:
    """Retrieve evidence chunks via semantic similarity."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        top_k: int = DEFAULT_TOP_K,
        max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self.max_total_chars = max_total_chars
        self._embeddings_available: bool | None = None

    async def _check_embedding(self) -> bool:
        if self._embeddings_available is not None:
            return self._embeddings_available
        vec = await get_embedding("test")
        self._embeddings_available = vec is not None
        if not self._embeddings_available:
            logger.warning("Embedding endpoint unavailable; evidence retriever will fall back to keyword matching")
        return self._embeddings_available

    async def build_evidence_block(
        self,
        brief: str,
        uploaded_texts: list[str],
        section_title: str = "",
        key_points: list[str] | None = None,
    ) -> str:
        """Build a formatted evidence block with source annotations.

        Returns a string like:
            【参考材料 — 来源: 2025年述职报告.docx】
            ...content...

            【参考材料 — 来源: 2025年述职报告.docx】
            ...content...
        """
        if not uploaded_texts:
            return ""

        # Build query from brief + section_title + key_points
        query_parts = [brief]
        if section_title:
            query_parts.append(section_title)
        if key_points:
            query_parts.extend(key_points)
        query = "\n".join(query_parts)

        # Build corpus: list of (source_name, chunk_text, full_text_index)
        corpus: list[tuple[str, str, int]] = []
        for src_text in uploaded_texts:
            src_name = _source_name(src_text)
            # Remove the 【名称】 prefix for chunking
            clean_text = re.sub(r"^【[^】]+】\s*", "", src_text)
            chunks = _semantic_chunks(clean_text, self.chunk_size, self.chunk_overlap)
            for chunk in chunks:
                if len(chunk) >= 20:
                    corpus.append((src_name, chunk, len(corpus)))

        if not corpus:
            return ""

        use_embed = await self._check_embedding()

        if use_embed:
            # Compute query embedding
            query_vec = await get_embedding(query[:2000])
            if query_vec:
                # Compute chunk embeddings in batches
                batch_size = 8
                scores: list[tuple[int, float]] = []
                for i in range(0, len(corpus), batch_size):
                    batch = corpus[i : i + batch_size]
                    for idx, (src_name, chunk, _) in enumerate(batch):
                        chunk_vec = await get_embedding(chunk[:4000])
                        if chunk_vec:
                            sim = cosine_similarity(
                                np.array(query_vec),
                                np.array(chunk_vec),
                            )
                            scores.append((i + idx, sim))

                if scores:
                    # Sort by similarity descending
                    scores.sort(key=lambda x: x[1], reverse=True)
                    selected_indices = [idx for idx, _ in scores[: self.top_k]]
                else:
                    selected_indices = list(range(min(self.top_k, len(corpus))))
            else:
                selected_indices = list(range(min(self.top_k, len(corpus))))
        else:
            # Fallback: simple keyword overlap scoring
            query_terms = set(re.findall(r"[一-鿿]{2,}", query))
            scores = []
            for idx, (src_name, chunk, _) in enumerate(corpus):
                chunk_terms = set(re.findall(r"[一-鿿]{2,}", chunk))
                overlap = len(query_terms & chunk_terms)
                scores.append((idx, overlap))
            scores.sort(key=lambda x: x[1], reverse=True)
            selected_indices = [idx for idx, _ in scores[: self.top_k]]

        # Build output, respecting max_total_chars
        selected_indices = sorted(set(selected_indices))
        parts: list[str] = []
        total_chars = 0
        for idx in selected_indices:
            src_name, chunk, _ = corpus[idx]
            entry = f"【参考材料 — 来源: {src_name}】\n{chunk}"
            if total_chars + len(entry) > self.max_total_chars:
                break
            parts.append(entry)
            total_chars += len(entry) + 2  # +2 for \n\n separator

        return "\n\n".join(parts) if parts else ""


def extract_source_names(uploaded_texts: list[str]) -> list[str]:
    """Return the list of unique source file names from uploaded_texts entries.

    Each entry is expected to start with 【filename】.  This list is used to
    validate `[来源: xxx]` annotations in generated content.
    """
    names: list[str] = []
    seen: set[str] = set()
    for t in uploaded_texts or []:
        m = re.match(r"【([^】]+)】", t)
        if m:
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


# Module-level singleton for reuse
_default_retriever: SemanticEvidenceRetriever | None = None


def get_retriever() -> SemanticEvidenceRetriever:
    global _default_retriever
    if _default_retriever is None:
        _default_retriever = SemanticEvidenceRetriever()
    return _default_retriever
