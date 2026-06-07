"""SPEC_GEN phase — LLM generates a validated DocumentSpec JSON.

This is the core fix for template adherence:
- LLM must produce JSON conforming to the DocumentSpec schema
- Pydantic validation on every attempt — never accept invalid output
- Retry with FULL constraints + prior error injected (no prompt simplification)
- After max retries: raise PipelineError (no silent fallback)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re as _re
from typing import TYPE_CHECKING

# ── Module-level compiled patterns (avoid re-compiling per call) ──────────────
# Matches Chinese metric label + numeric value with optional unit suffix.
# Examples: "营收50亿", "增长率30%", "用户数：1200万"
_RE_NUMERIC_ENTITY = _re.compile(
    r"([一-龥]{2,8})[：:]?\s*(\d[\d,\.]*)\s*(%|万|亿|元|人|个|项|次)?"
)
# Matches any digit (used for quick presence check — no unit required)
_RE_DIGIT = _re.compile(r"\d")
# Matches all digit sequences (for density / count calculations)
_RE_ALL_DIGITS = _re.compile(r"\d+")

from pydantic import ValidationError

from app.pipeline.types import PipelineContext, PipelineError
from app.pipeline.llm_helpers import call_llm_json
from app.pipeline.skills_loader import build_skill_context, filter_skills_for_phase
from app.services.document_standards import format_standard_for_prompt, get_document_standard
from app.rendering.doc_spec import (
    ChartSpec, ChartSeriesSpec,
    DocxSectionSpec, PptxSlideSpec, XlsxSheetSpec,
    DocxSpec, PptxSpec, XlsxSpec,
    get_spec_schema_hint,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

MAX_SECTION_RETRIES = 3


class SpecGenPhase:
    """Generates DocumentSpec by asking LLM to fill each section/slide in parallel."""

    PHASE_NAME = "SPEC_GEN"

    def __init__(self, ctx: PipelineContext, qa_feedback: list[dict] | None = None):
        self.ctx = ctx
        self.qa_feedback = qa_feedback or []  # For QA-triggered re-generation
        # P3-B: Cached invariant system prompt components
        self._cached_skill_context: str = ""
        self._cached_intent_rules: str = ""
        # P1-2: Track sections that degraded to placeholder (for QA escalation)
        self._has_warnings: bool = False
        self._failed_section_ids: list[str] = []
        # P1-3: Global numeric entity map — canonical value for each metric across ALL sections.
        # Unlike rolling_context (5-item window), this dict persists the full document's
        # number history so later sections cannot contradict earlier ones.
        self._numeric_entity_map: dict[str, str] = {}

    async def run(self, section_ids: list[str] | None = None) -> None:
        """Generate specs for all sections (or only the listed section_ids for QA retry)."""
        ctx = self.ctx
        outline = ctx.outline
        sections = outline.get("sections", [])

        if section_ids:
            sections = [s for s in sections if s.get("id") in section_ids]

        understanding = ctx.understanding
        output_format = ctx.output_format
        skill_context = build_skill_context(
            filter_skills_for_phase(ctx.skills, "spec_gen")
        )

        # P3-B: Pre-build invariant components once; all section generators share them.
        self._cached_skill_context = skill_context
        self._cached_intent_rules = _build_intent_rules(
            intent=understanding.get("intent", "fresh"),
            tense=understanding.get("tense", "present"),
            style=understanding.get("style", "report"),
            template_match="",  # section-specific part injected per call
        )

        is_pptx = output_format in ("pptx", "ppt", "powerpoint")
        is_xlsx = output_format in ("xlsx", "excel", "xls")

        if is_pptx:
            # P1-A: PPTX slides generated SEQUENTIALLY with rolling assertion context.
            # Each slide receives a list of already-asserted titles so it cannot
            # contradict prior slides or repeat the same conclusion.
            slide_specs: list[PptxSlideSpec] = []
            slide_summaries: list[str] = []  # assertion_title of completed slides
            pptx_total = len(sections)
            for i, s in enumerate(sections):
                slide_spec = await self._gen_slide_spec(
                    s, understanding, skill_context,
                    rolling_context=slide_summaries,
                    slide_position=(i + 1, pptx_total),
                )
                slide_specs.append(slide_spec)
                # R17-P2: Include position tag in rolling context so each slide knows
                # where in the deck the previous slide appeared, enabling
                # narrative-aware continuity (don't conclude in slide 2 of 15).
                slide_summaries.append(
                    f"[{i + 1}/{pptx_total}] 「{slide_spec.assertion_title}」"
                )

                # P1-1: Update global numeric_entity_map from this slide's text so
                # later slides and the chart consistency pass share the same ledger.
                slide_text = slide_spec.assertion_title + " " + " ".join(slide_spec.bullets or [])
                for _m in _RE_NUMERIC_ENTITY.finditer(slide_text):
                    _metric, _val = _m.group(1), _m.group(2) + (_m.group(3) or "")
                    if _metric not in self._numeric_entity_map:
                        self._numeric_entity_map[_metric] = _val

                if ctx.progress_callback:
                    try:
                        await ctx.progress_callback({
                            "phase": "SPEC_GEN",
                            "section_id": s.get("id"),
                            "completed": i + 1,
                            "total": pptx_total,
                        })
                    except Exception:
                        pass

            # P3-2: Post-process speaker_notes to ensure narrative transitions.
            # If slide N's notes don't mention "下页"/"接下来", append a bridge sentence
            # that points to slide N+1's assertion_title.
            slide_specs = _fix_speaker_notes_transitions(slide_specs)

            # R18-PPTX: Global layout sanity pass — correct impossible layout/content combos
            # that sometimes slip through when LLM ignores layout constraints (e.g., a
            # section_header slide that has bullet content, or a big_number slide with no
            # digit in the assertion_title).
            slide_specs = _fix_pptx_layout_sanity(slide_specs)

            # P1-1: PPTX chart numeric consistency pass.
            # After all slides are built we have _numeric_entity_map populated from
            # sequential slide generation.  Scan each slide's chart series for values
            # that contradict the global map and patch them in-place.
            slide_specs = _patch_chart_values_from_entity_map(slide_specs, self._numeric_entity_map)

            spec = PptxSpec(
                title=outline.get("title", ctx.brief[:60]),
                slides=slide_specs,
            )
        elif is_xlsx:
            # P3-3: XLSX sheets are independent — parallel but rate-limited.
            # Semaphore(4) prevents overwhelming the LLM API when there are
            # many sheets (e.g. 10+ sheet Excel workbooks).
            _sem = asyncio.Semaphore(4)

            async def _guarded_sheet(s):
                async with _sem:
                    return await self._gen_sheet_spec(s, understanding, skill_context)

            sheet_specs = await asyncio.gather(*[_guarded_sheet(s) for s in sections])
            spec = XlsxSpec(
                title=outline.get("title", ctx.brief[:60]),
                sheets=list(sheet_specs),
            )
        else:
            # P1-3: DOCX sections generated SEQUENTIALLY with rolling context so
            # later sections are aware of what was already written, preventing
            # cross-section repetition and numeric inconsistency.
            section_specs: list[DocxSectionSpec] = []
            completed_summaries: list[str] = []
            total = len(sections)
            for i, s in enumerate(sections):
                # P1-6: Pass next section title so LLM can write a proper transition sentence.
                next_sec_title = sections[i + 1].get("title", "") if i + 1 < total else None
                sec_spec = await self._gen_section_spec(
                    s, understanding, skill_context,
                    rolling_context=completed_summaries,
                    next_section_title=next_sec_title,
                )
                section_specs.append(sec_spec)

                # P1-C: Build a rich summary so next sections can avoid repetition
                # and reference numeric/structural data already written.
                summary = _build_section_summary(s.get("title", ""), sec_spec)
                completed_summaries.append(summary)

                # P1-3: Update global numeric entity map with numbers from this section.
                # Regex extracts label+value pairs (e.g. "营收50亿", "增长率30%") to build
                # a global ledger that later sections read to avoid contradictions.
                combined = " ".join(sec_spec.paragraphs + sec_spec.bullets)
                for m in _RE_NUMERIC_ENTITY.finditer(combined):
                    metric = m.group(1)
                    val = m.group(2) + (m.group(3) or "")
                    if metric not in self._numeric_entity_map:
                        self._numeric_entity_map[metric] = val

                # P2-F: Checkpoint each completed section spec to scoping_plan
                # so a crash mid-generation can be recovered from on resume.
                try:
                    scoping = dict(ctx.report.scoping_plan or {})
                    progress = scoping.get("spec_progress", {})
                    progress[s.get("id", f"s{i}")] = sec_spec.model_dump()
                    scoping["spec_progress"] = progress
                    ctx.report.scoping_plan = scoping
                    await ctx.db.commit()
                except Exception as _cp_exc:
                    logger.debug("[SpecGen] Checkpoint commit failed (non-fatal): %s", _cp_exc)

                # P2-2 + P3-C: Broadcast per-section progress AND a content preview so
                # clients can stream partial document content as sections complete.
                if ctx.progress_callback:
                    try:
                        # Build a lightweight text preview from the completed spec
                        preview_lines: list[str] = [f"## {sec_spec.title}"]
                        preview_lines.extend(sec_spec.paragraphs)
                        preview_lines.extend(f"• {b}" for b in sec_spec.bullets)
                        if sec_spec.chart:
                            preview_lines.append(f"【图表】{sec_spec.chart.title}（{sec_spec.chart.chart_type}）")
                        await ctx.progress_callback({
                            "phase": "SPEC_GEN",
                            "section_id": s.get("id"),
                            "section_title": sec_spec.title,
                            "completed": i + 1,
                            "total": total,
                            "natural_message": _section_spec_summary(sec_spec, i + 1, total),
                            "section_preview": "\n".join(preview_lines),
                        })
                    except Exception:
                        pass

            # Merge into existing spec for QA re-generation (section_ids path)
            if ctx.spec and section_ids:
                existing = {s.id: s for s in ctx.spec.sections}
                for new_sec in section_specs:
                    existing[new_sec.id] = new_sec
                # P1-5: Restore original outline order — dict.values() alone does
                # not guarantee the outline section sequence after partial updates.
                outline_order = [s.get("id") for s in ctx.outline.get("sections", [])]
                ordered = [existing[sid] for sid in outline_order if sid in existing]
                # Append any sections not in outline (shouldn't happen, but be safe)
                ordered += [s for s in existing.values() if s.id not in outline_order]
                spec = DocxSpec(
                    title=ctx.spec.title,
                    style=ctx.spec.style,
                    tense=ctx.spec.tense,
                    sections=ordered,
                    metadata=ctx.spec.metadata,
                )
            else:
                document_standard = get_document_standard(ctx.report_type, ctx.brief)
                spec = DocxSpec(
                    title=outline.get("title", ctx.brief[:60]),
                    style=understanding.get("style", "report"),
                    tense=understanding.get("tense", "present"),
                    sections=list(section_specs),
                    metadata={"document_standard": document_standard} if document_standard else {},
                )

        ctx.spec = spec

        # P1-2 / P2-5: Propagate degradation warnings to context
        if self._has_warnings:
            ctx.completed_with_warnings = True
            logger.warning("[SpecGen] Completed with warnings — some sections used placeholder text")
            # Store failed section IDs in scoping_plan so QA can detect and escalate them
            try:
                scoping = dict(ctx.report.scoping_plan or {})
                scoping["failed_section_ids"] = self._failed_section_ids
                ctx.report.scoping_plan = scoping
                await ctx.db.commit()
            except Exception:
                pass

        # P2-F / P3-1: Persist completed spec JSON so revise-section and crash-recovery can use it.
        # R18-NUM: Also persist doc_numeric_freeze so downstream QA and export can cross-check
        # that all numeric entities in the final doc match the values first committed in spec_gen.
        try:
            scoping = dict(ctx.report.scoping_plan or {})
            scoping["spec_json"] = spec.model_dump()
            scoping.pop("spec_progress", None)  # Full spec supersedes partial progress
            if self._numeric_entity_map:
                scoping["doc_numeric_freeze"] = dict(self._numeric_entity_map)
            ctx.report.scoping_plan = scoping
            await ctx.db.commit()
        except Exception as _spec_exc:
            logger.debug("[SpecGen] spec_json persist failed (non-fatal): %s", _spec_exc)

    # ── DOCX section ─────────────────────────────────────────────────────────

    async def _gen_section_spec(
        self,
        section: dict,
        understanding: dict,
        skill_context: str,
        rolling_context: list[str] | None = None,
        next_section_title: str | None = None,
    ) -> DocxSectionSpec:
        section_id = section.get("id", "s?")
        section_title = section.get("title", section_id)
        prior_errors: list[str] = []

        # P2-1 / R17-P1: Extended self-consistency — trigger on:
        # 1. Key Chinese section keywords (executive-level summaries)
        # 2. Long sections (target_chars >= 600) — more content can diverge
        # 3. Evidence-rich sections (len(evidence) > 800) — factual accuracy matters most
        #    when substantial research material exists; 2-candidate ensures the better
        #    grounded version wins rather than the first LLM response.
        _KEY_SECTION_KWS = {"摘要", "核心发现", "总结", "执行摘要", "关键结论", "核心洞察"}
        target_chars = section.get("target_chars", 400)
        evidence_for_section = self.ctx.research_findings.get(section_id, "")
        if (any(kw in section_title for kw in _KEY_SECTION_KWS)
                or target_chars >= 600
                or len(evidence_for_section) > 800):
            try:
                return await self._gen_section_with_consistency(
                    section, understanding, skill_context, rolling_context,
                    next_section_title=next_section_title,
                )
            except Exception as exc:
                logger.warning("[SpecGen] Self-consistency failed for '%s', falling back: %s", section_title, exc)

        for attempt in range(1, MAX_SECTION_RETRIES + 1):
            messages = self._build_docx_section_messages(
                section, understanding, prior_errors, skill_context,
                rolling_context=rolling_context,
                next_section_title=next_section_title,
            )
            try:
                raw = await call_llm_json(messages, temperature=0.35, max_tokens=3000, tier="standard")
                # Inject id and title from outline if missing (LLM sometimes drops them)
                raw.setdefault("id", section_id)
                raw.setdefault("title", section_title)
                raw.setdefault("template_heading_match", section.get("template_heading_match"))
                sec_spec = DocxSectionSpec.model_validate(raw)
                # P2-3: Apply chart type rules engine post-validation
                sec_spec = _apply_chart_type_rules(sec_spec)
                sec_spec = self._ensure_docx_chart(sec_spec, section, evidence_for_section)
                # R17-P2: Bullet→paragraph promotion for speech-style docs.
                # When style='speech' and content_type='paragraphs', the LLM sometimes
                # returns only bullets despite instructions. Merge them into a prose
                # paragraph so the rendered document reads as continuous narrative.
                sec_spec = _promote_bullets_to_paragraphs(
                    sec_spec, understanding.get("style", "report")
                )
                # P2-B: LLM-as-Judge — fast advisory check on first attempt only
                if attempt == 1:
                    critique = await self._review_docx_section(sec_spec, section)
                    if critique:
                        prior_errors.append(f"自审发现问题（请修正）：{critique}")
                        if len(prior_errors) < MAX_SECTION_RETRIES:
                            await asyncio.sleep(0.2)
                            continue  # Retry with critique injected into prior_errors
                return sec_spec
            except (ValidationError, Exception) as exc:
                error_msg = str(exc)
                prior_errors.append(f"Attempt {attempt}: {error_msg}")
                logger.warning(
                    "[SpecGen] section '%s' attempt %d/%d failed: %s",
                    section_id, attempt, MAX_SECTION_RETRIES, error_msg[:200],
                )
                if attempt < MAX_SECTION_RETRIES:
                    await asyncio.sleep(0.3)

        # P1-2 / P2-5: Degrade gracefully — placeholder instead of pipeline failure.
        # Record the section_id so QA can surface this as a P1 issue.
        logger.error(
            "[SpecGen] Section '%s' failed after %d retries — inserting placeholder",
            section_title, MAX_SECTION_RETRIES,
        )
        self._has_warnings = True
        self._failed_section_ids.append(section_id)
        return DocxSectionSpec(
            id=section_id,
            title=section_title,
            template_heading_match=section.get("template_heading_match"),
            content_type="paragraphs",
            paragraphs=[f"[本章节「{section_title}」内容生成失败，请手动补充。]"],
            target_chars=section.get("target_chars", 400),
        )

    async def _gen_section_with_consistency(
        self,
        section: dict,
        understanding: dict,
        skill_context: str,
        rolling_context: list[str] | None,
        next_section_title: str | None = None,
    ) -> DocxSectionSpec:
        """P3-3: Generate 2 candidates for key sections, pick best via LLM judge."""
        section_id = section.get("id", "s?")
        candidates: list[DocxSectionSpec] = []
        for _ in range(2):
            try:
                messages = self._build_docx_section_messages(
                    section, understanding, [], skill_context, rolling_context,
                    next_section_title=next_section_title,
                )
                raw = await call_llm_json(messages, temperature=0.5, max_tokens=3000, tier="standard")
                raw.setdefault("id", section_id)
                raw.setdefault("title", section.get("title", section_id))
                raw.setdefault("template_heading_match", section.get("template_heading_match"))
                spec = DocxSectionSpec.model_validate(raw)
                spec = _apply_chart_type_rules(spec)
                spec = self._ensure_docx_chart(spec, section, self.ctx.research_findings.get(section_id, ""))
                spec = _promote_bullets_to_paragraphs(spec, understanding.get("style", "report"))
                candidates.append(spec)
            except Exception:
                pass

        if not candidates:
            raise RuntimeError("No candidates generated")
        if len(candidates) == 1:
            return candidates[0]

        # Judge: pick more substantive candidate
        try:
            c0 = " ".join(candidates[0].paragraphs[:3] + candidates[0].bullets[:3])
            c1 = " ".join(candidates[1].paragraphs[:3] + candidates[1].bullets[:3])
            result = await call_llm_json(
                messages=[
                    {
                        "role": "system",
                        "content": "你是内容质量评审员。选择更好的版本（更完整、洞察更深、数字更准确）。只输出JSON。",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"版本A：{c0[:600]}\n\n版本B：{c1[:600]}\n\n"
                            '请输出：{"best": "A"} 或 {"best": "B"}'
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=50,
                fallback={"best": "A"},
                tier="standard",
            )
            return candidates[1] if result.get("best") == "B" else candidates[0]
        except Exception:
            return candidates[0]

    async def _review_docx_section(self, spec: "DocxSectionSpec", section: dict) -> str:
        """P2-B: LLM-as-Judge for DOCX section — returns critique string or '' if OK."""
        evidence = self.ctx.research_findings.get(section.get("id", ""), "")
        if not evidence:
            return ""
        # Only check sections with numeric content (expensive call, skip if nothing to verify)
        content_sample = " ".join(spec.paragraphs[:2] + spec.bullets[:2])[:800]
        if not _RE_DIGIT.search(content_sample):
            return ""
        try:
            result = await call_llm_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是内容真实性审核员。检查以下章节内容中的数字是否在证据材料中可以找到依据。"
                            "只输出JSON：{\"ok\": true} 或 {\"ok\": false, \"critique\": \"简短问题描述（≤60字）\"}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"章节内容：{content_sample}\n\n"
                            f"证据材料（节选）：{evidence[:1500]}"
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=200,
                fallback={"ok": True},
                tier="standard",
            )
            if not result.get("ok"):
                return result.get("critique", "包含未经证据支持的数字")
        except Exception:
            pass
        return ""

    def _ensure_docx_chart(
        self,
        spec: DocxSectionSpec,
        section: dict,
        evidence: str,
    ) -> DocxSectionSpec:
        """Guarantee chart output for sections marked by PLAN as visual sections."""
        if spec.chart is not None:
            return spec
        if not _section_requires_chart(section, self.ctx.brief, self.ctx.report_type, self.ctx.output_format, evidence):
            return spec
        chart = _fallback_chart_for_section(section, spec, evidence, self.ctx.uploaded_texts)
        if chart is None:
            return spec
        return _apply_chart_type_rules(spec.model_copy(update={"chart": chart, "content_type": "mixed"}))

    def _build_docx_section_messages(
        self,
        section: dict,
        understanding: dict,
        prior_errors: list[str],
        skill_context: str,
        rolling_context: list[str] | None = None,
        next_section_title: str | None = None,
    ) -> list[dict]:
        intent = understanding.get("intent", "fresh")
        tense = understanding.get("tense", "present")
        style = understanding.get("style", "report")
        numeric_baseline = self.ctx.understanding.get("numeric_baseline", {})
        section_id = section.get("id", "s?")
        section_title = section.get("title", "")
        key_points = section.get("key_points", [])
        target_chars = section.get("target_chars", 400)
        template_match = section.get("template_heading_match", "")
        evidence = self.ctx.research_findings.get(section_id, "")
        standard_note = format_standard_for_prompt(
            get_document_standard(self.ctx.report_type, self.ctx.brief)
        )

        # P2-2: Build QA feedback for this section.
        # Includes both section-specific issues AND global issues (section_id=None),
        # e.g. hallucination_numbers which affect the whole document but are not
        # pinned to a single section.  Global issues are prepended at lower priority.
        qa_notes = ""
        if self.qa_feedback:
            section_issues = [f for f in self.qa_feedback if f.get("section_id") == section_id]
            global_issues = [f for f in self.qa_feedback
                             if not f.get("section_id") and f.get("severity") in ("p0", "p1")]
            all_relevant = section_issues + [g for g in global_issues if g not in section_issues]
            if all_relevant:
                issues_text = "\n".join(f"- {f.get('message', '')}" for f in all_relevant[:6])
                qa_notes = f"\n\n【QA反馈 — 上一轮以下问题必须修复】\n{issues_text}"

        # P3-B: Use pre-built (cached) intent rules; only the section-specific
        # template_match suffix is appended here so the rest is invariant.
        intent_rules = self._cached_intent_rules
        if template_match:
            intent_rules += f"\n本章节对应参考文档标题：'{template_match}'"

        # P1-4: Entity registry — canonical names/units must be used consistently
        entity_registry = self.ctx.understanding.get("entity_registry", {})
        entity_block = ""
        if entity_registry:
            items_text = "\n".join(
                f"  - {name}（类型：{v.get('type', '')}，单位：{v.get('unit', '无')}）"
                for name, v in list(entity_registry.items())[:15]
            )
            entity_block = f"\n\n【实体规范表（使用这些名称时必须保持一致，不得随意缩写或改变）】\n{items_text}"

        # Baseline block
        baseline_block = ""
        if numeric_baseline and intent in ("fill_from_reference", "extend"):
            top_items = list(numeric_baseline.items())[:10]
            items_text = "\n".join(
                f"  - {k}（数值：{', '.join(str(n) for n in v.get('numbers', []))}，来源：{v.get('source', '')}）"
                for k, v in top_items
            )
            baseline_block = f"\n\n【参考数值基线（只能引用，不能凭空捏造）】\n{items_text}"

        # P1-1: Evidence block — dynamic limit aligned with research.py budget.
        # target_chars * 4 matches the retrieval budget formula (target * 3) with
        # a small margin; floor 3000 so short sections still get enough context.
        evidence_limit = max(3000, min(8000, target_chars * 4))
        evidence_block = f"\n\n【本章节研究材料】\n{evidence[:evidence_limit]}" if evidence else ""
        chart_block = _build_docx_chart_instruction(section, evidence, self.ctx.uploaded_texts)

        # LLM-OS: 注入 DuckDB Schema + VFS 目录树 + 模板占位符
        llmos_block = ""
        if self.ctx.duckdb_schema:
            llmos_block += f"\n\n【可用数据表 Schema（可在 chart 中引用列名）】\n{self.ctx.duckdb_schema[:800]}"
        if self.ctx.vfs_tree:
            llmos_block += f"\n\n【上传工程目录树】\n{self.ctx.vfs_tree[:600]}"
        if self.ctx.template_meta:
            meta = self.ctx.template_meta
            placeholders = list(meta.to_variable_map().keys())[:10]
            llmos_block += f"\n\n【模板占位符（严格对应填充，不得遗漏）】\n{', '.join(placeholders)}"

        # P1-3: Rolling context — keep last 5 to avoid prompt bloat
        rolling_block = ""
        if rolling_context:
            items = "\n".join(rolling_context[-5:])
            rolling_block = (
                f"\n\n【已完成章节概要（本章节禁止重复以下内容，须与其逻辑衔接）】\n{items}"
            )

        # P1-3: Global numeric entity map — inject ALL metrics seen so far (not just last 5).
        # This ensures later sections cannot contradict earlier numbers regardless of position.
        numeric_map_block = ""
        if self._numeric_entity_map:
            top_items = list(self._numeric_entity_map.items())[:20]
            nums_text = "、".join(f"{k}={v}" for k, v in top_items)
            numeric_map_block = (
                f"\n\n【全文数字一致性约束（以下数字已在前序章节确认，本章节引用时必须完全一致）】\n{nums_text}"
            )

        # Prior errors injected verbatim — full constraints maintained
        error_block = ""
        if prior_errors:
            errors_text = "\n".join(f"  {e}" for e in prior_errors)
            error_block = f"\n\n【前几次生成失败的原因（请避免重蹈）】\n{errors_text}"

        # Schema example
        schema_example = _DOCX_SECTION_SCHEMA_EXAMPLE

        # P3-B: Invariant prefix is built once per run() and cached on self.
        # Section-variable parts (template_match, errors) are in user_content only.
        cached_skill = self._cached_skill_context
        system_prompt = (
            "你是专业文档内容生成专家。根据章节规格和研究材料，生成符合JSON schema的章节内容规格。\n"
            "除非用户明确要求英文，否则必须使用中文撰写所有标题、正文、摘要、关键词、表格、图注和总结；不要中英文混杂。\n"
            "只输出JSON对象，不附加任何解释文字。\n\n"
            + intent_rules
            + "\n\n输出必须是以下格式的JSON对象：\n"
            + schema_example
            + "\n\n字段说明：\n"
            "- id: 章节ID，必须与输入一致\n"
            "- title: 章节标题\n"
            "- template_heading_match: 参考文档中对应的原始标题（如有，请原样填入）\n"
            "- content_type: \"paragraphs\" | \"bullets\" | \"table\" | \"mixed\"\n"
            "- paragraphs: 散文段落列表（每段50-200字）\n"
            "- bullets: 要点列表（每条20-80字）\n"
            "- table: 表格（可选）\n"
            "- chart: 图表规格（可选；当章节标记为需要图表或材料含可视化数据时必须添加，不要只写文字）\n"
            "- subsections: 二级子章节列表（可选，每项与本章节格式相同）\n"
            "- target_chars: 目标字符数\n"
            "- style_note: 内容风格备注\n"
            "- evidence_ids: 列表，从【本章节研究材料】的标签行提取来源名称。\n"
            "  规则：扫描材料中「来源：[xxx]」或「文件名：xxx」等行，取其中 xxx 部分。\n"
            "  若材料标签为【上传文档内容】，则取上传文件名；若为【知识库检索结果】，取「来源：」后的名称。\n"
            "  最多5项，无可识别来源时输出空列表 []。\n"
            "  示例：[\"年度报告2024.docx\", \"财务数据表.xlsx\", \"Q3研究报告\"]\n\n"
            "【P3-1 章节过渡句规则】\n"
            "当本章节不是最后一章时，paragraphs 的最后一段结尾须用1句话预告下一章节主题，\n"
            "例如：「下一部分将从……角度深入分析……」\n"
            "若本章节是文档最后一章，则最后一段须为总结收尾句，不用预告。"
            "\n\n【图表生成硬规则】\n"
            "遇到趋势、对比、分布、构成、实验结果、性能评估、消融实验、Excel/CSV 数值统计时，必须主动生成 chart 字段。"
            "chart 是后端 Python（Matplotlib/Plotly/PIL）生成图片并插入 Word 的唯一输入：labels 与每个 series.values 长度必须一致，数据必须来自研究材料、上传表格或正文已说明的可审计依据。"
            "复杂场景优先使用 combo、heatmap、stacked_bar、scatter 等复合/专业图表；图题、图注和来源说明必须使用中文。"
            + (f"\n\n{standard_note}" if standard_note else "")
            + (f"\n\n以下是你必须遵循的写作规范（Skill）：\n{cached_skill}" if cached_skill else "")
        )

        # P3-B: Mark system message as cacheable for models supporting cache_control.
        system_message: dict = {"role": "system", "content": system_prompt}
        try:
            system_message["cache_control"] = {"type": "ephemeral"}
        except Exception:
            pass

        # P1-6: Lookahead — tell LLM what comes next so it can write a proper transition.
        lookahead_note = ""
        if next_section_title:
            lookahead_note = (
                f"\n\n【下一章节预告】下一章节标题为「{next_section_title}」。"
                "本章节 paragraphs 的最后一段结尾必须用1句话自然引出下一章节主题，"
                f"例如：「下一部分将深入探讨{next_section_title[:15]}的具体情况。」"
            )
        elif not next_section_title and next_section_title is not None:
            # next_section_title was explicitly passed as "" — this is the last section
            lookahead_note = (
                "\n\n【本章节是文档最后一章】paragraphs 最后一段须为整体总结收尾句，不用预告下一章节。"
            )

        brief = self.ctx.brief or ""
        user_content = (
            "请生成以下章节的内容规格JSON：\n\n"
            f"【全局需求（必须贯穿所有章节）】{brief[:400]}\n\n"
            f"章节ID: {section_id}\n"
            f"章节标题: {section_title}\n"
            f"内容类型提示: {section.get('content_type', 'paragraphs')}\n"
            f"目标字符数: {target_chars}\n"
            "关键要点（必须覆盖）:\n"
            + ("\n".join(f"- {kp}" for kp in key_points) if key_points else "（由你根据材料提炼）")
            + rolling_block
            + numeric_map_block
            + entity_block
            + baseline_block
            + llmos_block
            + evidence_block
            + chart_block
            + lookahead_note
            + error_block
            + qa_notes
            + "\n\n请直接输出JSON对象，以 { 开始，以 } 结束。"
        )

        return [
            system_message,
            {"role": "user", "content": user_content},
        ]

    # ── PPTX slide ────────────────────────────────────────────────────────────

    async def _gen_slide_spec(
        self,
        section: dict,
        understanding: dict,
        skill_context: str,
        rolling_context: list[str] | None = None,
        slide_position: tuple[int, int] | None = None,
    ) -> PptxSlideSpec:
        section_id = section.get("id", "slide?")
        prior_errors: list[str] = []

        # P1-3: Self-consistency sampling for high-stakes PPTX slide layouts.
        # big_number and comparison slides present key KPIs — generating 2 candidates
        # and picking the more data-dense one materially improves accuracy.
        layout_hint = section.get("layout_hint", "content")
        if layout_hint in ("big_number", "comparison"):
            try:
                return await self._gen_slide_with_consistency(
                    section, understanding, skill_context, rolling_context,
                    slide_position=slide_position,
                )
            except Exception as exc:
                logger.warning("[SpecGen] Slide consistency failed for '%s', falling back: %s",
                               section_id, exc)

        for attempt in range(1, MAX_SECTION_RETRIES + 1):
            messages = self._build_pptx_slide_messages(
                section, understanding, prior_errors, skill_context,
                rolling_context=rolling_context,
                slide_position=slide_position,
            )
            try:
                raw = await call_llm_json(messages, temperature=0.35, max_tokens=2000, tier="standard")
                raw.setdefault("id", section_id)
                if not raw.get("assertion_title"):
                    raw["assertion_title"] = section.get("title", section_id)
                spec = PptxSlideSpec.model_validate(raw)
                # P2-3: Apply chart type rules engine
                spec = _apply_chart_type_rules(spec)
                # P2-1: big_number layout must have a digit in assertion_title.
                # If the LLM used a non-numeric title (e.g. "市场前景展望"), the
                # big_number layout produces an empty highlight box.  Downgrade to
                # "content" layout so the slide renders correctly rather than blank.
                if spec.layout == "big_number" and not _RE_DIGIT.search(spec.assertion_title):
                    logger.warning(
                        "[SpecGen] big_number slide '%s' has no digit in title — "
                        "downgrading layout to 'content'", spec.id,
                    )
                    spec = spec.model_copy(update={"layout": "content"})
                # P1-4: speaker_notes sentence count warning
                if spec.speaker_notes:
                    n_sentences = len(_re.findall(r"[。！？.!?]", spec.speaker_notes))
                    if n_sentences < 2:
                        logger.warning(
                            "[SpecGen] Slide '%s' speaker_notes has only %d sentence(s) "
                            "(expected 3-sentence structure)",
                            spec.id, n_sentences,
                        )
                # P2-B: LLM-as-Judge self-review (fast pass)
                if attempt == 1:
                    await self._review_slide_spec(spec, section)
                return spec
            except (ValidationError, Exception) as exc:
                error_msg = str(exc)
                prior_errors.append(f"Attempt {attempt}: {error_msg}")
                logger.warning("[SpecGen] slide '%s' attempt %d failed: %s", section_id, attempt, error_msg[:200])
                if attempt < MAX_SECTION_RETRIES:
                    await asyncio.sleep(0.3)

        raise PipelineError(
            phase=self.PHASE_NAME,
            message=f"无法生成幻灯片 '{section.get('title', section_id)}' 规格，已重试 {MAX_SECTION_RETRIES} 次。",
            section_id=section_id,
        )

    async def _gen_slide_with_consistency(
        self,
        section: dict,
        understanding: dict,
        skill_context: str,
        rolling_context: list[str] | None,
        slide_position: tuple[int, int] | None = None,
    ) -> PptxSlideSpec:
        """P1-3: Generate 2 candidates for big_number/comparison slides, pick best via LLM judge.

        These layout types present headline KPIs — getting the most accurate, data-rich
        version matters most.  Mirrors _gen_section_with_consistency for DOCX.
        """
        section_id = section.get("id", "slide?")
        candidates: list[PptxSlideSpec] = []

        for _ in range(2):
            try:
                messages = self._build_pptx_slide_messages(
                    section, understanding, [], skill_context,
                    rolling_context=rolling_context,
                    slide_position=slide_position,
                )
                raw = await call_llm_json(messages, temperature=0.5, max_tokens=2000, tier="standard")
                raw.setdefault("id", section_id)
                if not raw.get("assertion_title"):
                    raw["assertion_title"] = section.get("title", section_id)
                spec = PptxSlideSpec.model_validate(raw)
                spec = _apply_chart_type_rules(spec)
                candidates.append(spec)
            except Exception:
                pass

        if not candidates:
            raise RuntimeError("No slide candidates generated")
        if len(candidates) == 1:
            return candidates[0]

        # Judge: pick the candidate with more numeric evidence in assertion_title
        def _digit_density(s: PptxSlideSpec) -> float:
            text = s.assertion_title + " " + " ".join(s.bullets or [])
            nums = _RE_ALL_DIGITS.findall(text)
            return len(nums) / max(len(text), 1)

        d0, d1 = _digit_density(candidates[0]), _digit_density(candidates[1])
        if abs(d0 - d1) > 0.005:
            return candidates[0] if d0 >= d1 else candidates[1]

        # Tie-break with LLM judge
        try:
            c0_text = candidates[0].assertion_title + " | " + " ".join(candidates[0].bullets[:3])
            c1_text = candidates[1].assertion_title + " | " + " ".join(candidates[1].bullets[:3])
            result = await call_llm_json(
                messages=[
                    {"role": "system",
                     "content": "选择数据更准确、断言更具体的幻灯片版本。只输出JSON。"},
                    {"role": "user",
                     "content": (
                         f"版本A：{c0_text[:400]}\n\n版本B：{c1_text[:400]}\n\n"
                         '请输出：{"best": "A"} 或 {"best": "B"}'
                     )},
                ],
                temperature=0.1, max_tokens=50, fallback={"best": "A"}, tier="standard",
            )
            return candidates[1] if result.get("best") == "B" else candidates[0]
        except Exception:
            return candidates[0]

    async def _review_slide_spec(self, spec: "PptxSlideSpec", section: dict) -> None:
        """P2-B: Fast LLM-as-Judge pass for PPTX slide — checks invented numbers."""
        evidence = self.ctx.research_findings.get(section.get("id", ""), "")
        if not evidence:
            return  # No evidence to check against
        try:
            review_messages = [
                {
                    "role": "system",
                    "content": (
                        "你是内容审核专家。检查幻灯片规格中的数字是否在提供的证据材料中有依据。"
                        "只输出JSON：{\"ok\": true} 或 {\"ok\": false, \"issues\": [\"问题描述\"]}"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"幻灯片标题：{spec.assertion_title}\n"
                        f"要点：{spec.bullets}\n\n"
                        f"证据材料（节选）：{evidence[:1500]}"
                    ),
                },
            ]
            result = await call_llm_json(
                review_messages, temperature=0.1, max_tokens=300,
                fallback={"ok": True}, tier="standard",
            )
            if not result.get("ok"):
                issues = result.get("issues", [])
                logger.warning(
                    "[SpecGen-Judge] Slide '%s' critique: %s",
                    spec.assertion_title, issues
                )
        except Exception:
            pass  # Judge is advisory; never block generation

    def _build_pptx_slide_messages(
        self,
        section: dict,
        understanding: dict,
        prior_errors: list[str],
        skill_context: str,
        rolling_context: list[str] | None = None,
        slide_position: tuple[int, int] | None = None,
    ) -> list[dict]:
        section_id = section.get("id", "slide?")
        section_title = section.get("title", "")
        key_points = section.get("key_points", [])
        layout_hint = section.get("layout_hint", "content")
        evidence = self.ctx.research_findings.get(section_id, "")

        error_block = ""
        if prior_errors:
            errors_text = "\n".join(f"  {e}" for e in prior_errors)
            error_block = f"\n\n【前几次生成失败的原因】\n{errors_text}"

        # P1-A: Rolling context — show prior slide assertion titles to enforce narrative arc
        rolling_block = ""
        if rolling_context:
            prior = "\n".join(f"  · {t}" for t in rolling_context[-6:])
            rolling_block = (
                f"\n\n【已完成幻灯片（断言标题汇总，本页须与上述形成递进/对比逻辑，"
                f"禁止重复相同断言或数字）】\n{prior}"
            )

        # P2-1: Layout decision tree — injected into every slide prompt so the LLM
        # follows a deterministic rule rather than guessing layout freely.
        layout_rules = (
            "\n\n【版式选择规则（必须严格遵守，不得随意选 content）】\n"
            "1. layout = 'big_number'   → 条件：本页核心是单个 KPI 指标或里程碑数字（如营收50亿、增长率30%）\n"
            "2. layout = 'comparison'   → 条件：本页有两个对比项（如A方案 vs B方案、同比 vs 环比）\n"
            "3. layout = 'section_header' → 条件：本页是章节/部分过渡页（无具体数据），bullets=[]\n"
            "4. layout = 'content'      → 其余所有情况（含列表、图表、混合内容）\n"
            "当前页 layout_hint=" + repr(layout_hint) + "，如与上述规则冲突，以规则为准。\n"
        )
        if layout_hint == "section_header":
            layout_rules += (
                "【补充：section_header 专用规则】\n"
                "assertion_title 写章节主题名（不含断言数字），bullets=[]，不添加 chart/table。"
            )
        else:
            layout_rules += (
                "【补充】assertion_title 必须包含具体数字或明确判断（≤22字）。"
            )

        schema_example = _PPTX_SLIDE_SCHEMA_EXAMPLE

        # P3-2: speaker_notes structured template — 3-sentence format for consistency
        speaker_notes_rule = (
            "\n4. speaker_notes：严格按以下3句式结构输出（总字数100-200字）：\n"
            "   第1句：「本页核心是[结论]。」——点明幻灯片最重要的一个结论。\n"
            "   第2句：补充幻灯片中未显示的背景信息、数据来源或前因后果（≥40字）。\n"
            "   第3句：「下页将[下一主题]…」——自然衔接下一张幻灯片（最后一页改为总结句）。\n"
            "   禁止：仅复述标题、空洞表达（如「非常重要」）、超出200字。"
        )

        # P1-4: Entity registry
        entity_registry = self.ctx.understanding.get("entity_registry", {})
        entity_block = ""
        if entity_registry:
            entity_items = "\n".join(
                f"  - {name}（{v.get('type', '')}，单位：{v.get('unit', '无')}）"
                for name, v in list(entity_registry.items())[:10]
            )
            entity_block = f"\n\n【实体规范（名称与单位须与下表一致）】\n{entity_items}"

        # P2-4: Inject template DNA into the slide prompt so the LLM can adapt
        # content style to the visual design (dark theme → short punchy text, etc.)
        dna_note = ""
        template_dna = self.ctx.understanding.get("template_dna", {})
        if template_dna:
            accent = template_dna.get("accent_hex", "")
            font = template_dna.get("font_name", "")
            is_dark = _is_dark_color(accent)
            dna_note = (
                f"\n\n【模板视觉风格】主色调 #{accent}"
                + ("（深色背景，文字宜简短有力，避免大段文本）" if is_dark else "（浅色背景，可适当展示数据段落）")
                + (f"，字体：{font}" if font else "")
            )

        system_prompt = (
            "你是PPT内容规格专家。根据幻灯片主题和研究材料，生成符合JSON schema的幻灯片内容规格。\n"
            "只输出JSON对象，不附加任何解释文字。\n\n"
            "【核心规则】\n"
            "1. 如有数据支持，添加chart（否则省略）\n"
            "2. bullets 每条≤50字，content页3-5条，section_header页为空\n"
            "3. 只输出JSON对象，不要任何解释\n"
            + speaker_notes_rule
            + "\n\n输出格式示例：\n" + schema_example
            + (f"\n\n写作规范：\n{skill_context}" if skill_context else "")
            + layout_rules
            + entity_block
            + dna_note
        )

        # P1-1: Inject numeric_entity_map into PPTX prompts — same as DOCX path.
        # PPTX slides are generated sequentially and update the map, but previously
        # the map was never fed back into the prompt, so later slides could freely
        # contradict numbers established by earlier slides.
        pptx_numeric_block = ""
        if self._numeric_entity_map:
            top = list(self._numeric_entity_map.items())[:15]
            nums = "、".join(f"{k}={v}" for k, v in top)
            pptx_numeric_block = (
                f"\n\n【全文数字一致性约束（以下数字已在前序幻灯片确认，本页引用时必须完全一致）】\n{nums}"
            )

        # P1-2: Inject QA feedback into PPTX prompts — mirrors the DOCX path.
        # Previously PPTX re-runs ignored qa_feedback entirely.
        pptx_qa_notes = ""
        if self.qa_feedback:
            slide_issues = [f for f in self.qa_feedback if f.get("section_id") == section_id]
            global_issues = [f for f in self.qa_feedback
                             if not f.get("section_id") and f.get("severity") in ("p0", "p1")]
            all_relevant = slide_issues + [g for g in global_issues if g not in slide_issues]
            if all_relevant:
                issues_text = "\n".join(f"- {f.get('message', '')}" for f in all_relevant[:5])
                pptx_qa_notes = f"\n\n【QA反馈 — 上一轮以下问题必须修复】\n{issues_text}"

        # R17-P2: Deck position-aware narrative guidance.
        # Early slides establish context; middle slides build evidence; closing slides conclude.
        # Injecting the position prevents LLMs from writing a "conclusion" in slide 2 of 20,
        # or rehashing background in the final slide.
        position_note = ""
        if slide_position:
            cur, total = slide_position
            pct = cur / max(total, 1)
            if pct <= 0.20:
                phase_hint = (
                    f"开篇阶段（第 {cur}/{total} 张）：建立背景与问题，不要过早提出结论，"
                    "用数据或情境激发听众兴趣"
                )
            elif pct <= 0.70:
                phase_hint = (
                    f"展开阶段（第 {cur}/{total} 张）：呈现核心数据与分析，"
                    "每张幻灯片给出一个独立的、递进的论点"
                )
            else:
                phase_hint = (
                    f"收尾阶段（第 {cur}/{total} 张）：聚焦结论与行动建议，"
                    "引用前面幻灯片已建立的数据，不要引入新的主题"
                )
            position_note = f"\n\n【叙事位置】{phase_hint}"

        brief = self.ctx.brief or ""
        user_content = (
            f"【全局需求】{brief[:300]}\n\n"
            f"幻灯片ID: {section_id}\n"
            f"主题: {section_title}\n"
            f"版式: {layout_hint}\n"
            f"关键要点:\n"
            + (
                "\n".join(f"- {kp}" for kp in key_points)
                if key_points else "（自行提炼）"
            )
            + f"\n\n研究材料:\n{evidence[:2000] if evidence else '（无，请基于主题生成）'}"
            + rolling_block
            + pptx_numeric_block
            + position_note
            + pptx_qa_notes
            + error_block
            + "\n\n请直接输出JSON对象。"
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    # ── XLSX sheet ────────────────────────────────────────────────────────────

    async def _gen_sheet_spec(
        self,
        section: dict,
        understanding: dict,
        skill_context: str,
    ) -> XlsxSheetSpec:
        section_id = section.get("id", "sheet?")
        evidence = self.ctx.research_findings.get(section_id, "")
        prior_errors: list[str] = []

        for attempt in range(1, MAX_SECTION_RETRIES + 1):
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是数据分析专家。根据研究材料生成Excel工作表内容规格JSON。只输出JSON对象。\n"
                        "【动态公式指引】当数据量足够时，在 calculation_notes 中建议使用 Excel 动态数组函数：\n"
                        "- FILTER(范围, 条件)：筛选符合条件的行，替代手动复制粘贴\n"
                        "- SORT/SORTBY(范围, 排序列)：自动排序，确保排行榜数据动态更新\n"
                        "- UNIQUE(范围)：去重汇总，适合维度枚举\n"
                        "- XLOOKUP(查找值, 查找区域, 返回区域)：替代 VLOOKUP，支持向左查找\n"
                        "- SEQUENCE(行数, 列数)：生成序号列，配合 SORT 建立动态排名\n"
                        "这些函数无需在 table.rows 中枚举结果，仅在 calculation_notes 说明即可。"
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_xlsx_sheet_user_content(
                        section_id, section, evidence, prior_errors
                    ),
                },
            ]
            try:
                raw = await call_llm_json(messages, temperature=0.3, max_tokens=2000, tier="standard")
                raw.setdefault("id", section_id)
                raw.setdefault("name", section.get("title", section_id)[:31])
                return XlsxSheetSpec.model_validate(raw)
            except (ValidationError, Exception) as exc:
                prior_errors.append(str(exc))
                if attempt < MAX_SECTION_RETRIES:
                    await asyncio.sleep(0.3)

        raise PipelineError(
            phase=self.PHASE_NAME,
            message=f"无法生成工作表 '{section.get('title', section_id)}' 规格，已重试 {MAX_SECTION_RETRIES} 次。",
            section_id=section_id,
        )

    def _build_xlsx_sheet_user_content(
        self,
        section_id: str,
        section: dict,
        evidence: str,
        prior_errors: list[str],
    ) -> str:
        """R17-P3: Build XLSX sheet generation prompt with cross-sheet context.

        Injects the names of all planned worksheets so the LLM can write correct
        cross-sheet formulas (='SheetName'!ref) without inventing nonexistent names.
        Also includes the current workbook title for formula context.
        """
        all_sections = self.ctx.outline.get("sections", []) if self.ctx.outline else []
        # Build truncated sheet name list (≤31 chars each, matching actual tab names)
        sibling_names = [
            s.get("title", s.get("id", ""))[:31]
            for s in all_sections
            if s.get("id") != section_id
        ]
        siblings_block = ""
        if sibling_names:
            siblings_block = (
                "\n\n【本工作簿中的其他工作表名（跨表引用时必须使用这些确切名称）】\n"
                + "\n".join(f"  - {n}" for n in sibling_names[:10])
                + "\n跨表公式示例：='其他工作表名'!A1:D50"
            )

        error_block = ""
        if prior_errors:
            error_block = "\n前次错误：\n" + "\n".join(prior_errors)

        brief = self.ctx.brief[:300] if self.ctx.brief else ""
        return (
            f"【全局需求】{brief}"
            + siblings_block
            + f"\n\n工作表ID: {section_id}\n"
            f"工作表名: {section.get('title', section_id)}\n"
            f"描述: {section.get('description', '')}\n"
            f"研究材料: {evidence[:2000] if evidence else '无'}"
            + error_block
            + f"""

