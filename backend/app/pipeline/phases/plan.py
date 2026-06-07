"""PLAN phase — generates report outline.

Core fix: when intent is fill_from_reference and a reference_structure exists,
the outline sections are derived DETERMINISTICALLY from the reference document's
headings. The LLM only fills in key_points per section — it cannot re-invent
the structure.

For fresh intent: LLM generates the full outline as before.
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from app.pipeline.types import PipelineContext, PipelineError
from app.pipeline.llm_helpers import call_llm_json, _coerce_json_object, _listify
from app.pipeline.skills_loader import build_skill_context, filter_skills_for_phase
from app.rendering.ref_extractor import ReferenceStructure
from app.services.document_standards import (
    apply_standard_sections,
    format_standard_for_prompt,
    get_document_standard,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class PlanPhase:
    PHASE_NAME = "PLAN"

    def __init__(self, ctx: PipelineContext):
        self.ctx = ctx

    async def run(self) -> None:
        ctx = self.ctx
        understanding = ctx.understanding
        intent = understanding.get("intent", "fresh")
        ref_structure_dict = understanding.get("reference_structure")

        ref_structure = None
        if ref_structure_dict:
            try:
                ref_structure = ReferenceStructure.from_dict(ref_structure_dict)
            except Exception as exc:
                logger.warning("[PLAN] Failed to deserialise reference_structure: %s", exc)

        if intent in ("fill_from_reference", "extend") and ref_structure and ref_structure.sections:
            # P2-1: Both fill_from_reference AND extend use the deterministic reference path.
            # For extend, _outline_from_reference preserves existing sections from the template
            # and the LLM-generated key_points naturally include extension content.
            outline = await self._outline_from_reference(ref_structure, understanding)
        else:
            # LLM-generated path: fresh (or extend without a reference doc)
            outline = await self._outline_from_llm(understanding)

        ctx.outline = outline
        ctx.report.section_outline = outline
        await ctx.db.commit()
        if ctx.progress_callback:
            try:
                await ctx.progress_callback({
                    "phase": "PLAN",
                    "progress": 0.18,
                    "natural_message": _build_plan_narrative(outline),
                    "outline_preview": _build_outline_preview(outline),
                })
            except Exception:
                pass

    # ── Deterministic path ─────────────────────────────────────────────────────

    async def _outline_from_reference(
        self,
        ref_structure: ReferenceStructure,
        understanding: dict,
    ) -> dict:
        """Build outline from reference sections, then ask LLM for key_points only."""
        brief = self.ctx.brief
        skill_context = build_skill_context(
            filter_skills_for_phase(self.ctx.skills, "plan")
        )

        # P1-A: Proportional target_chars — distribute a total target across sections
        # using each reference section's actual char count as a weight, so longer
        # template sections get proportionally more space in the output.
        total_ref_chars = sum(max(s.char_count, 1) for s in ref_structure.sections)
        n_sections = len(ref_structure.sections)
        total_target = max(n_sections * 500, 3000)

        sections_base = []
        for i, ref_sec in enumerate(ref_structure.sections):
            ratio = max(ref_sec.char_count, 1) / total_ref_chars
            target_chars = max(200, min(1500, int(total_target * ratio)))
            sections_base.append({
                "id": f"s{i + 1}",
                "title": ref_sec.heading_text,
                "template_heading_match": ref_sec.heading_text,
                "content_type": ref_sec.content_type,
                "target_chars": target_chars,
                "key_points": [],  # to be filled by LLM
                "layout_hint": _layout_hint_for_content_type(ref_sec.content_type),
            })

        # Ask LLM ONLY for key_points per section (structure is fixed)
        sections_with_points = await self._fill_key_points(
            sections_base, brief, understanding, skill_context
        )

        title = _infer_title(brief, understanding)
        outline = {
            "title": title,
            "intent": "fill_from_reference",
            "tense": understanding.get("tense", "present"),
            "style": understanding.get("style", "report"),
            "sections": sections_with_points,
            "derived_from_reference": True,
        }
        from app.services.request_intelligence import chart_policy_for_request
        document_standard = get_document_standard(self.ctx.report_type, brief)
        outline["sections"] = _activate_docx_visual_plan(
            outline["sections"],
            brief=brief,
            report_type=self.ctx.report_type,
            output_format=self.ctx.output_format,
            chart_policy=chart_policy_for_request(brief, self.ctx.report_type, self.ctx.output_format),
            document_standard=document_standard,
            uploaded_texts=self.ctx.uploaded_texts,
        )
        if document_standard:
            outline["document_standard"] = document_standard
        logger.info("[PLAN] Built outline from reference: %d sections", len(sections_with_points))
        return outline

    async def _fill_key_points(
        self,
        sections: list[dict],
        brief: str,
        understanding: dict,
        skill_context: str,
    ) -> list[dict]:
        """Ask LLM to suggest key_points for each section (small, focused call)."""
        section_list_text = "\n".join(
            f"{i + 1}. {s['title']} (目标字数: {s['target_chars']})"
            for i, s in enumerate(sections)
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "你是文档大纲规划助手。根据章节标题和用户需求，为每个章节建议3-5个关键内容要点。"
                    "只输出JSON数组，每项包含 id 和 key_points 字段，不附加任何解释。"
                    + (f"\n\n写作规范：\n{skill_context}" if skill_context else "")
                ),
            },
            {
                "role": "user",
                "content": f"""需求：{brief}
