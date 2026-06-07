"""
Shared report helpers (formerly the multi-agent orchestration engine).

The multi-agent / swarm pipelines that once lived here have been retired in favour
of the unified 7-phase pipeline (app/pipeline/). What remains are the small,
dependency-free utilities still consumed by live code:

  - add_message / add_timeline_event / update_report_status / wait_if_paused
      (conversation + report-state helpers used by chat, messages, report_service)
  - clean_generated_content / is_placeholder_content   (text hygiene)
  - build_source_grounded_draft (+ its text helpers)
      (reports.py download path: no-LLM deliverable from uploaded docs)
  - build_requirement_contract / build_evidence_pack / build_quality_gate
      (lightweight request-analysis helpers)
  - AGENT_DEFINITIONS / REPORT_TYPE_AGENTS  (UI metadata)
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.message import Message
from app.models.timeline_event import TimelineEvent
from app.services.request_intelligence import (
    chart_policy_for_request,
    normalize_requested_title,
    temporal_policy_for_request,
)

logger = logging.getLogger(__name__)

AGENT_DEFINITIONS = {
    "elin": {
        "employee_id": "elin",
        "name": "Elin",
        "role": "Intake Officer",
        "tag": "任务拆解",
        "system_prompt": "你是 Elin，任务拆解专家。将用户的研究需求分解为清晰的子任务和执行计划。输出 JSON 格式。",
    },
    "chief": {
        "employee_id": "chief",
        "name": "Chief",
        "role": "Production Supervisor",
        "tag": "编排调度",
        "system_prompt": "你是 Chief，生产主管。根据报告类型和任务复杂度，指派合适的数字员工，编排生产流程。",
    },
    "quinn": {
        "employee_id": "quinn",
        "name": "Quinn",
        "role": "Data Wrangler",
        "tag": "数据处理",
        "system_prompt": "你是 Quinn，数据工程师。分析上传的数据文件，提取关键指标，发现数据中的模式和异常。用数字说话，每个结论都要有具体数据支撑。",
    },
    "remy": {
        "employee_id": "remy",
        "name": "Remy",
        "role": "Material Analyst",
        "tag": "材料解析",
        "system_prompt": "你是 Remy，材料分析师。深入解读上传的文档材料，提取与报告主题相关的核心信息，识别关键论据和数据。",
    },
    "li_bai": {
        "employee_id": "li_bai",
        "name": "Li Bai",
        "role": "Structured Writer",
        "tag": "内容写作",
        "system_prompt": "你是 Li Bai，专业报告撰写者。基于研究发现和数据，撰写逻辑清晰、论据充分、语言专业的报告内容。善于用结构化方式呈现复杂信息，每个论点都有数据支撑。",
    },
    "iris": {
        "employee_id": "iris",
        "name": "Iris",
        "role": "Chart Maker",
        "tag": "可视化",
        "system_prompt": "你是 Iris，数据可视化专家。根据数据特征选择最合适的图表类型，生成清晰、美观、信息密度高的可视化配置。",
    },
    "sage": {
        "employee_id": "sage",
        "name": "Sage",
        "role": "QA Reviewer",
        "tag": "质量控制",
        "system_prompt": "你是 Sage，专业质量审核员。从逻辑一致性、数据准确性、内容完整性和表达专业性四个维度严格审查报告。发现问题时给出具体修改建议。",
    },
    "adler": {
        "employee_id": "adler",
        "name": "Adler",
        "role": "Risk Auditor",
        "tag": "风险评估",
        "system_prompt": "你是 Adler，风险审计师。识别报告中的风险点，量化风险等级（高/中/低），提出具体的风险缓释建议。",
    },
    "orin": {
        "employee_id": "orin",
        "name": "Orin",
        "role": "Compliance Checker",
        "tag": "合规检查",
        "system_prompt": "你是 Orin，合规检查员。确保报告内容符合相关法规和行业规范，识别潜在合规风险并给出整改建议。",
    },
    "nash": {
        "employee_id": "nash",
        "name": "Nash",
        "role": "Template Filler",
        "tag": "模板交付",
        "system_prompt": "你是 Nash，模板交付专家。将报告内容填入标准模板，确保格式规范、结构统一、排版专业。",
    },
    "milo": {
        "employee_id": "milo",
        "name": "Milo",
        "role": "Layout Designer",
        "tag": "版式设计",
        "system_prompt": "你是 Milo，版式设计师。优化报告的视觉呈现，确保层次清晰、排版美观、阅读体验专业。",
    },
    "nova": {
        "employee_id": "nova",
        "name": "Nova",
        "role": "Knowledge Enricher",
        "tag": "知识深化",
        "system_prompt": "你是 Nova，离线知识深化专家。在无互联网访问的情况下，通过深度激活LLM内部知识储备，为研究提供行业基准数据、分析框架、底层机制和情景推演，弥补缺失实时数据的能力缺口。",
    },
    "vera": {
        "employee_id": "vera",
        "name": "Vera",
        "role": "Document Analyst",
        "tag": "文档解析",
        "system_prompt": "你是 Vera，文档分析专家。深度解析上传的文档材料，提取结构化数据点、识别核心论证链条、发现知识缺口，将原始文档转化为可直接用于报告写作的结构化发现。",
    },
    "echo": {
        "employee_id": "echo",
        "name": "Echo",
        "role": "Narrative Builder",
        "tag": "叙事构建",
        "system_prompt": "你是 Echo，叙事构建专家。将碎片化的研究发现整合为连贯有力的报告叙事，确保故事线清晰、论证逻辑递进、结论水到渠成。擅长从混乱的信息中提炼主线，构建引人入胜的分析框架。",
    },
    "lyra": {
        "employee_id": "lyra",
        "name": "Lyra",
        "role": "Insight Synthesizer",
        "tag": "洞察综合",
        "system_prompt": "你是 Lyra，洞察综合专家。专门从多源数据和分析结果中提炼非显而易见的高价值洞察，发现反直觉规律、二阶效应和战略转折点。你的洞察总是超越表面趋势，直指问题本质。",
    },
}

REPORT_TYPE_AGENTS = {
    "经营分析": ["quinn", "remy", "li_bai", "iris", "sage", "adler", "nash", "milo"],
    "专项研究": ["remy", "li_bai", "iris", "sage", "nash", "milo"],
    "风险评估": ["quinn", "remy", "adler", "orin", "li_bai", "sage", "nash"],
    "合规报送": ["remy", "orin", "li_bai", "sage", "nash"],
}


def _is_ppt_format(output_format: str) -> bool:
    return (output_format or "").lower() in ("ppt", "pptx", "powerpoint")


def _is_sheet_format(output_format: str) -> bool:
    return (output_format or "").lower() in ("excel", "sheet", "xlsx", "xls")


def _is_doc_format(output_format: str) -> bool:
    return (output_format or "").lower() in ("word", "doc", "docx", "wps")


def clean_generated_content(text: str) -> str:
    """Remove assistant meta-talk and prompt-compliance boilerplate from drafts."""
    if not text:
        return ""

    cleaned_lines: list[str] = []
    label_re = re.compile(r"^\s*\*{0,2}(核心信息|要点列表|数据亮点|演讲备注|输出格式|章节要求)\*{0,2}\s*[：:]?\s*(.*)$")
    meta_re = re.compile(
        r"^\s*(好的|遵照|根据您(?:的)?指示|按照您(?:的)?要求|我将|我会|以下是|作为.*?(撰写者|Li Bai)|所有内容均符合|请注意)",
        re.I,
    )
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if meta_re.match(line):
            continue
        label_match = label_re.match(line)
        if label_match:
            tail = label_match.group(2).strip()
            if tail and not tail.startswith("["):
                cleaned_lines.append(tail)
            continue
        if line.startswith("[") and line.endswith("]"):
            continue
        cleaned_lines.append(raw)

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def is_placeholder_content(text: str) -> bool:
    """Detect failed model output that must not enter user-facing documents."""
    if not text or not text.strip():
        return True
    markers = (
        "LLM 不可用",
        "以占位完成",
        "章节生成失败",
        "需要基于实际数据人工补充",
        "[章节生成失败",
    )
    return any(marker in text for marker in markers)


def _split_source_paragraphs(source_text: str) -> list[str]:
    lines = []
    for raw in source_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("---"):
            continue
        if re.fullmatch(r"【[^】]+】", line):
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if line:
            lines.append(line)
    return lines


def _shorten_cn(text: str, limit: int = 34) -> str:
    text = re.sub(r"\s+", "", text.strip("，。；; "))
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _find_para(paragraphs: list[str], *keywords: str) -> str:
    for para in paragraphs:
        if all(k in para for k in keywords):
            return para
    return ""


def _numbers_from_text(text: str) -> list[str]:
    pattern = r"(?:近|超|逾|约|累计|全年|新增|共)?\d+(?:\.\d+)?(?:余|多)?(?:款|次|项|位|篇|期|份|%|％|亿次|万次|个|年|月|日)"
    seen = []
    for match in re.findall(pattern, text):
        if match not in seen:
            seen.append(match)
    return seen


def _sentences_from_paragraph(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])", text)
    sentences = []
    for part in parts:
        cleaned = re.sub(r"\s+", "", part.strip(" ，,。；;"))
        if len(cleaned) >= 8:
            sentences.append(cleaned)
    return sentences


STOP_REQUEST_TERMS = {
    "生成", "制作", "输出", "报告", "文档", "材料", "内容", "分析", "整理", "基于",
    "根据", "需要", "请你", "帮我", "一个", "一份", "进行", "要求", "模板", "上传",
    "用户", "主题", "相关", "完整", "专业", "深度", "中文", "英文", "包括", "以及",
}

REQUEST_MARKERS = (
    "竞品", "对比", "比较", "定价", "价格", "风险", "收益", "成本", "收入", "利润",
    "合规", "渠道", "策略", "方案", "计划", "行动", "上市", "商业化", "路径",
    "趋势", "预测", "复盘", "述职", "路演", "管理层", "投资人", "客户", "培训",
    "欧洲", "海外", "国内", "市场", "用户", "产品", "平台", "模型", "数据",
)


def _request_terms(brief: str, limit: int = 14) -> list[str]:
    """Extract task-specific terms from the user's current request."""
    if not brief:
        return []

    raw_terms: list[str] = []
    normalized = re.sub(
        r"(请|请你|帮我|需要|围绕|基于|根据|重点|突出|分析|制作|生成|输出|整理|做|和|与|及|以及|的)",
        " ",
        brief,
    )
    for token in re.split(r"[\s,，。；;：:、/|()\[\]（）【】《》<>\"'""'']+", normalized):
        token = token.strip()
        if 2 <= len(token) <= 18 and token not in STOP_REQUEST_TERMS:
            raw_terms.append(token)

    for marker in REQUEST_MARKERS:
        if marker in brief:
            raw_terms.append(marker)

    for chunk in re.findall(r"[\u4e00-\u9fffA-Za-z0-9][\u4e00-\u9fffA-Za-z0-9_-]{1,17}", brief):
        if chunk not in STOP_REQUEST_TERMS:
            raw_terms.append(chunk)

    seen = []
    for term in raw_terms:
        if term not in seen:
            seen.append(term)
        if len(seen) >= limit:
            break
    return seen