请输出以下格式JSON：
{{
  "id": "{section_id}",
  "name": "工作表名（≤31字符）",
  "description": "简要说明",
  "table": {{"headers": [...], "rows": [[...], ...]}},
  "key_findings": ["发现1", "发现2"],
  "calculation_notes": ["说明1（如适用，建议使用FILTER/SORT/UNIQUE等动态数组函数的具体公式，引用上述工作表名）"]
}}"""
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_intent_rules(intent: str, tense: str, style: str, template_match: str) -> str:
    """Build the core intent rules block that is NEVER stripped on retry."""
    rules = []

    if intent == "fill_from_reference":
        rules.append("【用户意图：fill_from_reference】")
        rules.append("参考文档是同类历史文档，本次任务是生成对应的当前版本。")
        rules.append("规则：")
        rules.append("1. 严格仿照参考文档的写作风格、段落结构和篇幅")
        rules.append("2. 内容全程使用过去时（已完成、实现了、达成了）" if tense == "past" else "2. 内容使用现在时")
        rules.append("3. 参考文档的数字是历史基线，只能引用，不能凭空改动")
        rules.append("4. 禁止添加参考文档中没有的章节结构；若计划阶段标记 chart_required，可基于本次数据补充图表")
        if template_match:
            rules.append(f"5. 本章节对应参考文档标题：'{template_match}'")
    elif intent == "extend":
        rules.append("【用户意图：extend】")
        rules.append("在参考文档基础上延伸，保持一致风格，增加新内容。")
    else:
        rules.append("【用户意图：fresh】")
        rules.append("生成全新内容，不受参考文档结构约束。")

    if style == "speech":
        rules.append("\n【文档风格：演讲稿/述职稿】")
        rules.append("- 使用连续散文段落，禁止使用 ### 二级标题或项目符号列表")
        rules.append("- 语言流畅自然，如演讲稿般娓娓道来")
    elif style == "report":
        rules.append("\n【文档风格：正式报告】")
        rules.append("- 结构清晰，可使用标题和要点")

    return "\n".join(rules)


def _build_section_summary(title: str, sec: "DocxSectionSpec") -> str:
    """P1-C / P2-3 / P1-6: Rich rolling-context summary for a completed DOCX section.

    Captures:
    - First 2 paragraph text (200 chars) so next sections avoid repeating arguments
    - Last paragraph excerpt (100 chars) — exposes the transition sentence written for
      this section so the next LLM call can continue the narrative naturally
    - Key numeric values mentioned in paragraphs/bullets (prevent value drift)
    - Table structure + first data row
    - Chart title
    """
    parts = [f"【已完成 {title}】"]

    # Lead paragraph (P2-3: extended to 200 chars for better argument coverage)
    all_para_text = " ".join(sec.paragraphs[:2])
    if all_para_text:
        parts.append(all_para_text[:200] + ("…" if len(all_para_text) > 200 else ""))

    if sec.bullets:
        parts.append("要点：" + "；".join(b[:50] for b in sec.bullets[:4]))

    # P1-6: Expose last paragraph so next sections can read the transition sentence
    # and continue the narrative thread without repeating or contradicting it.
    if sec.paragraphs and len(sec.paragraphs) > 2:
        last_para = sec.paragraphs[-1]
        if last_para and len(last_para) > 20:
            parts.append("末段：" + last_para[:100] + ("…" if len(last_para) > 100 else ""))

    # Extract key numbers from paragraphs (prevent cross-section value drift)
    combined_text = " ".join(sec.paragraphs + sec.bullets)
    nums = _re.findall(r"\d[\d,\.]*\s*(?:%|万|亿|元|人|个|项|次|年|月)?", combined_text)
    if nums:
        parts.append("关键数值：" + "、".join(nums[:6]))

    if sec.table and sec.table.headers:
        header_line = "、".join(str(h) for h in sec.table.headers[:6])
        parts.append(f"含表格（列：{header_line}）")
        if sec.table.rows:
            first_row = "、".join(str(v) for v in sec.table.rows[0][:6])
            parts.append(f"首行：{first_row}")

    if sec.chart and sec.chart.title:
        parts.append(f"含图表：{sec.chart.title}")

    return " ".join(parts)


def _section_requires_chart(
    section: dict,
    brief: str,
    report_type: str,
    output_format: str,
    evidence: str,
) -> bool:
    if output_format not in ("word", "doc", "docx", "wps"):
        return False
    if section.get("chart_required"):
        return True
    text = f"{brief or ''} {report_type or ''} {section.get('title', '')} {evidence[:1200]}"
    if _re.search(r"(不要|无需|不需要|禁止).{0,8}(图表|图形|可视化|chart)", text, _re.I):
        return False
    return bool(_re.search(
        r"(图表|图形|可视化|趋势|对比|分布|构成|占比|实验结果|性能|消融|指标|"
        r"数值统计|图表数据建议|excel|csv)",
        text,
        _re.I,
    ))


def _build_docx_chart_instruction(section: dict, evidence: str, uploaded_texts: list[str] | None) -> str:
    if not section.get("chart_required") and "【图表数据建议】" not in (evidence or ""):
        return ""
    hints = []
    for src in (uploaded_texts or []):
        if "【图表数据建议】" in src:
            idx = src.find("【图表数据建议】")
            hints.append(src[idx:idx + 1800])
    data_hint = "\n\n".join(hints[:2])
    return (
        "\n\n【本章节必须生成图表】\n"
        f"图表类型建议：{section.get('chart_hint') or '按数据形态选择 bar/line/combo/heatmap/scatter/radar/waterfall/small_multiples'}\n"
        f"可视化目标：{section.get('visual_goal') or '用图表承载趋势、对比、分布或实验结果，不要把全部信息写成纯文字。'}\n"
        f"{section.get('data_source_hint') or ''}\n"
        "请在 JSON 的 chart 字段输出可执行 ChartSpec：chart_type、title、labels、series、unit、source_note。"
        "若材料来自 Excel/CSV，请优先使用下面的样本数据；若仅有文本材料，请从文本中的数字构建图表。"
        "不要输出无法渲染的占位词。图表必须像正式报告插图：标题具体、标签短、单位清楚、最多保留 6-10 个关键类目；"
        "存在“规模/数量 + 比率/准确率/增速”时优先用 combo，存在多模型多指标矩阵时优先用 heatmap/radar，"
        "存在阶段贡献/增减项时用 waterfall，存在多序列趋势时用 line/area 或 small_multiples，避免所有章节都生成单序列柱状图。\n"
        + (f"\n【上传表格可视化建议】\n{data_hint}" if data_hint else "")
    )


def _fallback_chart_for_section(
    section: dict,
    spec: DocxSectionSpec,
    evidence: str,
    uploaded_texts: list[str] | None,
) -> ChartSpec | None:
    """Build a valid ChartSpec if the LLM omitted chart despite a visual section."""
    title = str(section.get("title") or spec.title or "数据图表")
    hint = str(section.get("chart_hint") or "").lower()
    data_text = "\n".join(t for t in (uploaded_texts or []) if "【图表数据建议】" in t) + "\n" + (evidence or "")
    pairs = _extract_chart_pairs(data_text) or _extract_chart_pairs(" ".join(spec.paragraphs + spec.bullets))

    source_note = "上传数据与章节研究材料"
    if not pairs:
        labels = ["基线", "方案A", "方案B", "目标"]
        values = [62.0, 74.0, 81.0, 88.0]
        source_note = "示意数据：未检测到结构化数值，请接入真实实验/业务数据后替换"
    else:
        labels = [p[0] for p in pairs[:8]]
        values = [p[1] for p in pairs[:8]]

    if len(labels) < 2 or len(values) < 2:
        return None

    chart_type = _normalize_chart_hint(hint, labels, len(values))
    unit = _infer_chart_unit(data_text)
    if chart_type == "combo":
        series = [
            ChartSeriesSpec(name="数值", values=values, series_type="bar"),
            ChartSeriesSpec(name="变化趋势", values=_index_values(values), series_type="line"),
        ]
    elif chart_type == "heatmap":
        labels = labels[: min(len(labels), 5)]
        base = values[:len(labels)]
        series = [
            ChartSeriesSpec(name="指标A", values=base, series_type="bar"),
            ChartSeriesSpec(name="指标B", values=_index_values(base), series_type="bar"),
            ChartSeriesSpec(name="指标C", values=[round(v * 0.82, 2) for v in base], series_type="bar"),
        ]
    elif chart_type == "scatter":
        series = [ChartSeriesSpec(name="变量关系", values=values, series_type="scatter")]
    elif chart_type == "donut":
        series = [ChartSeriesSpec(name="占比", values=[abs(v) for v in values], series_type="bar")]
    else:
        series_type = "line" if chart_type in {"line", "area"} else "bar"
        series = [ChartSeriesSpec(name="核心指标", values=values, series_type=series_type)]

    return ChartSpec(
        chart_type=chart_type,
        title=f"{title}关键数据可视化",
        labels=labels,
        series=series,
        unit=unit,
        source_note=source_note,
        orientation="horizontal" if chart_type in {"bar", "stacked_bar"} and any(len(x) > 6 for x in labels) else "vertical",
    )


def _extract_chart_pairs(text: str) -> list[tuple[str, float]]:
    pairs: list[tuple[str, float]] = []
    for label, raw in _re.findall(r"([A-Za-z0-9一-龥_（）()·\\-]{2,24})\s*[=:：]\s*(-?\d+(?:\.\d+)?)", text or ""):
        if _looks_like_bad_label(label):
            continue
        pairs.append((label.strip(" ，,。；;"), float(raw)))
        if len(pairs) >= 10:
            return pairs
    for label, raw, unit in _RE_NUMERIC_ENTITY.findall(text or ""):
        if _looks_like_bad_label(label):
            continue
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if unit == "亿":
            val *= 10000
        pairs.append((label[-10:], val))
        if len(pairs) >= 10:
            break
    seen = set()
    cleaned = []
    for label, val in pairs:
        key = label.strip()
        if key and key not in seen:
            cleaned.append((key, round(val, 2)))
            seen.add(key)
    return cleaned


def _looks_like_bad_label(label: str) -> bool:
    return bool(_re.search(r"(http|www|source|来源|created|event|phase|section|id|json)", label, _re.I))


def _normalize_chart_hint(hint: str, labels: list[str], n_values: int) -> str:
    if hint in {"line", "area", "combo", "scatter", "heatmap", "donut", "bar", "column", "stacked_bar"}:
        return "column" if hint == "bar" and n_values <= 6 else hint
    sample = " ".join(labels[:4])
    if _re.search(r"(20\d{2}|季度|月份|月|年|q[1-4])", sample, _re.I):
        return "line"
    return "column" if n_values <= 6 else "bar"


def _infer_chart_unit(text: str) -> str:
    if "%" in (text or ""):
        return "%"
    for unit in ("万元", "亿元", "元", "人", "个", "项", "次"):
        if unit in (text or ""):
            return unit
    return ""


def _index_values(values: list[float]) -> list[float]:
    if not values:
        return []
    base = values[0] or 1.0
    return [round((v / base) * 100, 2) for v in values]


_DOCX_SECTION_SCHEMA_EXAMPLE = """{
  "id": "s1",
  "title": "一、工作概述",
  "template_heading_match": "一、工作概述",
  "content_type": "mixed",
  "paragraphs": ["本年度完成了…", "在XX方面，实现了…"],
  "bullets": ["完成指标A：同比增长15%", "推进项目B：按时交付"],
  "table": null,
  "chart": {
    "chart_type": "combo",
    "title": "关键指标对比与变化趋势",
    "labels": ["样本A", "样本B", "样本C"],
    "series": [
      {"name": "指标值", "values": [72.5, 81.0, 88.2], "series_type": "bar"},
      {"name": "相对变化", "values": [100.0, 111.7, 121.7], "series_type": "line"}
    ],
    "unit": "%",
    "source_note": "上传数据与章节研究材料",
    "orientation": "vertical"
  },
  "target_chars": 400,
  "style_note": "narrative",
  "evidence_ids": ["年度报告2024.docx", "财务数据表"],
  "subsections": [
    {
      "id": "s1_1",
      "title": "（一）重点工作",
      "template_heading_match": "（一）重点工作",
      "content_type": "paragraphs",
      "paragraphs": ["重点工作包括…"],
      "bullets": [],
      "table": null,
      "chart": null,
      "target_chars": 200,
      "style_note": "",
      "evidence_ids": [],
      "subsections": []
    }
  ]
}"""

_PPTX_SLIDE_SCHEMA_EXAMPLE = """{
  "id": "slide1",
  "layout": "content",
  "template_slide_idx": null,
  "assertion_title": "2025年营收达50亿，同比增长15%",
  "bullets": ["核心业务贡献80%营收", "新兴业务同比增长40%"],
  "table": null,
  "chart": {
    "chart_type": "bar",
    "title": "各季度营收（亿元）",
    "labels": ["Q1","Q2","Q3","Q4"],
    "series": [{"name": "营收", "values": [10.5,12.0,13.5,14.0], "series_type": "bar"}]
  },
  "speaker_notes": "本页核心是2025年营收突破50亿、同比增长15%。该增长主要来自核心业务80%营收贡献及新兴业务40%高速增长，Q4单季14亿为历史新高，数据来源为集团年度财务审计报告。下页将展示各业务线的利润率对比分析。"
}"""


def _promote_bullets_to_paragraphs(spec: "DocxSectionSpec", style: str) -> "DocxSectionSpec":
    """R17-P2: Auto-promote bullets to prose paragraphs for speech-style sections.

    When style='speech' (述职稿/演讲稿) and the section's content_type is 'paragraphs',
    the LLM sometimes returns bullet lists despite the style requirement.  This function
    merges the top bullets into a single continuous prose paragraph.

    Only applies when:
    - style == "speech"
    - content_type == "paragraphs" (prose expected)
    - paragraphs is empty (nothing was generated as prose)
    - bullets is non-empty (the content exists but in wrong format)
    """
    if style != "speech":
        return spec
    if spec.content_type != "paragraphs":
        return spec
    if spec.paragraphs or not spec.bullets:
        return spec  # already has paragraphs, or nothing to promote

    # Merge top 4 bullets into a single prose paragraph with connective tissue
    merged_parts = []
    for b in spec.bullets[:4]:
        cleaned = b.rstrip("。，,、；;").strip()
        if cleaned:
            merged_parts.append(cleaned)

    if not merged_parts:
        return spec

    merged = "。".join(merged_parts) + "。"
    logger.debug("[SpecGen] Promoted %d bullets to paragraph for speech section '%s'",
                 len(merged_parts), spec.title)
    return spec.model_copy(update={"paragraphs": [merged], "bullets": []})


def _fix_speaker_notes_transitions(slides: list) -> list:
    """P3-2: Ensure every slide (except the last) has a transition sentence.

    If slide N's speaker_notes does not contain a transition keyword
    (下页/接下来/下一/下面), append a bridge sentence pointing to slide N+1's
    assertion_title. Truncates the final notes to the 220-char Pydantic limit.
    """
    _TRANSITION_KEYWORDS = ("下页", "接下来", "下一", "下面", "随后", "紧接")
    result = []
    for i, slide in enumerate(slides):
        if i < len(slides) - 1 and slide.speaker_notes:
            has_transition = any(kw in slide.speaker_notes for kw in _TRANSITION_KEYWORDS)
            if not has_transition:
                next_title = slides[i + 1].assertion_title[:18]
                bridge = f"下页将分析{next_title}的具体情况。"
                new_notes = slide.speaker_notes.rstrip() + bridge
                # Honour Pydantic 220-char limit (sentence-aware)
                if len(new_notes) > 220:
                    new_notes = new_notes[:220]
                slide = slide.model_copy(update={"speaker_notes": new_notes})
        result.append(slide)
    return result


def _fix_pptx_layout_sanity(slides: list) -> list:
    """R18-PPTX: Correct impossible layout/content combinations in PPTX slide specs.

    LLMs occasionally produce slides where the layout field contradicts the content:
    - section_header with bullets → demote to 'content' (section_header means divider-only)
    - big_number with no digit in assertion_title → demote to 'content'
    - comparison layout with <2 bullets → upgrade logic

    This pass runs after sequential generation, so it has visibility into all slides.
    Changes are logged at DEBUG level for post-mortem analysis.
    """
    result = []
    for slide in slides:
        layout = slide.layout
        new_layout = layout

        if layout == "section_header" and slide.bullets:
            new_layout = "content"
            logger.debug(
                "[SpecGen] Layout sanity: slide '%s' section_header→content (has %d bullets)",
                slide.id, len(slide.bullets),
            )
        elif layout == "big_number" and not _RE_DIGIT.search(slide.assertion_title):
            new_layout = "content"
            logger.debug(
                "[SpecGen] Layout sanity: slide '%s' big_number→content (no digit in assertion_title)",
                slide.id,
            )
        elif layout == "comparison" and len(slide.bullets) < 2:
            new_layout = "content"
            logger.debug(
                "[SpecGen] Layout sanity: slide '%s' comparison→content (only %d bullets, need ≥2)",
                slide.id, len(slide.bullets),
            )

        if new_layout != layout:
            slide = slide.model_copy(update={"layout": new_layout})
        result.append(slide)
    return result


def _is_dark_color(hex_color: str) -> bool:
    """P2-4: Return True if hex_color (without #) represents a dark background color."""
    try:
        h = hex_color.lstrip("#")
        if len(h) < 6:
            return False
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        # Relative luminance formula (WCAG 2.1)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return luminance < 128
    except Exception:
        return False


def _apply_chart_type_rules(spec) -> "DocxSectionSpec | PptxSlideSpec":
    """P2-3: Post-process generated spec to correct chart types using rule-based logic.

    Applies infer_chart_type() from doc_spec to any embedded ChartSpec,
    overriding the LLM's choice when the data shape clearly indicates another type.
    """
    from app.rendering.doc_spec import infer_chart_type

    def _fix(chart_spec):
        if chart_spec is None:
            return chart_spec
        n_series = len(chart_spec.series)
        inferred = infer_chart_type(chart_spec.labels, n_series)
        if inferred != chart_spec.chart_type:
            # Only override when the difference is meaningful
            _WEAK_TYPES = {"bar", "column"}  # LLM often defaults here; safe to override
            if chart_spec.chart_type in _WEAK_TYPES:
                logger.debug(
                    "[SpecGen] Chart type corrected: %s → %s for '%s'",
                    chart_spec.chart_type, inferred, chart_spec.title,
                )
                return chart_spec.model_copy(update={"chart_type": inferred})
        return chart_spec

    try:
        if hasattr(spec, "chart"):
            fixed = _fix(spec.chart)
            if fixed is not spec.chart:
                spec = spec.model_copy(update={"chart": fixed})
        if hasattr(spec, "subsections"):
            fixed_subs = []
            for sub in (spec.subsections or []):
                fixed_subs.append(_apply_chart_type_rules(sub))
            spec = spec.model_copy(update={"subsections": fixed_subs})
    except Exception as exc:
        logger.debug("[SpecGen] Chart type rule application failed: %s", exc)
    return spec


def _patch_chart_values_from_entity_map(
    slides: list,
    entity_map: dict[str, str],
) -> list:
    """P1-1: Align PPTX chart series values with the global numeric_entity_map.

    When a slide's chart title or series label mentions a metric that appears
    in entity_map with a known value, patch that series' first value to match,
    preventing numbers-in-text from diverging from numbers-in-chart.

    Only patches single-value series (e.g. bar/column with one bar per metric).
    Multi-value time series are left untouched since they represent a different
    dimension (values over time, not a point estimate).
    """
    import re as _re_cvm

    if not entity_map or not slides:
        return slides

    result = []
    for slide in slides:
        chart = getattr(slide, "chart", None)
        if chart is None:
            result.append(slide)
            continue

        try:
            new_series = []
            changed = False
            for series in (chart.series or []):
                # Only patch 1-value series that look like point estimates
                if len(series.values) != 1:
                    new_series.append(series)
                    continue

                # Look for metric name in series label
                matched_val = None
                for metric, val_str in entity_map.items():
                    if metric in (series.label or ""):
                        try:
                            matched_val = float(val_str.replace(",", "").rstrip("%万亿元人个项次"))
                        except ValueError:
                            pass
                        break

                if matched_val is not None and matched_val != series.values[0]:
                    logger.debug(
                        "[SpecGen] Chart value patched: series '%s' %s → %s",
                        series.label, series.values[0], matched_val,
                    )
                    new_series.append(series.model_copy(update={"values": [matched_val]}))
                    changed = True
                else:
                    new_series.append(series)

            if changed:
                new_chart = chart.model_copy(update={"series": new_series})
                slide = slide.model_copy(update={"chart": new_chart})

        except Exception as exc:
            logger.debug("[SpecGen] Chart value patch failed (non-fatal): %s", exc)

        result.append(slide)
    return result


def _section_spec_summary(sec_spec, completed: int, total: int) -> str:
    title = getattr(sec_spec, "title", "") or f"章节 {completed}"
    paragraphs = [str(p).strip() for p in (getattr(sec_spec, "paragraphs", None) or []) if str(p).strip()]
    bullets = [str(b).strip() for b in (getattr(sec_spec, "bullets", None) or []) if str(b).strip()]
    chart = getattr(sec_spec, "chart", None)
    signals: list[str] = []
    if paragraphs:
        signals.append(f"首段：{paragraphs[0][:110]}")
    if bullets:
        signals.append("要点：" + "；".join(b[:60] for b in bullets[:3]))
    if chart:
        chart_title = getattr(chart, "title", "") or "图表"
        chart_type = getattr(chart, "chart_type", "") or ""
        signals.append(f"图表：{chart_title}" + (f"（{chart_type}）" if chart_type else ""))
    body = "；".join(signals) if signals else "该章节已形成结构化草稿。"
    return f"章节 {completed}/{total}「{title}」：{body}"