目标：{understanding.get('goal', '')}
已定章节结构（来自参考文档，请为每章建议要点）：
{section_list_text}

请输出JSON数组：
[
  {{"id": "s1", "key_points": ["要点1", "要点2", "要点3"]}},
  ...
]""",
            },
        ]

        try:
            raw = await call_llm_json(messages, temperature=0.4, max_tokens=3000, tier="standard")
            # raw might be {"items": [...]} or a list directly
            items = raw.get("items", raw) if isinstance(raw, dict) else raw
            if not isinstance(items, list):
                items = list(raw.values())[0] if raw else []
            points_map = {item["id"]: item.get("key_points", []) for item in items if isinstance(item, dict)}
        except Exception as exc:
            logger.warning("[PLAN] key_points fill failed: %s — using empty points", exc)
            points_map = {}

        result = []
        for sec in sections:
            updated = dict(sec)
            updated["key_points"] = points_map.get(sec["id"], [])
            result.append(updated)
        return result

    # ── LLM-generated path ────────────────────────────────────────────────────

    async def _outline_from_llm(self, understanding: dict) -> dict:
        from app.services.request_intelligence import (
            normalize_requested_title,
            chart_policy_for_request,
            temporal_policy_for_request,
        )

        ctx = self.ctx
        brief = ctx.brief
        report_type = ctx.report_type
        output_format = ctx.output_format
        uploaded_texts = ctx.uploaded_texts
        document_standard = get_document_standard(report_type, brief)
        standard_note = format_standard_for_prompt(document_standard)
        skill_context = build_skill_context(
            filter_skills_for_phase(ctx.skills, "plan")
        )

        evidence_block = ""
        if uploaded_texts:
            excerpts = [t[:2000] for t in uploaded_texts[:4]]
            evidence_block = "\n\n---\n\n".join(excerpts)

        topic = understanding.get("topic", brief[:50])
        goal = understanding.get("goal", "")
        key_questions = understanding.get("key_questions", [])
        tone = understanding.get("tone", "专业")
        estimated_sections = int(understanding.get("estimated_sections", 6) or 6)

        normalized_title = normalize_requested_title("", brief, report_type)
        chart_policy = chart_policy_for_request(brief, report_type, output_format)
        temporal_policy = temporal_policy_for_request(brief, report_type)

        format_note = _format_outline_note(output_format, estimated_sections)

        # P1-1: Inject narrative framework as a structural constraint
        narrative_framework = understanding.get("narrative_framework", "SCR")
        framework_note = _narrative_framework_note(narrative_framework, output_format)

        branch_context = understanding.get("branch_context") or {}
        branch_note = ""
        if branch_context and branch_context.get("is_branch_data"):
            dim_col = branch_context.get("dimension_col", "分行")
            kpi_cols = branch_context.get("kpi_cols", [])
            n_branches = branch_context.get("branch_count", 0)
            branch_note = (
                f"\n【多实体数据】数据含 {n_branches} 个{dim_col}，"
                f"KPI：{', '.join(kpi_cols[:5])}。"
                f"请在大纲中安排排名对比、KPI达标分析章节。"
            )

        system_prompt = (
            "你是文档结构专家。根据用户需求设计章节大纲。"
            "当存在所选模板标准时，必须把它当成硬性结构约束，而不是风格建议。"
            "只输出JSON，不附加任何解释文字。"
            + (f"\n\n{standard_note}" if standard_note else "")
            + (f"\n\n写作规范：\n{skill_context}" if skill_context else "")
        )

        user_prompt = f"""请为以下需求设计章节大纲。