def _rank_paragraphs_for_request(paragraphs: list[str], brief: str) -> list[str]:
    """Rank source paragraphs by overlap with the user's request."""
    terms = _request_terms(brief, limit=16)
    if not terms:
        return paragraphs

    def score(para: str) -> tuple[int, int]:
        compact = re.sub(r"\s+", "", para)
        term_hits = sum(1 for term in terms if term and term in compact)
        number_hits = min(len(_numbers_from_text(para)), 4)
        return (term_hits * 3 + number_hits, min(len(compact), 600))

    ranked = sorted(paragraphs, key=score, reverse=True)
    return ranked if score(ranked[0])[0] > 0 else paragraphs


def _draft_addresses_user_need(draft: str, brief: str) -> bool:
    """Cheap guardrail: the draft should visibly reflect the user's task terms."""
    terms = [t for t in _request_terms(brief, limit=10) if len(t) >= 2]
    if not terms or not draft:
        return True
    compact = re.sub(r"\s+", "", draft)
    hits = sum(1 for term in terms if term in compact)
    return hits >= min(2, max(1, len(terms) // 3))


def build_requirement_contract(brief: str, output_format: str, report_type: str = "") -> dict:
    """Turn the input-box request into a portable production contract."""
    terms = _request_terms(brief, limit=12)
    normalized_title = normalize_requested_title("", brief, report_type)
    chart_policy = chart_policy_for_request(brief, report_type, output_format)
    temporal_policy = temporal_policy_for_request(brief, report_type)
    angle_markers = []
    marker_groups = {
        "comparison": ("竞品", "对比", "比较", "差异"),
        "risk": ("风险", "合规", "挑战", "问题"),
        "strategy": ("策略", "方案", "路径", "行动", "计划"),
        "commercial": ("商业化", "收益", "定价", "收入", "利润", "成本"),
        "trend": ("趋势", "预测", "增长", "变化"),
    }
    for label, markers in marker_groups.items():
        if any(marker in brief for marker in markers):
            angle_markers.append(label)

    return {
        "goal": brief.strip(),
        "normalized_title": normalized_title,
        "output_format": (output_format or "word").lower(),
        "report_type": report_type,
        "must_cover": terms,
        "angles": angle_markers or ["general"],
        "chart_policy": chart_policy,
        "temporal_policy": temporal_policy,
        "source_policy": "用户输入决定主题、结构和取舍；上传文件/知识库只作为证据来源；模板和 skill 只提供结构、方法和视觉约束。",
        "failure_modes": [
            "机械摘要附件而没有回答用户需求",
            "套用通用经营分析结构",
            "使用模板示例内容替代用户主题",
            "缺少证据时编造数字或结论",
            "未要求图表却自动生成装饰性图表",
            "把非目标年份的大篇幅进展写成目标年份述职内容",
        ],
    }


def build_evidence_pack(brief: str, uploaded_texts: list[str] | None) -> dict:
    """Create a compact, request-ranked evidence pack from uploaded text."""
    source_texts = uploaded_texts or []
    if not source_texts:
        return {
            "request_terms": _request_terms(brief, limit=12),
            "sources_count": 0,
            "direct": [],
            "supporting": [],
            "numbers": [],
            "gaps": ["未上传附件，需依赖知识库/研究发现/模型知识并标注不确定性"],
        }

    paragraphs = _split_source_paragraphs("\n\n".join(source_texts))
    ranked = _rank_paragraphs_for_request(paragraphs, brief)
    terms = _request_terms(brief, limit=12)

    direct: list[dict] = []
    supporting: list[dict] = []
    for para in ranked[:24]:
        compact = re.sub(r"\s+", "", para)
        matched = [term for term in terms if term in compact]
        item = {
            "text": _shorten_cn(para, 180),
            "matched_terms": matched[:6],
            "numbers": _numbers_from_text(para)[:6],
        }
        if matched:
            direct.append(item)
        elif item["numbers"]:
            supporting.append(item)
        if len(direct) >= 8 and len(supporting) >= 4:
            break

    all_numbers = []
    for text in source_texts:
        for number in _numbers_from_text(text):
            if number not in all_numbers:
                all_numbers.append(number)

    gaps = []
    if terms and not direct:
        gaps.append("上传材料与用户需求关键词重合度低，需要补充资料或显式标注假设")
    if not all_numbers:
        gaps.append("未发现可用数字，避免生成精确比例、排名或增长结论")

    return {
        "request_terms": terms,
        "sources_count": len(source_texts),
        "direct": direct[:8],
        "supporting": supporting[:6],
        "numbers": all_numbers[:16],
        "gaps": gaps,
    }


def build_quality_gate(
    draft: str,
    brief: str,
    output_format: str,
    uploaded_texts: list[str] | None = None,
) -> dict:
    """Deterministic final gate that complements LLM QA."""
    blockers = []
    warnings = []

    if is_placeholder_content(draft):
        blockers.append("生成内容包含失败占位符")
    if not _draft_addresses_user_need(draft, brief):
        blockers.append("内容未明显覆盖用户输入框需求")
    if uploaded_texts and not _draft_uses_uploaded_material(draft, uploaded_texts):
        warnings.append("已上传附件，但成稿中缺少可识别的附件事实或数字")
    if _is_ppt_format(output_format):
        slide_count = len(re.findall(r"^##\s+", draft or "", flags=re.M))
        if slide_count and slide_count < 4:
            warnings.append("PPT页数偏少，可能没有完整承载用户需求")
    if not (draft or "").strip():
        blockers.append("成稿为空")

    return {
        "passed": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "requirement_terms": _request_terms(brief, limit=12),
    }


def _requested_fallback_sections(brief: str, output_format: str) -> list[str]:
    """Build request-shaped fallback sections instead of generic business labels."""
    terms = _request_terms(brief, limit=6)
    topic = _shorten_cn("".join(terms[:2]) or brief or "用户需求", 14)
    sections = ["需求对齐", "材料证据"]
    if any(k in brief for k in ("对比", "竞品", "比较", "差异")):
        sections.append("对比分析")
    if any(k in brief for k in ("趋势", "预测", "变化", "增长")):
        sections.append("趋势判断")
    if any(k in brief for k in ("风险", "问题", "挑战", "不足")):
        sections.append("问题风险")
    if any(k in brief for k in ("建议", "方案", "策略", "计划", "行动")):
        sections.append("行动建议")
    if len(sections) < 5:
        sections.extend([f"{topic}洞察", "下一步计划"])
    if _is_sheet_format(output_format):
        return ["需求说明", "原始数据", "清洗口径", "分析模型", "图表看板", "结论说明"]
    return list(dict.fromkeys(sections))[:8]


def _title_from_paragraph(text: str, fallback: str) -> str:
    compact = re.sub(r"\s+", "", text)
    keyword_titles = [
        ("平台", "平台建设"),
        ("模型", "模型能力"),
        ("数据", "数据支撑"),
        ("培训", "能力建设"),
        ("评审", "评审与治理"),
        ("标准", "标准建设"),
        ("风险", "风险与改进"),
        ("计划", "后续计划"),
        ("建议", "行动建议"),
        ("问题", "问题诊断"),
        ("落地", "应用落地"),
        ("合作", "协同推进"),
    ]
    for key, title in keyword_titles:
        if key in compact:
            return title
    first = re.split(r"[：:，,。；;]", compact, maxsplit=1)[0]
    if 4 <= len(first) <= 14:
        return first
    return fallback


def _build_extract_slide_items(paragraph: str, max_items: int = 4) -> list[str]:
    sentences = _sentences_from_paragraph(paragraph)
    if not sentences:
        return [_shorten_cn(paragraph, 44)] if paragraph else []

    numbered = [s for s in sentences if _numbers_from_text(s)]
    selected = []
    for sentence in numbered + sentences:
        short = _shorten_cn(sentence, 46)
        if short and short not in selected:
            selected.append(short)
        if len(selected) >= max_items:
            break
    return selected


def _generic_source_grounded_draft(
    brief: str,
    report_type: str,
    source_text: str,
    output_format: str = "word",
) -> str:
    """Build a deterministic draft from uploaded material when the LLM is down."""
    paragraphs = _split_source_paragraphs(source_text)
    if not paragraphs:
        return ""

    request_title = _shorten_cn(brief, 34) if brief else f"{report_type}交付稿"
    source_title = paragraphs[0] if len(paragraphs[0]) <= 40 else ""
    title = request_title or source_title or f"{report_type}交付稿"
    body = [p for p in paragraphs[1:] if len(p) > 16] or paragraphs
    ranked_body = _rank_paragraphs_for_request(body, brief)
    numbers = _numbers_from_text(source_text)
    request_terms = _request_terms(brief, limit=10)
    normalized_title = normalize_requested_title("", brief, report_type)
    chart_policy = chart_policy_for_request(brief, report_type, output_format)
    temporal_policy = temporal_policy_for_request(brief, report_type)
    section_names = _requested_fallback_sections(brief, output_format)

    if _is_ppt_format(output_format):
        slides: list[tuple[str, list[str]]] = []
        intro_items = [
            f"用户需求：{_shorten_cn(brief, 42)}" if brief else f"交付类型：{report_type}",
            "附件只作为证据来源，页面主题按用户输入重组",
        ]
        if source_title:
            intro_items.append(f"参考材料：{_shorten_cn(source_title, 24)}")
        for para in ranked_body[:2]:
            intro_items.extend(_build_extract_slide_items(para, 2))
        if numbers:
            intro_items.append("关键数字：" + "、".join(numbers[:6]))
        slides.append((section_names[0], intro_items[:5] or [_shorten_cn(ranked_body[0] if ranked_body else title, 46)]))

        used_titles: set[str] = set()
        for idx, para in enumerate(ranked_body[:10], start=1):
            items = _build_extract_slide_items(para, 4)
            if not items:
                continue
            slide_title = section_names[idx] if idx < len(section_names) else _title_from_paragraph(para, f"材料要点{idx}")
            if slide_title in used_titles:
                slide_title = f"{slide_title}{idx}"
            used_titles.add(slide_title)
            slides.append((slide_title, items))
            if len(slides) >= 9:
                break

        if numbers:
            number_items = []
            for number in numbers[:8]:
                source_sentence = next(
                    (s for s in _sentences_from_paragraph(source_text) if number in s),
                    f"{number} 来自上传材料原文",
                )
                number_items.append(_shorten_cn(source_sentence, 46))
            slides.insert(1, ("关键数字", number_items[:5]))

        return "\n\n".join(
            f"## {heading}\n\n" + "\n".join(f"- {item}" for item in items if item)
            for heading, items in slides
        )

    section_candidates: list[str] = []
    intro = [
        f"本稿围绕用户需求【{_shorten_cn(brief, 60)}】组织内容。" if brief else "本稿基于用户上传材料组织内容。",
        "上传材料只作为事实来源，章节主题和取舍以用户当前输入为准。",
    ]
    if source_title:
        intro.append(f"主要参考材料：{source_title}")
    if request_terms:
        intro.append("需求关键词：" + "、".join(request_terms[:8]))
    if numbers:
        intro.append("原文关键数字：" + "、".join(numbers[:10]))
    section_candidates.append(f"## {section_names[0]}\n\n" + "\n\n".join(intro))

    for idx, para in enumerate(ranked_body[:12], start=1):
        heading = section_names[idx] if idx < len(section_names) else _title_from_paragraph(para, f"材料要点{idx}")
        sentences = _sentences_from_paragraph(para)
        if sentences:
            content = "\n".join(f"- {s}" for s in sentences[:5])
        else:
            content = para
        section_candidates.append(f"## {heading}\n\n{content}")

    if not section_candidates:
        section_candidates.append("## 上传材料摘录\n\n" + _shorten_cn(source_text, 1200))

    return f"# {title}\n\n" + "\n\n".join(section_candidates[:9])


def _draft_uses_uploaded_material(draft: str, uploaded_texts: list[str] | None) -> bool:
    source_text = "\n\n".join(uploaded_texts or [])
    if not source_text.strip() or not draft.strip():
        return False

    source_numbers = _numbers_from_text(source_text)
    if source_numbers and any(number in draft for number in source_numbers[:20]):
        return True

    for sentence in _sentences_from_paragraph(source_text)[:30]:
        compact = _shorten_cn(sentence, 18).rstrip("…")
        if len(compact) >= 10 and compact in draft:
            return True

    return False


def build_source_grounded_draft(
    brief: str,
    report_type: str,
    uploaded_texts: list[str] | None,
    output_format: str = "word",
) -> str:
    """Create a source-grounded deliverable from uploaded docs without model calls."""
    source_text = "\n\n".join(uploaded_texts or [])
    if not source_text.strip():
        return ""

    paragraphs = _split_source_paragraphs(source_text)
    if not paragraphs:
        return ""

    return _generic_source_grounded_draft(brief, report_type, source_text, output_format)


async def add_timeline_event(db: AsyncSession, report_id: int, event_type: str, label: str, payload: dict | None = None):
    event = TimelineEvent(
        report_id=report_id,
        event_type=event_type,
        label=label,
        payload=payload,
    )
    db.add(event)
    await db.commit()


async def add_message(db: AsyncSession, report_id: int, role: str, content: str,
                      author_id: str | None = None, author_name: str | None = None):
    msg = Message(
        report_id=report_id,
        role=role,
        author_id=author_id,
        author_name=author_name,
        content=content,
    )
    db.add(msg)
    await db.commit()
    return msg


async def update_report_status(db: AsyncSession, report: Report, status: str, progress: float, phase: str):
    report.status = status
    report.progress = progress
    report.phase = phase
    report.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)


async def wait_if_paused(db: AsyncSession, report: Report):
    """Cooperative pause point between model/tool calls."""
    while True:
        await db.refresh(report)
        if report.status != "paused":
            return
        await asyncio.sleep(1.0)

