import hashlib
import math
import re
from collections import Counter
from typing import Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.config_service import ConfigService


class KnowledgeBaseService:
    """
    Builds a task-scoped evidence index from uploaded files.
    Vectorization is configured only through /admin system settings.
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def build_for_task(self, files: List[dict]) -> dict:
        config = await ConfigService(self.db).get_embedding_config()
        chunks = self._chunk_files(files, chunk_size=config["chunk_size"])
        embeddings_enabled = bool(config["enabled"] and config["api_key"] and chunks)

        if embeddings_enabled:
            await self._attach_embeddings(chunks, config)

        return {
            "enabled": True,
            "vector_store_enabled": embeddings_enabled,
            "embedding_model": config["model"] if embeddings_enabled else None,
            "chunk_size": config["chunk_size"],
            "top_k": config["top_k"],
            "document_count": len(files),
            "chunk_count": len(chunks),
            "documents": [
                {
                    "file_id": f.get("id"),
                    "file_name": f.get("name"),
                    "file_type": f.get("type"),
                    "size": f.get("size"),
                    "content_chars": len(f.get("content") or ""),
                }
                for f in files
            ],
            "chunks": chunks,
            "evidence_summary": self.format_evidence_summary(chunks, limit=config["top_k"]),
        }

    def format_evidence_summary(self, chunks: List[dict], limit: int = 12) -> str:
        if not chunks:
            return "## 知识库证据索引\n- 未发现可索引的上传文件内容。"
        parts = ["## 知识库证据索引"]
        for chunk in chunks[:limit]:
            parts.append(
                f"- [{chunk['evidence_id']}] {chunk['file_name']} | "
                f"片段{chunk['chunk_index'] + 1} | 关键词: {', '.join(chunk['keywords'][:6])}\n"
                f"  摘要: {chunk['preview']}"
            )
        return "\n".join(parts)

    def select_relevant(self, knowledge_base: dict, query: str, top_k: Optional[int] = None) -> List[dict]:
        chunks = knowledge_base.get("chunks") or []
        if not chunks:
            return []
        top_k = top_k or knowledge_base.get("top_k") or 12
        query_terms = self._keywords(query, limit=32)
        scored = []
        for chunk in chunks:
            score = len(set(query_terms) & set(chunk.get("keywords", [])))
            if score == 0:
                score = self._text_overlap(query, chunk.get("text", ""))
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for score, chunk in scored[:top_k] if score > 0] or chunks[:top_k]

    def _chunk_files(self, files: List[dict], chunk_size: int) -> List[dict]:
        chunks = []
        for file in files:
            text = (file.get("content") or "").strip()
            if not text:
                continue
            for idx, (start, chunk_text) in enumerate(self._split_text(text, chunk_size)):
                evidence_id = self._evidence_id(file.get("id"), idx, chunk_text)
                chunks.append({
                    "evidence_id": evidence_id,
                    "file_id": file.get("id"),
                    "file_name": file.get("name"),
                    "file_type": file.get("type"),
                    "chunk_index": idx,
                    "char_start": start,
                    "char_end": start + len(chunk_text),
                    "keywords": self._keywords(chunk_text),
                    "preview": re.sub(r"\s+", " ", chunk_text[:260]).strip(),
                    "text": chunk_text,
                })
        return chunks

    def _split_text(self, text: str, chunk_size: int) -> List[tuple]:
        chunk_size = max(400, min(int(chunk_size or 1200), 4000))
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
        chunks = []
        current = ""
        current_start = 0
        cursor = 0
        for para in paragraphs or [text]:
            found_at = text.find(para, cursor)
            if found_at >= 0:
                cursor = found_at + len(para)
            if len(current) + len(para) + 2 <= chunk_size:
                if not current:
                    current_start = found_at if found_at >= 0 else cursor
                current = f"{current}\n\n{para}".strip()
            else:
                if current:
                    chunks.append((current_start, current))
                current_start = found_at if found_at >= 0 else cursor
                current = para[:chunk_size]
        if current:
            chunks.append((current_start, current))
        return chunks

    async def _attach_embeddings(self, chunks: List[dict], config: Dict):
        client = AsyncOpenAI(api_key=config["api_key"], base_url=config["base_url"])
        batch_size = 64
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start:start + batch_size]
            response = await client.embeddings.create(
                model=config["model"],
                input=[chunk["text"][:8000] for chunk in batch],
            )
            for chunk, item in zip(batch, response.data):
                # Keep enough for local similarity without making task JSON enormous.
                chunk["embedding"] = [round(float(v), 6) for v in item.embedding[:512]]

    def _keywords(self, text: str, limit: int = 16) -> List[str]:
        tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+-]{2,}|\d+(?:\.\d+)?%?", text)
        stop = {"the", "and", "for", "with", "this", "that", "from", "文件", "工作表", "数据", "分析"}
        counts = Counter(t.lower() for t in tokens if t.lower() not in stop)
        return [term for term, _ in counts.most_common(limit)]

    def _text_overlap(self, query: str, text: str) -> float:
        query_chars = set(query)
        text_chars = set(text[:1000])
        if not query_chars:
            return 0
        return len(query_chars & text_chars) / math.sqrt(len(query_chars))

    def _evidence_id(self, file_id, index: int, text: str) -> str:
        digest = hashlib.sha1(f"{file_id}:{index}:{text[:80]}".encode("utf-8")).hexdigest()[:8]
        return f"E{file_id or 'X'}-{index + 1}-{digest}"
