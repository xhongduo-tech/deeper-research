"""知识三角协调器 — 本体论 → 图数据库 → 向量库三路协同检索.

调度顺序:
  1. 意图路由匹配本体论 → 生成结构化约束 + 查询骨架
  2. 图谱查询（entity hops / causal chain）→ 提取因果骨架
  3. 向量 RAG 检索 → 提取原文血肉
  4. 融合：骨架 + 血肉 → 喂给 LLM 合成
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from .intent_router import RoutedIntent

logger = logging.getLogger(__name__)


@dataclass
class TriadResult:
    """三角检索的融合结果."""
    intent: RoutedIntent
    ontology_constraints: dict = field(default_factory=dict)
    graph_context: str = ""        # 图谱实体/关系摘要
    vector_chunks: list[str] = field(default_factory=list)  # RAG 检索段落
    datasource_snippets: list[str] = field(default_factory=list)  # 外部数据源摘要

    def build_context_block(self) -> str:
        """构建注入 LLM 的统一上下文块."""
        parts: list[str] = []

        if self.ontology_constraints:
            parts.append("【本体论约束】")
            for k, v in self.ontology_constraints.items():
                parts.append(f"  {k}: {v}")

        if self.graph_context:
            parts.append("【知识图谱（实体关系/因果链）】")
            parts.append(self.graph_context[:2000])

        if self.vector_chunks:
            parts.append("【知识库检索片段】")
            for i, chunk in enumerate(self.vector_chunks[:8], 1):
                parts.append(f"[{i}] {chunk[:600]}")

        if self.datasource_snippets:
            parts.append("【外部数据源】")
            for snip in self.datasource_snippets[:4]:
                parts.append(snip[:400])

        return "\n\n".join(parts)


class TriadCoordinator:
    """协调三角知识引擎的检索与融合."""

    def __init__(self, db: "AsyncSession"):
        self.db = db

    async def retrieve(
        self,
        query: str,
        intent: RoutedIntent,
        kb_ids: list[int] | None = None,
        entity_hints: list[str] | None = None,
        top_k: int = 8,
    ) -> TriadResult:
        """执行三角检索，返回融合上下文."""
        result = TriadResult(intent=intent)

        # 并行执行三路检索
        import asyncio
        tasks = []

        if intent.uses_ontology():
            tasks.append(self._fetch_ontology_constraints(intent, result))
        else:
            async def _noop_ont(): pass
            tasks.append(_noop_ont())

        tasks.append(self._fetch_graph(query, entity_hints, intent, result))
        tasks.append(self._fetch_vector(query, kb_ids, top_k, result))

        await asyncio.gather(*tasks, return_exceptions=True)

        return result

    # ── 本体论约束 ──────────────────────────────────────────────────────────

    async def _fetch_ontology_constraints(
        self, intent: RoutedIntent, result: TriadResult
    ) -> None:
        """从本体服务取得本体约束规则."""
        try:
            from app.services.ontology_service import OntologyService
            svc = OntologyService(self.db)
            domain = intent.ontology_domain
            constraints = await svc.get_domain_constraints(domain)
            result.ontology_constraints = constraints or {}
            logger.debug("[Triad] Ontology constraints: %d rules", len(result.ontology_constraints))
        except Exception as exc:
            logger.warning("[Triad] Ontology fetch failed: %s", exc)

    # ── 图数据库 ─────────────────────────────────────────────────────────────

    async def _fetch_graph(
        self,
        query: str,
        entity_hints: list[str] | None,
        intent: RoutedIntent,
        result: TriadResult,
    ) -> None:
        """在文档图谱中进行实体hop查询，提取因果骨架."""
        try:
            from app.services.document_graph import DocumentGraph
            graph = DocumentGraph(self.db)

            # 提取查询中的实体（轻量关键词提取）
            entities = entity_hints or _extract_entities(query)
            if not entities:
                return

            snippets: list[str] = []
            for entity in entities[:5]:
                related = await graph.find_related(entity, max_hops=2)
                if related:
                    snippets.append(f"实体「{entity}」相关: {', '.join(related[:10])}")

            result.graph_context = "\n".join(snippets)
            logger.debug("[Triad] Graph: %d entity hops", len(snippets))
        except Exception as exc:
            logger.debug("[Triad] Graph fetch failed (non-critical): %s", exc)

    # ── 向量 RAG ─────────────────────────────────────────────────────────────

    async def _fetch_vector(
        self,
        query: str,
        kb_ids: list[int] | None,
        top_k: int,
        result: TriadResult,
    ) -> None:
        """向量检索知识库."""
        try:
            from app.services.rag_service import search_knowledge_base
            chunks = await search_knowledge_base(
                query=query,
                kb_ids=kb_ids,
                top_k=top_k,
                db=self.db,
            )
            result.vector_chunks = [c.get("text", "") for c in (chunks or []) if c.get("text")]
            logger.debug("[Triad] Vector RAG: %d chunks", len(result.vector_chunks))
        except Exception as exc:
            logger.warning("[Triad] Vector fetch failed: %s", exc)


# ── 轻量实体提取 ───────────────────────────────────────────────────────────────

import re

_STOP_WORDS = {"的", "了", "在", "是", "有", "和", "与", "对", "为", "以", "从", "到", "中", "上", "下"}

def _extract_entities(text: str) -> list[str]:
    """基于规则提取候选实体（无 NLP 依赖）."""
    # CJK 词段
    cjk = re.findall(r"[一-鿿]{2,8}", text)
    # 英文专有名词（首字母大写）
    en = re.findall(r"\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b", text)
    # 数字 + 汉字组合（如 2023年、GDP增长率）
    num_cn = re.findall(r"\d{4}年|[A-Z]{2,10}(?:\d+)?", text)

    candidates = []
    seen: set[str] = set()
    for token in cjk + en + num_cn:
        t = token.strip()
        if t and t not in _STOP_WORDS and t not in seen and len(t) >= 2:
            candidates.append(t)
            seen.add(t)

    return candidates[:10]
