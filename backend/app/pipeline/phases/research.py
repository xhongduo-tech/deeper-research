"""RESEARCH phase — retrieves evidence for each section.

Extracted from the old _phase_generate so that evidence retrieval is:
1. Independently testable
2. Cacheable (result stored in ctx.research_findings)
3. Not tangled with content generation
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import TYPE_CHECKING

from app.pipeline.types import PipelineContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ResearchPhase:
    PHASE_NAME = "RESEARCH"

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx
        # P2-4: Global evidence digest — 4-gram hashes of every block fetched so far.
        # Shared across all concurrent _retrieve_for_section calls to prevent the same
        # RAG chunk from being pulled into multiple sections' evidence budgets.
        self._global_evidence_hashes: set[str] = set()

    async def run(self) -> None:
        ctx = self.ctx
        sections = ctx.outline.get("sections", [])
        tasks = [self._retrieve_for_section(sec) for sec in sections]
        await asyncio.gather(*tasks)

        # P3-A: Cross-section global evidence dedup — remove near-duplicate blocks
        # that ended up in multiple sections (same RAG chunk retrieved for several queries).
        _cross_section_dedup(ctx.research_findings)

        # P3-1: Cache research findings in scoping_plan so section revision can reuse them.
        try:
            scoping = dict(ctx.report.scoping_plan or {})
            scoping["research_cache"] = dict(ctx.research_findings)
            ctx.report.scoping_plan = scoping
            await ctx.db.commit()
        except Exception as exc:
            logger.debug("[RESEARCH] research_cache persist failed (non-fatal): %s", exc)

    async def _retrieve_for_section(self, section: dict) -> None:
        ctx = self.ctx
        section_id = section.get("id", "")
        section_title = section.get("title", "")
        key_points = section.get("key_points", [])
        # P1-3: Dynamic evidence budget — scale with section's target_chars so
        # long sections get proportionally more evidence context.
        target_chars = section.get("target_chars", 500)
        evidence_budget = max(1500, min(6000, target_chars * 3))

        # P2-3: Summary/conclusion sections synthesize the whole document — use
        # ctx.brief as the primary query so RAG retrieves globally relevant chunks
        # rather than only chunks matching the section title.
        _SUMMARY_KWS = {"摘要", "总结", "结论", "概述", "执行摘要", "executive summary",
                        "overview", "conclusion", "summary", "abstract"}
        is_summary_section = any(kw in section_title.lower() for kw in _SUMMARY_KWS)
        if is_summary_section:
            base_query = ctx.brief + "\n" + section_title
        else:
            base_query = f"{ctx.brief}\n{section_title}"
        if key_points:
            base_query += "\n" + " ".join(key_points[:3])

        # P2-A: HyDE — generate a hypothetical excerpt first, use it as the RAG query.
        # Falls back to the original query if HyDE generation fails.
        hyde_query = await _hyde_query(ctx, section_title, key_points, base_query,
                                       target_chars=target_chars)

        # P3-2: Route evidence based on content_type.
        # Narrative/speech sections benefit more from uploaded_texts (prose style);
        # data/table sections benefit more from RAG (structured facts and numbers).
        content_type = section.get("content_type", "paragraphs")
        _DATA_TYPES = {"table", "mixed"}
        prefer_rag = content_type in _DATA_TYPES  # data sections → RAG first
        prefer_texts = not prefer_rag              # narrative sections → uploaded_texts first

        evidence_parts: list[str] = []

        # 1. Evidence from uploaded texts (weighted by content_type)
        # P2-2: Use HyDE query for uploaded_texts retrieval too — the hypothetical
        # excerpt better matches the style/vocabulary of user-uploaded business docs.
        uploaded_query = hyde_query if hyde_query != base_query else section_title
        if ctx.uploaded_texts and prefer_texts:
            try:
                from app.services.evidence_retriever import get_retriever
                retriever = get_retriever()
                ev = retriever.build_evidence_block(
                    ctx.brief,
                    ctx.uploaded_texts,
                    section_title=uploaded_query,
                    key_points=key_points,
                )
                if ev:
                    # P2-4: Label uploaded-text evidence so LLM can attribute evidence_ids
                    evidence_parts.append(f"【上传文档内容】\n{ev}")
            except Exception as exc:
                logger.warning("[RESEARCH] evidence_retriever failed for '%s': %s", section_title, exc)

        # 2. RAG from knowledge base — use HyDE query for better retrieval precision
        if ctx.kb_ids:
            try:
                rag = await _search_rag(ctx.db, ctx.kb_ids, hyde_query)
                if rag:
                    evidence_parts.append(f"【知识库检索结果】\n{rag}")
            except Exception as exc:
                logger.warning("[RESEARCH] RAG failed for '%s': %s", section_title, exc)

        # 2a. LLM-OS: Knowledge Triad Coordinator（本体论→图谱→向量三角协同）
        if ctx.intent and (ctx.intent.uses_ontology() or ctx.intent.uses_vector_rag()):
            try:
                from app.knowledge.triad_coordinator import TriadCoordinator
                coordinator = TriadCoordinator(ctx.db)
                triad = await coordinator.retrieve(
                    query=hyde_query,
                    intent=ctx.intent,
                    kb_ids=ctx.kb_ids or None,
                    top_k=6,
                )
                triad_block = triad.build_context_block()
                if triad_block and len(triad_block) > 100:
                    evidence_parts.append(f"【知识三角检索】\n{triad_block}")
                # 保存到 ctx 供后续章节复用
                if not ctx.triad_result:
                    ctx.triad_result = triad
            except Exception as exc:
                logger.debug("[RESEARCH] Triad coordinator failed (non-fatal): %s", exc)

        # 2b. Official data source routing — fan out to structured knowledge sources
        # based on domain hints extracted from section content_type and title keywords.
        try:
            from app.services.datasource_router import route_query, format_result_as_text
            domain_hints = _build_domain_hints(section_title, content_type, key_points)
            ds_query = f"{ctx.brief} {section_title}"
            report_id = ctx.report.id if ctx.report else 0
            ds_results = await route_query(report_id, ds_query, domain_hints)
            for ds_res in ds_results:
                if not ds_res.error and ds_res.data:
                    ds_text = format_result_as_text(ds_res)
                    if ds_text and len(ds_text) > 50:
                        evidence_parts.append(ds_text)
        except Exception as exc:
            logger.debug("[RESEARCH] datasource_router failed (non-fatal): %s", exc)

        # 1b. Uploaded texts for data sections (added after RAG so RAG is first)
        # P2-2: Use HyDE query here too for consistent retrieval quality
        if ctx.uploaded_texts and prefer_rag:
            try:
                from app.services.evidence_retriever import get_retriever
                retriever = get_retriever()
                ev = retriever.build_evidence_block(
                    ctx.brief,
                    ctx.uploaded_texts,
                    section_title=uploaded_query,
                    key_points=key_points,
                )
                if ev:
                    evidence_parts.append(f"【上传文档内容】\n{ev}")
            except Exception as exc:
                logger.warning("[RESEARCH] evidence_retriever (data route) failed for '%s': %s", section_title, exc)

        # P1-D: Deduplicate near-identical evidence blocks before ranking
        if len(evidence_parts) > 1:
            evidence_parts = _dedup_evidence(evidence_parts, threshold=0.75)

        # P2-4: Global evidence digest — filter out blocks already committed to
        # another section's findings to maximize cross-section content diversity.
        if self._global_evidence_hashes and evidence_parts:
            unique_parts = []
            for ep in evidence_parts:
                ep_hash = _block_hash(ep)
                if ep_hash not in self._global_evidence_hashes:
                    unique_parts.append(ep)
            if unique_parts:  # keep original list if all are new (avoid empty evidence)
                evidence_parts = unique_parts

        # P2-A: MMR selection — balance relevance and diversity
        if len(evidence_parts) > 1:
            query_terms = _extract_query_terms(section_title, key_points)
            evidence_parts = _select_evidence_mmr(evidence_parts, query_terms, k=4, lambda_=0.6)

        # P3-2: Expand evidence when total is too sparse
        if sum(len(e) for e in evidence_parts) < 300:
            evidence_parts = await _expand_evidence(
                ctx, section_title, key_points, evidence_parts
            )

        # Two-hop retrieval: if evidence is still thin after expansion, use the
        # initial findings to formulate a more targeted follow-up query and
        # retrieve a second pass of results from the knowledge base.
        if ctx.kb_ids and sum(len(e) for e in evidence_parts) < 600:
            initial_sample = " ".join(evidence_parts)[:400].strip()
            if initial_sample:
                hop2_query = f"{section_title} {initial_sample[:250]}"
                try:
                    hop2_rag = await _search_rag(ctx.db, ctx.kb_ids, hop2_query)
                    if hop2_rag:
                        # Only add if meaningfully different from existing evidence
                        existing_text = " ".join(evidence_parts)
                        if _jaccard(hop2_rag[:300], existing_text[:300]) < 0.5:
                            evidence_parts.append(f"【深度检索结果】\n{hop2_rag}")
                            logger.debug("[RESEARCH] Two-hop added %d chars for '%s'",
                                         len(hop2_rag), section_title)
                except Exception as exc:
                    logger.debug("[RESEARCH] Two-hop retrieval failed (non-fatal): %s", exc)

        # P3-4: Multi-subquery expansion for complex briefs.
        # When the brief is detailed (≥60 chars) and key_points exist, generate
        # up to 2 focused sub-queries from individual key_points and run additional
        # RAG passes.  Each result is dedup-checked before appending.
        if ctx.kb_ids and key_points and len(ctx.brief or "") >= 60:
            sub_queries = [
                f"{section_title}：{kp}"
                for kp in key_points[:2]
                if kp and len(kp) >= 6
            ]
            existing_text = " ".join(evidence_parts)
            for sub_q in sub_queries:
                try:
                    sub_rag = await _search_rag(ctx.db, ctx.kb_ids, sub_q)
                    if sub_rag and _jaccard(sub_rag[:300], existing_text[:300]) < 0.45:
                        evidence_parts.append(f"【多维检索结果】\n{sub_rag}")
                        existing_text += sub_rag
                        logger.debug("[RESEARCH] Multi-subquery added for '%s': %s…",
                                     section_title, sub_q[:40])
                except Exception as exc:
                    logger.debug("[RESEARCH] Multi-subquery failed (non-fatal): %s", exc)

        # P1-2: Sort evidence blocks by relevance score before capping/joining.
        # Blocks with higher term-hit rates come first so the LLM sees the
        # most relevant context in the budget window.
        query_terms = _extract_query_terms(section_title, key_points)
        if len(evidence_parts) > 1:
            evidence_parts = sorted(
                evidence_parts,
                key=lambda ev: _relevance_score(ev, query_terms),
                reverse=True,
            )

        # P2-1: LLM-based evidence reranking for long analytical sections.
        # Term-hit scoring (above) is fast but surface-level.  For sections that
        # will generate 800+ chars of analysis, a lightweight LLM rerank pass
        # produces better-ordered context — the most relevant blocks move to the
        # front where spec_gen sees them within its token budget.
        if target_chars >= 800 and len(evidence_parts) >= 3 and ctx.kb_ids:
            evidence_parts = await _llm_rerank_evidence(evidence_parts, section_title, key_points)

        # P1-1 + P1-3: Cap evidence to section-specific budget (dynamically set above),
        # preserving at least one block from each distinct source label.
        evidence_parts = _cap_evidence_budget(evidence_parts, max_chars=evidence_budget)

        ctx.research_findings[section_id] = "\n\n".join(evidence_parts)
        if ctx.progress_callback:
            try:
                evidence_text = ctx.research_findings[section_id]
                await ctx.progress_callback({
                    "phase": "RESEARCH",
                    "section_id": section_id,
                    "section_title": section_title,
                    "natural_message": _build_research_narrative(section_title, evidence_text),
                    "evidence_preview": evidence_text[:1800],
                })
            except Exception:
                pass

        # P2-4: Register the kept blocks in the global digest so subsequent sections
        # can skip them. Done after the final cap so only actually-used blocks count.
        for ep in evidence_parts:
            self._global_evidence_hashes.add(_block_hash(ep))


def _build_domain_hints(section_title: str, content_type: str, key_points: list[str]) -> list[str]:
    """Derive domain hints for the datasource router from section metadata.

    Maps content_type and title/keyword signals to high-level domain strings
    that the router's _DOMAIN_HINT_MAP understands (e.g. "金融", "学术").
    """
    hints: list[str] = []
    text = (section_title + " " + " ".join(key_points or [])).lower()

    domain_signals = [
        (["股票", "股价", "财报", "证券", "基金", "期货", "债券", "汇率", "宏观经济", "金融"], "金融"),
        (["论文", "学术", "研究", "文献", "arxiv", "专利"], "学术"),
        (["政策", "政府", "统计局", "发改委", "国务院", "规划", "财政"], "政府"),
        (["天气", "气候", "气象", "降雨", "温度", "环境", "AQI", "碳排放"], "环境"),
        (["新闻", "舆情", "报道", "媒体"], "新闻"),
        (["世界银行", "IMF", "联合国", "国际贸易", "全球"], "国际"),
        (["法律", "法规", "裁判", "合规", "监管"], "法律"),
        (["医疗", "医药", "疾病", "卫生"], "医疗"),
        (["教育", "高考", "学校", "高校", "毕业生"], "教育"),
        (["汽车", "房地产", "能源", "农业", "医药", "零售", "物流", "电信"], "行业"),
        (["工商", "企业注册", "招标", "公告", "ESG", "司法"], "企业"),
    ]

    for keywords, hint in domain_signals:
        if any(kw in text for kw in keywords):
            hints.append(hint)

    # content_type signals
    if content_type in ("table", "mixed"):
        if "金融" not in hints:
            hints.append("金融")

    return hints[:3]  # cap to avoid routing overload


def _block_hash(block: str) -> str:
    """P2-4: Stable 8-char hash of an evidence block for global dedup tracking."""
    import hashlib
    return hashlib.md5(block[:500].encode("utf-8", errors="replace")).hexdigest()[:8]


def _build_research_narrative(section_title: str, evidence: str) -> str:
    text = (evidence or "").strip()
    if not text:
        return f"「{section_title}」资料缺口：未命中可引用材料，正文只能写方法、假设和待验证项，不能写具体事实结论。"
    source_labels = re.findall(r"【([^】]{2,40})】", text)
    source_summary = "、".join(dict.fromkeys(source_labels[:4])) or "上下文材料"
    snippets = [
        re.sub(r"\s+", " ", line).strip(" -•")
        for line in text.splitlines()
        if line.strip() and not re.fullmatch(r"【[^】]+】", line.strip())
    ][:3]
    snippet_text = "；".join(s[:90] for s in snippets if s)
    if len(text) > 120:
        return (
            f"「{section_title}」资料命中：{source_summary}。"
            + (f" 可用要点：{snippet_text}" if snippet_text else "")
        )
    return f"「{section_title}」资料不足：目前只有少量上下文，需降低事实断言密度。"


def _extract_query_terms(section_title: str, key_points: list[str]) -> set[str]:
    """Extract CJK (≥2 char) and ASCII (≥3 char) terms from section title + key points."""
    terms: set[str] = set()
    for text in [section_title] + (key_points or []):
        for term in re.findall(r'[一-龥]{2,}|[a-zA-Z]{3,}', text):
            terms.add(term.lower())
    return terms


def _ngrams(text: str, n: int = 4) -> set[str]:
    """Return the set of n-gram strings from text (chars, not words)."""
    text = re.sub(r'\s+', ' ', text).strip()
    return {text[i:i + n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}


def _jaccard(a: str, b: str, n: int = 4) -> float:
    """Jaccard similarity between 4-gram sets of two strings."""
    sa, sb = _ngrams(a, n), _ngrams(b, n)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _dedup_evidence(parts: list[str], threshold: float = 0.75) -> list[str]:
    """P1-D: Remove near-duplicate evidence blocks using 4-gram Jaccard similarity.

    Keeps the first (usually most relevant) of any near-duplicate pair.
    """
    kept: list[str] = []
    for candidate in parts:
        if not any(_jaccard(candidate, k) >= threshold for k in kept):
            kept.append(candidate)
    return kept


def _cap_evidence_budget(parts: list[str], max_chars: int = 4000) -> list[str]:
    """P1-1: Trim evidence list to stay within max_chars while preserving source diversity.

    Strategy:
    1. Always keep the first block from each distinct source label (【...】 prefix).
    2. Fill remaining budget with additional blocks in order.
    3. Truncate the last block at a sentence boundary if it pushes over budget.
    """
    if not parts:
        return parts

    import re as _re
    _SOURCE_RE = _re.compile(r"^【([^】]+)】")

    seen_labels: set[str] = set()
    anchors: list[str] = []     # one block per unique source label
    rest: list[str] = []

    for block in parts:
        m = _SOURCE_RE.match(block)
        label = m.group(1) if m else "__unlabeled__"
        if label not in seen_labels:
            seen_labels.add(label)
            anchors.append(block)
        else:
            rest.append(block)

    result: list[str] = []
    budget = max_chars

    for block in anchors + rest:
        if budget <= 0:
            break
        if len(block) <= budget:
            result.append(block)
            budget -= len(block)
        else:
            # Truncate at last sentence end within budget
            truncated = block[:budget]
            for punct in ("。", "！", "？", ".", "!", "?"):
                idx = truncated.rfind(punct)
                if idx > max(50, budget // 3):
                    truncated = truncated[: idx + 1]
                    break
            result.append(truncated)
            budget = 0

    return result


def _relevance_score(ev: str, query_terms: set[str]) -> float:
    """Simple term-hit rate as a relevance proxy."""
    if not query_terms:
        return 0.0
    ev_lower = ev.lower()
    return sum(1 for t in query_terms if t in ev_lower) / len(query_terms)


def _select_evidence_mmr(
    parts: list[str],
    query_terms: set[str],
    k: int = 4,
    lambda_: float = 0.6,
) -> list[str]:
    """P2-A: Maximal Marginal Relevance selection to balance relevance and diversity.

    λ=1 → pure relevance ranking; λ=0 → maximum diversity.
    Selected blocks cover different aspects of the section query.
    """
    if not parts:
        return parts
    if len(parts) <= k:
        return parts

    selected: list[str] = []
    remaining = list(parts)

    while remaining and len(selected) < k:
        scores = []
        for ev in remaining:
            rel = _relevance_score(ev, query_terms)
            # Similarity to already-selected blocks (max sim)
            max_sim = max((_jaccard(ev, s) for s in selected), default=0.0)
            mmr = lambda_ * rel - (1 - lambda_) * max_sim
            scores.append(mmr)
        best_idx = scores.index(max(scores))
        selected.append(remaining.pop(best_idx))

    return selected


async def _expand_evidence(
    ctx,
    section_title: str,
    key_points: list[str],
    existing_parts: list[str],
) -> list[str]:
    """P3-2: Try broader queries when gathered evidence is too sparse (< 300 chars total).

    Attempts the brief itself as a query, then individual key points, stopping
    once the total evidence reaches at least 300 chars.
    """
    expanded = list(existing_parts)
    total_chars = sum(len(e) for e in expanded)

    fallback_queries = [ctx.brief] + (key_points or [])[:3]

    for fallback_q in fallback_queries:
        if total_chars >= 300 or not fallback_q:
            break
        try:
            if ctx.kb_ids:
                rag = await _search_rag(ctx.db, ctx.kb_ids, fallback_q)
                if rag and rag not in expanded:
                    expanded.append(f"【扩展检索结果】\n{rag}")
                    total_chars += len(rag)
        except Exception as exc:
            logger.debug("[RESEARCH] expand_evidence RAG failed: %s", exc)

    return expanded if expanded else existing_parts


async def _hyde_query(
    ctx,
    section_title: str,
    key_points: list[str],
    fallback: str,
    target_chars: int = 500,
) -> str:
    """P2-A: HyDE — Hypothetical Document Embeddings.

    Generates a hypothetical excerpt that would appear in a document section
    with this title/key_points. Using the excerpt as the embedding query yields
    better semantic matches than using the question itself.

    P3-3: HyDE length is dynamically scaled to section target_chars:
      target_chars < 400  → 50-char excerpt (brief bullets/data sections)
      target_chars 400-800 → 100-char excerpt (standard sections)
      target_chars > 800  → 150-char excerpt (long analytical sections)

    Falls back to the original query string on any failure (never blocks retrieval).
    """
    if not ctx.kb_ids:
        return fallback  # No RAG to improve; skip expensive LLM call
    try:
        from app.pipeline.llm_helpers import call_llm_text
        kp_text = "、".join(key_points[:3]) if key_points else ""

        # P3-3: Dynamic length target
        if target_chars < 400:
            char_range = "40-60"
            max_tokens = 120
        elif target_chars <= 800:
            char_range = "80-120"
            max_tokens = 250
        else:
            char_range = "120-180"
            max_tokens = 350

        # P1-1: Language-aware HyDE — detect corpus language and generate
        # the excerpt in the same language so the embedding distance is smaller.
        lang = _detect_corpus_language(ctx.uploaded_texts)
        if lang == "en":
            prompt = (
                f"Write a {char_range}-character document excerpt for a section titled "
                f"'{section_title}'"
                + (f", covering: {kp_text}" if kp_text else "")
                + ". Output only the body text, no heading or explanation."
            )
        else:
            prompt = (
                f"请写一段{char_range}字的文档正文，内容属于『{section_title}』章节"
                + (f"，涵盖：{kp_text}" if kp_text else "")
                + "。只输出正文，不要标题或解释。"
            )
        hypothesis = await call_llm_text(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=max_tokens,
            fallback="",
            tier="standard",
        )
        if hypothesis and len(hypothesis.strip()) > 20:
            logger.debug("[RESEARCH] HyDE query generated (%d chars) for '%s'", len(hypothesis), section_title)
            return hypothesis.strip()
    except Exception as exc:
        logger.debug("[RESEARCH] HyDE generation failed (using fallback): %s", exc)
    return fallback


def _cross_section_dedup(research_findings: dict[str, str]) -> None:
    """P3-A: Remove near-duplicate evidence blocks that appear in multiple sections.

    When two sections share a Jaccard-similar block (e.g., same RAG chunk retrieved
    for different queries), keep it only in the first section that received it and
    remove it from subsequent sections to ensure content diversity.
    """
    seen_blocks: list[str] = []
    for section_id, combined in list(research_findings.items()):
        if not combined:
            continue
        blocks = combined.split("\n\n")
        kept = []
        for block in blocks:
            if len(block) < 50:
                kept.append(block)
                continue
            # P3-3: Lowered from 0.7 to 0.55 — catches semantically similar blocks
            # that differ in surface wording (same RAG chunk, slight paraphrase).
            if any(_jaccard(block, seen) >= 0.55 for seen in seen_blocks):
                logger.debug("[RESEARCH] Cross-section dup removed from '%s'", section_id)
                continue
            kept.append(block)
            seen_blocks.append(block)
        research_findings[section_id] = "\n\n".join(kept)


async def _search_rag(db, kb_ids: list[int], query: str, max_chars: int = 3000) -> str:
    if not kb_ids or not query.strip():
        return ""
    try:
        from app.services import rag_service
        results = await rag_service.search_kb(db, kb_ids=kb_ids, query=query, top_k=6)
        return rag_service.format_rag_context(results, max_chars=max_chars)
    except Exception as exc:
        logger.warning("RAG search failed: %s", exc)
        return ""


def _detect_corpus_language(uploaded_texts: list[str] | None) -> str:
    """P1-1 / P3-2: Detect the primary language of the evidence corpus.

    Strategy:
    - Sample up to 2000 chars from uploaded texts
    - Count ASCII alphabetic chars vs CJK chars
    - Use a 0.55 threshold (biased toward CJK since mixed docs are common)
    - Also handles Japanese/Korean by counting them as non-Latin

    Returns "en" for predominantly Latin-alphabet documents, "zh" otherwise.
    Capped at 2000 chars total to avoid O(n) overhead on large documents.
    """
    if not uploaded_texts:
        return "zh"
    sample = "".join(t[:500] for t in uploaded_texts[:4])
    if len(sample) < 50:
        return "zh"

    alpha_ascii = sum(1 for c in sample if c.isalpha() and ord(c) < 128)
    # Count all CJK Unified Ideographs + Katakana + Hiragana + Hangul
    cjk = sum(1 for c in sample if (
        "一" <= c <= "鿿"   # CJK unified
        or "぀" <= c <= "ヿ"  # Hiragana/Katakana
        or "가" <= c <= "힯"  # Hangul
    ))
    total = alpha_ascii + cjk
    if total == 0:
        return "zh"
    return "en" if alpha_ascii / total > 0.55 else "zh"


async def _llm_rerank_evidence(
    parts: list[str],
    section_title: str,
    key_points: list[str],
) -> list[str]:
    """P2-1: LLM-based evidence reranking for long analytical sections.

    Scores each evidence block (0-10) against the section query and returns them
    ordered best-first.  Falls back to the original order on any failure so the
    call is always non-blocking.

    Only invoked for sections with target_chars ≥ 800 and ≥ 3 evidence blocks.
    Uses 'standard' tier to keep latency low (same tier as HyDE).
    """
    try:
        from app.pipeline.llm_helpers import call_llm_json
        kp_text = "；".join(key_points[:3]) if key_points else ""
        # Build compact summaries (first 200 chars each) so the prompt stays small
        summaries = "\n".join(
            f"[{i}] {p[:200].replace(chr(10), ' ')}"
            for i, p in enumerate(parts)
        )
        result = await call_llm_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是信息检索专家。对以下证据片段按与查询的相关性打分（0-10整数），"
                        "只输出JSON数组，每项含 index 和 score 字段。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"查询：{section_title}" + (f"；{kp_text}" if kp_text else "") + "\n\n"
                        f"证据片段：\n{summaries}"
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=300,
            fallback=[],
            tier="standard",
        )
        items = result if isinstance(result, list) else result.get("items", [])
        scored = [(item.get("index", i), int(item.get("score", 5))) for i, item in enumerate(items)]
        scored.sort(key=lambda x: x[1], reverse=True)
        reordered = []
        used = set()
        for idx, _ in scored:
            if isinstance(idx, int) and 0 <= idx < len(parts) and idx not in used:
                reordered.append(parts[idx])
                used.add(idx)
        # Append any blocks not mentioned by LLM (safety net)
        for i, p in enumerate(parts):
            if i not in used:
                reordered.append(p)
        if reordered:
            logger.debug("[RESEARCH] LLM rerank reordered %d blocks for '%s'",
                         len(reordered), section_title)
            return reordered
    except Exception as exc:
        logger.debug("[RESEARCH] LLM rerank failed (non-fatal): %s", exc)
    return parts