【主题】{topic}
【标准标题】{normalized_title}
【核心目标】{goal}
【报告类型】{report_type}
【语气风格】{tone}
【关键问题】{', '.join(key_questions) if key_questions else '（按需自动识别）'}
【时间口径】{temporal_policy.get('instruction', '使用报告中的实际时间')}
【图表口径】{chart_policy.get('instruction', '适当添加图表')}{framework_note}{branch_note}

{format_note}

{standard_note}

【参考材料摘要】
{evidence_block or "（无上传材料）"}

请输出JSON：
{{
  "title": "报告标题",
  "sections": [
    {{
      "id": "s1",
      "title": "章节标题",
      "content_type": "paragraphs|bullets|table|mixed",
      "key_points": ["要点1", "要点2", "要点3"],
      "target_chars": 500,
      "layout_hint": "content"
    }}
  ]
}}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        raw = await call_llm_json(messages, temperature=0.4, max_tokens=4000, tier="heavy")
        raw = _coerce_json_object(raw, context="outline")
        sections = raw.get("sections") or raw.get("items") or []
        if not isinstance(sections, list):
            sections = []

        if not sections:
            sections = _fallback_sections(brief, output_format, estimated_sections)
        else:
            sections = [_normalize_section(s, i, output_format) for i, s in enumerate(sections)]
        sections = apply_standard_sections(sections, document_standard, output_format)
        sections = _activate_docx_visual_plan(
            sections,
            brief=brief,
            report_type=report_type,
            output_format=output_format,
            chart_policy=chart_policy,
            document_standard=document_standard,
            uploaded_texts=uploaded_texts,
        )

        outline = {
            "title": str(raw.get("title", normalized_title)),
            "intent": understanding.get("intent", "fresh"),
            "tense": understanding.get("tense", "present"),
            "style": understanding.get("style", "report"),
            "sections": sections,
            "derived_from_reference": False,
            "document_standard": document_standard,
        }

        # P1-2: Critique pass — verify key_questions coverage, detect duplicate themes
        outline = await self._critique_outline(outline, understanding)

        # P2-3: PPTX-specific critique — assertion ratio, layout diversity, slide count
        if output_format in ("pptx", "ppt"):
            outline = await self._critique_pptx_outline(outline, understanding)
            # R16-P1: Auto-insert agenda slide as slide 2 for presentations with 5+ sections.
            # Must run BEFORE closing slide guarantee so the slide count is stable.
            outline = _ensure_pptx_agenda_slide(outline)
            # P3-3: Auto-append a closing slide if the deck has no conclusion section.
            # Professional presentations always end with a wrap-up slide so the
            # audience knows the presentation is complete.
            outline = _ensure_pptx_closing_slide(outline)

        logger.info("[PLAN] Built LLM outline: %d sections", len(outline["sections"]))
        return outline

    async def _critique_outline(self, outline: dict, understanding: dict) -> dict:
        """P1-2: Fast LLM check that outline covers key_questions with no duplicate themes."""
        key_questions = understanding.get("key_questions", [])
        if not key_questions or len(outline.get("sections", [])) == 0:
            return outline

        sections_text = "\n".join(
            f"- {s.get('title', '')}：{', '.join(s.get('key_points', [])[:3])}"
            for s in outline["sections"]
        )
        questions_text = "\n".join(f"- {q}" for q in key_questions[:8])

        try:
            result = await call_llm_json(
                messages=[
                    {
                        "role": "system",
                        "content": "你是大纲评审专家。检查大纲是否覆盖了所有关键问题，并识别主题重复的章节。只输出JSON。",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"关键问题（必须被大纲覆盖）：\n{questions_text}\n\n"
                            f"当前大纲：\n{sections_text}\n\n"
                            '请输出JSON：{"ok": true} 或\n'
                            '{"ok": false, "missing_questions": ["未覆盖问题"], "has_duplicates": false}'
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=400,
                fallback={"ok": True},
                tier="standard",
            )

            if result.get("ok"):
                return outline

            missing = result.get("missing_questions", [])
            if missing:
                logger.info("[PLAN] Critique: %d uncovered questions — appending sections", len(missing))
                sections = list(outline["sections"])
                for q in missing[:3]:
                    new_id = f"s_ex{len(sections) + 1}"
                    sections.append({
                        "id": new_id,
                        "title": str(q)[:40],
                        "content_type": "paragraphs",
                        "key_points": [str(q)],
                        "target_chars": 400,
                        "layout_hint": "content",
                        "template_heading_match": None,
                    })
                outline["sections"] = sections

            if result.get("has_duplicates"):
                logger.info("[PLAN] Critique flagged duplicate themes (manual review recommended)")

        except Exception as exc:
            logger.debug("[PLAN] Outline critique failed (non-fatal): %s", exc)

        return outline

    async def _critique_pptx_outline(self, outline: dict, understanding: dict) -> dict:
        """P2-3: PPTX-specific critique — assertion ratio, layout diversity, slide count."""
        sections = outline.get("sections", [])
        if not sections:
            return outline

        # Check 1: Assertion title ratio — >80% of slide titles should contain
        # numbers or judgment words (the hallmark of assertive PPTX titles).
        # P3-2: Require 2+ digit number OR percentage to avoid counting "第1节"
        # style sequence numbers as meaningful assertions.
        _JUDGMENT_PAT = re.compile(
            r"\d{2,}|%|增长|下降|超|达|占|领先|落后|持平|提升|下滑|改善|恶化|突破|不足"
        )
        assertion_count = sum(1 for s in sections if _JUDGMENT_PAT.search(s.get("title", "")))
        assertion_ratio = assertion_count / len(sections)

        needs_title_fix = assertion_ratio < 0.6  # tolerate up to 40% non-assertive

        # Check 2: Layout diversity — flag if >75% of slides share the same layout_hint
        from collections import Counter
        layout_counts = Counter(s.get("layout_hint", "content") for s in sections)
        most_common_layout, most_common_count = layout_counts.most_common(1)[0]
        layout_diversity_ok = (most_common_count / len(sections)) <= 0.75

        # Check 3: Slide count alignment — if brief mentions a target count
        target_count = None
        for pat in [r"(\d+)\s*(?:页|slides?|张|片)", r"(?:约|大约|共)\s*(\d+)\s*(?:页|张)"]:
            m = re.search(pat, self.ctx.brief or "", re.IGNORECASE)
            if m:
                target_count = int(m.group(1))
                break

        if not needs_title_fix and layout_diversity_ok and not target_count:
            logger.info("[PLAN] PPTX critique passed: assertion_ratio=%.0f%%, layout_ok=%s",
                        assertion_ratio * 100, layout_diversity_ok)
            return outline

        # Build critique report for LLM re-generation guidance
        issues: list[str] = []
        if needs_title_fix:
            issues.append(
                f"断言标题比例过低（{assertion_ratio:.0%}），至少 80% 的幻灯片标题应包含数字或判断性词语"
            )
        if not layout_diversity_ok:
            issues.append(
                f"布局单一：{most_common_count}/{len(sections)} 张幻灯片使用 '{most_common_layout}' 布局，"
                "请使用 big_number/comparison/section_header 等多样布局"
            )
        if target_count and abs(len(sections) - target_count) > 2:
            issues.append(
                f"幻灯片数量 {len(sections)} 与需求中的 {target_count} 偏差过大"
            )

        logger.info("[PLAN] PPTX critique issues: %s", "; ".join(issues))

        # Ask LLM to patch the outline (titles + layout_hints only — structure preserved)
        sections_text = "\n".join(
            f"{i + 1}. title={s.get('title', '')} layout={s.get('layout_hint', 'content')}"
            for i, s in enumerate(sections)
        )
        try:
            patch_result = await call_llm_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是PPT幻灯片大纲优化专家。根据反馈修正每张幻灯片的标题和布局类型。"
                            "只输出JSON数组，每项包含 index（从0开始）、title、layout_hint 三个字段。"
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"需求：{self.ctx.brief}\n"
                            + (f"目标幻灯片数量：{target_count} 页\n" if target_count else "")
                            + f"\n当前幻灯片列表（共 {len(sections)} 页）：\n{sections_text}\n\n"
                            f"问题：\n" + "\n".join(f"- {i}" for i in issues) + "\n\n"
                            "请输出修正后的幻灯片列表（只修改有问题的条目，保持结构不变）："
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=2000,
                fallback=[],
                tier="standard",
            )

            patches = patch_result if isinstance(patch_result, list) else patch_result.get("items", [])
            if patches:
                updated_sections = list(sections)
                for patch in patches:
                    idx = patch.get("index")
                    if idx is None or not isinstance(idx, int) or idx >= len(updated_sections):
                        continue
                    sec = dict(updated_sections[idx])
                    if patch.get("title"):
                        sec["title"] = str(patch["title"])
                    if patch.get("layout_hint") in ("content", "comparison", "title_only",
                                                     "section_header", "big_number"):
                        sec["layout_hint"] = patch["layout_hint"]
                    updated_sections[idx] = sec
                outline["sections"] = updated_sections
                logger.info("[PLAN] PPTX critique applied %d patches", len(patches))

        except Exception as exc:
            logger.debug("[PLAN] PPTX critique patch failed (non-fatal): %s", exc)

        return outline


# ── Helpers ───────────────────────────────────────────────────────────────────

def _layout_hint_for_content_type(content_type: str) -> str:
    return {
        "table": "data_table",
        "mixed": "content",
        "paragraphs": "content",
        "bullets": "content",
    }.get(content_type, "content")


def _infer_title(brief: str, understanding: dict) -> str:
    from app.services.request_intelligence import normalize_requested_title
    return normalize_requested_title("", brief, "")


def _format_outline_note(output_format: str, estimated_sections: int) -> str:
    if output_format in ("pptx", "ppt"):
        return (
            f"【格式：PPT】每页一个幻灯片规格，约 {max(estimated_sections, 8)}-{max(estimated_sections + 4, 12)} 页。"
            "\n每页 title 是断言式标题（含数字/结论），content_type 通常是 'mixed'。"
        )
    elif output_format in ("xlsx", "excel", "xls"):
        return (
            f"【格式：Excel】每章对应一个工作表，约 {estimated_sections} 个工作表。"
            "\ncontent_type 一律填 'table'。"
        )
    else:
        return (
            f"【格式：Word】结构化报告，约 {estimated_sections} 章，"
            "\n每章 500-800 字，content_type 用 'paragraphs'|'bullets'|'mixed'。"
        )


def _build_outline_preview(outline: dict) -> str:
    sections = outline.get("sections") or []
    lines = [f"# {outline.get('title') or '文档结构计划'}", ""]
    for idx, section in enumerate(sections[:20], 1):
        title = str(section.get("title") or f"第{idx}节")
        points = section.get("key_points") or []
        lines.append(f"{idx}. {title}")
        for point in points[:3]:
            lines.append(f"   - {point}")
    return "\n".join(lines).strip()


def _build_plan_narrative(outline: dict) -> str:
    sections = outline.get("sections") or []
    title = outline.get("title") or "这份文档"
    if not sections:
        return f"我已经完成《{title}》的结构规划，接下来会进入资料检索和正文撰写。"
    first_titles = "、".join(str(s.get("title") or "") for s in sections[:4] if s.get("title"))
    return (
        f"我已经把《{title}》拆成 {len(sections)} 个主要部分。"
        f"前几部分会从 {first_titles} 开始展开；接下来我会为每个章节检索资料、提取证据，并把正文逐段写入右侧文档。"
    )


def _activate_docx_visual_plan(
    sections: list[dict],
    *,
    brief: str,
    report_type: str,
    output_format: str,
    chart_policy: dict,
    document_standard: str | None,
    uploaded_texts: list[str] | None,
) -> list[dict]:
    """Mark data-bearing Word sections that must become chart-enabled."""
    if output_format not in ("word", "doc", "docx", "wps"):
        return sections

    combined = f"{brief or ''} {report_type or ''} {document_standard or ''}"
    has_tabular_data = any("【图表数据建议】" in t or "【数值统计（严格参考）】" in t for t in (uploaded_texts or []))
    chart_worthy = bool(chart_policy.get("allowed")) or has_tabular_data or bool(
        re.search(r"(论文|实验报告|科研|研究|实验|数据|分析|评估|对比|趋势|消融|benchmark)", combined, re.I)
    )
    if not chart_worthy:
        return sections

    skip_re = re.compile(r"(摘要|关键词|参考文献|致谢|附录|结论|目录|封面|abstract|keywords|reference)", re.I)
    strong_re = re.compile(
        r"(实验|结果|分析|数据|指标|对比|趋势|评估|性能|方法|讨论|发现|经营|财务|销售|用户|"
        r"results?|experiment|analysis|method|discussion|performance|benchmark)",
        re.I,
    )

    result = [dict(s) for s in sections]
    candidates: list[int] = []
    for idx, sec in enumerate(result):
        title = str(sec.get("title", ""))
        if skip_re.search(title):
            continue
        if strong_re.search(title) or has_tabular_data:
            candidates.append(idx)

    if not candidates and len(result) >= 3:
        candidates = [max(1, len(result) // 2)]

    target_count = 3 if has_tabular_data or "实验" in combined or "论文" in combined else 2
    for order, idx in enumerate(candidates[:target_count]):
        sec = result[idx]
        title = str(sec.get("title", ""))
        sec["chart_required"] = True
        sec["content_type"] = "mixed"
        sec["layout_hint"] = "content_with_chart"
        sec["chart_hint"] = _chart_hint_for_section(title, order, has_tabular_data)
        sec["visual_goal"] = _visual_goal_for_section(title, sec["chart_hint"])
        if has_tabular_data:
            sec["data_source_hint"] = "优先读取上传的 Excel/CSV 数据文件，使用【图表数据建议】和【数值统计（严格参考）】构建图表。"
        points = list(sec.get("key_points") or [])
        if not any("图" in p or "可视化" in p for p in points):
            points.append("主动识别可图表化的数据，生成可审计 ChartSpec，并由后端渲染为图片插入文档。")
        sec["key_points"] = points
    return result


def _chart_hint_for_section(title: str, order: int, has_tabular_data: bool) -> str:
    text = title.lower()
    if re.search(r"(趋势|时间|年度|季度|月份|发展|演变|trend|time)", text, re.I):
        return "line"
    if re.search(r"(对比|比较|排名|差异|性能|benchmark|结果)", text, re.I):
        return "combo" if has_tabular_data or order % 2 else "bar"
    if re.search(r"(分布|构成|占比|结构)", text, re.I):
        return "donut"
    if re.search(r"(相关|关系|散点|影响因素)", text, re.I):
        return "scatter"
    if re.search(r"(多指标|指标体系|矩阵|热度)", text, re.I):
        return "heatmap"
    return ["bar", "line", "combo", "heatmap"][order % 4]


def _visual_goal_for_section(title: str, chart_hint: str) -> str:
    names = {
        "bar": "用多色柱状/条形图展示核心对象之间的差异。",
        "line": "用折线或面积图展示趋势、阶段变化和关键拐点。",
        "combo": "用复合图同时展示绝对值和比例/增速，增强分析层次。",
        "donut": "用环图展示构成关系和主要占比。",
        "scatter": "用散点图展示变量关系、聚类和异常点。",
        "heatmap": "用热力图展示多指标交叉表现。",
    }
    return f"章节「{title}」需要图文结合。{names.get(chart_hint, names['bar'])}"


def _normalize_section(item: dict, idx: int, output_format: str) -> dict:
    import re
    if not isinstance(item, dict):
        title = str(item).strip() or f"第{idx + 1}节"
        item = {"id": f"s{idx + 1}", "title": title}

    sec = dict(item)
    sec.setdefault("id", f"s{idx + 1}")
    sec["id"] = str(sec.get("id") or f"s{idx + 1}")
    sec["title"] = str(sec.get("title") or f"第{idx + 1}节").strip() or f"第{idx + 1}节"
    sec["content_type"] = str(sec.get("content_type") or "paragraphs")
    if sec["content_type"] not in ("paragraphs", "bullets", "table", "mixed"):
        sec["content_type"] = "paragraphs"
    sec["key_points"] = [str(k).strip() for k in _listify(sec.get("key_points")) if str(k).strip()]
    sec.setdefault("template_heading_match", None)
    sec.setdefault("layout_hint", "content")
    try:
        is_pptx = output_format in ("pptx", "ppt")
        default_chars = 200 if is_pptx else 500
        sec["target_chars"] = int(sec.get("target_chars") or sec.get("word_count") or default_chars)
    except Exception:
        sec["target_chars"] = 500
    return sec


def _fallback_sections(brief: str, output_format: str, n: int = 6) -> list[dict]:
    """Minimal fallback when LLM outline generation fails."""
    if output_format in ("pptx", "ppt"):
        titles = ["背景与目标", "现状分析", "核心发现", "关键数据", "结论与建议", "行动计划"]
    elif output_format in ("xlsx", "excel", "xls"):
        titles = ["数据汇总", "趋势分析", "对比分析", "关键指标", "风险评估", "建议"]
    else:
        titles = ["摘要", "背景与目标", "现状分析", "核心发现", "结论与建议", "附录"]
    titles = titles[:n]
    return [
        {
            "id": f"s{i + 1}",
            "title": t,
            "content_type": "paragraphs",
            "key_points": [],
            "target_chars": 500,
            "layout_hint": "content",
            "template_heading_match": None,
        }
        for i, t in enumerate(titles)
    ]


def _narrative_framework_note(framework: str, output_format: str) -> str:
    """P1-1: Return a structural constraint block for the LLM outline prompt.
    P2-1: Extended to provide PPTX-specific storyboard guidance.
    """
    if output_format in ("xlsx", "excel", "xls"):
        return ""  # Not applicable to spreadsheets

    # P2-1: PPTX-specific narrative frameworks — storyboard-style slide sequencing
    if output_format in ("pptx", "ppt"):
        if framework == "SCR":
            return (
                "\n【PPTX叙事框架：SCR（情境-复杂性-解决方案）】"
                "幻灯片顺序应体现：封面/议程 → 现状与背景（1-2页）→ 核心挑战/机会（1-2页）"
                " → 解决方案/行动（2-3页）→ 成果与建议（1-2页）→ 总结/下一步"
            )
        if framework == "Problem-Solution":
            return (
                "\n【PPTX叙事框架：Problem-Solution】"
                "幻灯片顺序：封面 → 问题现状（数据佐证）→ 根因分析 → 解决方案对比 → 推荐方案详解 → 实施路径 → 总结"
            )
        if framework == "Data-Driven":
            return (
                "\n【PPTX叙事框架：Data-Driven】"
                "幻灯片顺序：核心数据大图（big_number布局）→ 趋势分析（图表页）→ 分项拆解 → 对比分析 → 结论与行动建议"
                "；优先使用 big_number 和 comparison 布局突出关键指标"
            )
        if framework == "Chronological":
            return (
                "\n【PPTX叙事框架：Chronological】"
                "幻灯片按时间线排列，每阶段使用 section_header 布局作为分隔页，"
                "阶段内用 content/big_number 布局展示具体内容"
            )
        return ""

    # DOCX frameworks
    if framework == "SCR":
        return (
            "\n【叙事框架：SCR（情境-复杂性-解决方案）】"
            "章节顺序应体现：1.现状背景 → 2.核心挑战/机会 → 3.行动/解决方案 → 4.成果/建议"
        )
    if framework == "Problem-Solution":
        return (
            "\n【叙事框架：Problem-Solution】"
            "章节顺序：1.问题识别 → 2.根因分析 → 3.解决方案 → 4.预期效果与风险"
        )
    if framework == "Data-Driven":
        return (
            "\n【叙事框架：Data-Driven】"
            "章节顺序：1.核心数据发现 → 2.趋势与对比分析 → 3.数据支撑的结论 → 4.行动建议"
        )
    if framework == "Chronological":
        return (
            "\n【叙事框架：Chronological】"
            "章节按时间线或阶段顺序排列，每章对应一个时间段或工作阶段"
        )
    return ""


def _ensure_pptx_agenda_slide(outline: dict) -> dict:
    """R16-P1: Auto-insert an 'agenda' slide as slide 2 for presentations with 5+ sections.

    Professional presentations always show a table of contents after the cover slide
    so the audience knows the structure upfront.  If no agenda/TOC slide is already
    present in the first 3 positions, one is inserted automatically.

    The bullets list the titles of the main content sections (not section_header
    dividers or the cover itself), capped at 6 items for readability.
    """
    _AGENDA_KEYWORDS = {"议程", "目录", "agenda", "outline", "contents", "overview", "概览", "今日"}
    sections = outline.get("sections", [])
    if len(sections) < 5:
        return outline  # short decks don't need a formal agenda slide

    # Check whether an agenda slide already exists within the first 3 slides
    for s in sections[:3]:
        title_lower = s.get("title", "").lower()
        if any(kw in title_lower for kw in _AGENDA_KEYWORDS):
            return outline  # already present — do nothing

    # Collect agenda items: non-section_header slide titles, skip the very first (cover)
    agenda_bullets: list[str] = []
    for s in sections[1:]:
        layout = s.get("layout_hint", "content")
        title = s.get("title", "")
        if layout != "section_header" and title:
            agenda_bullets.append(title[:35])
        if len(agenda_bullets) >= 6:
            break

    if not agenda_bullets:
        return outline

    agenda_slide = {
        "id": "s_agenda",
        "title": "今日议程",
        "content_type": "bullets",
        "key_points": agenda_bullets,
        "target_chars": 150,
        "layout_hint": "content",
        "template_heading_match": None,
    }

    # Insert after first slide (cover); preserve all remaining slides
    new_sections = [sections[0], agenda_slide] + list(sections[1:])
    outline["sections"] = new_sections
    logger.info("[PLAN] Inserted agenda slide with %d items", len(agenda_bullets))
    return outline


def _ensure_pptx_closing_slide(outline: dict) -> dict:
    """P3-3: Guarantee the last PPTX section is a conclusion/CTA slide.

    If the last section title already contains conclusion keywords, return unchanged.
    Otherwise append a minimal closing slide with layout_hint='content' and a
    generic 'conclusion' content_type so spec_gen generates a proper wrap-up.
    """
    _CTA_KEYWORDS = {
        "总结", "结论", "建议", "下一步", "行动", "展望", "问答", "附录",
        "conclusion", "next steps", "summary", "recommendations", "action", "q&a",
    }
    sections = outline.get("sections", [])
    if not sections:
        return outline

    last_title = sections[-1].get("title", "").lower()
    has_closing = any(kw in last_title for kw in _CTA_KEYWORDS)
    if has_closing:
        return outline

    new_id = f"s_close{len(sections) + 1}"
    closing_slide = {
        "id": new_id,
        "title": "结论与下一步行动",
        "content_type": "bullets",
        "key_points": ["核心结论汇总", "行动建议", "下一步计划"],
        "target_chars": 200,
        "layout_hint": "content",
        "template_heading_match": None,
    }
    outline["sections"] = list(sections) + [closing_slide]
    return outline
