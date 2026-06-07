"""Delivery-time quality helpers for exported PPTX/DOCX artifacts."""
from __future__ import annotations

import re


_SOURCE_MARKER_PATTERNS = [
    # Inline Chinese source labels emitted for QA grounding.
    re.compile(r"\s*[\[【]\s*(?:KB\s*)?来源\s*[：:]\s*[^\]】]+[\]】]"),
    re.compile(r"\s*[\[【]\s*(?:数据)?来源\s*[：:]\s*附件（[^）]+）\s*[\]】]"),
    re.compile(r"\s*[\[【]\s*基于行业惯例[，,]\s*无直接来源\s*[\]】]"),
    # Claim-verification metadata that should never appear in the polished draft.
    re.compile(
        r"\s*[\[【]\s*"
        r"(?:source_id|source_anchor|support_level|confidence|evidence_id|claim_id|来源ID|证据ID)"
        r"\s*[：:=]\s*[^\]】]+[\]】]",
        re.I,
    ),
    # Compact source refs occasionally emitted by skills.
    re.compile(r"\s*\[(?:SRC|SOURCE|EVIDENCE|CITE)\s*[:#][^\]]+\]", re.I),
    # Leaked uploaded/source filenames without brackets, e.g. "来源：example.xlsx".
    re.compile(r"\s*[（(]?\s*(?:数据)?来源\s*[：:]\s*example\.(?:xlsx|xls|csv|docx|pdf|pptx)\s*[）)]?", re.I),
    re.compile(r"\s*example\.(?:xlsx|xls|csv|docx|pdf|pptx)\s*", re.I),
]

_SOURCE_ONLY_LINE_RE = re.compile(
    r"^\s*(?:"
    r"(?:source_id|source_anchor|support_level|confidence|evidence_id|claim_id)\s*[：:=].*|"
    r"(?:来源ID|证据ID|来源锚点|支持等级|置信度)\s*[：:：].*"
    r")\s*$",
    re.I,
)

_SOURCE_SECTION_HEADING_RE = re.compile(
    r"^#{1,3}\s*(?:资料来源与引用说明|数据来源列表|来源清单|证据锚点|Source Registry)\s*$",
    re.I,
)

_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$")
_REPORT_YEAR_RE = re.compile(r"(?<!\d)(20[2-3]\d)(?=年|年度|年报|报告)")
_GENERIC_REPEAT_HEADINGS = {"小结", "本章小结", "风险提示", "附录"}


def infer_requested_report_year(context: str | None) -> str | None:
    """Infer an explicitly requested reporting year from user-facing context."""
    if not context:
        return None
    years = _REPORT_YEAR_RE.findall(context)
    return years[0] if years else None


def _normalize_heading_key(text: str) -> str:
    text = re.sub(r"^[一二三四五六七八九十\d]+[、.．]\s*", "", text or "")
    text = re.sub(r"\s+", "", text)
    return text.strip("：:;；。")


def remove_duplicate_markdown_headings(markdown_content: str) -> str:
    """Remove repeated generated section headings while preserving generic summaries."""
    if not markdown_content:
        return ""
    seen: set[str] = set()
    output: list[str] = []
    for raw in markdown_content.splitlines():
        match = _MARKDOWN_HEADING_RE.match(raw.strip())
        if match:
            key = _normalize_heading_key(match.group(2))
            if key and key not in _GENERIC_REPEAT_HEADINGS:
                if key in seen:
                    continue
                seen.add(key)
        output.append(raw)
    return "\n".join(output)


def normalize_report_years(markdown_content: str, requested_year: str | None) -> str:
    """Align top-level reporting-period phrases with the year requested by the user.

    This intentionally avoids replacing prior-year comparisons such as "较2024年".
    It only fixes phrases that name the report period itself.
    """
    if not markdown_content or not requested_year:
        return markdown_content or ""
    year = str(requested_year)
    replacements = [
        (r"截至20[2-3]\d年(12月31日|末|年底)", fr"截至{year}年\1"),
        (r"20[2-3]\d年(全年|年度|年末|年底)", fr"{year}年\1"),
        (r"(报告期|本报告期|期内)20[2-3]\d年", fr"\g<1>{year}年"),
    ]
    cleaned = markdown_content
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)
    return cleaned


def polish_final_report_markdown(markdown_content: str, context_text: str | None = None) -> str:
    """Apply deterministic final-delivery cleanup before DOCX/PDF/PPT export."""
    cleaned = strip_internal_source_markers(markdown_content)
    cleaned = remove_duplicate_markdown_headings(cleaned)
    cleaned = normalize_report_years(cleaned, infer_requested_report_year(context_text))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def merge_slidespec_sections(sections: list[dict], section_outline: dict | None) -> list[dict]:
    """Carry outline SlideSpec metadata into final PPTX rendering sections."""
    outline_sections = (section_outline or {}).get("sections") or []
    if not outline_sections:
        return sections

    by_title = {
        (item.get("title") or "").strip(): item
        for item in outline_sections
        if isinstance(item, dict) and item.get("title")
    }
    merged = []
    for idx, section in enumerate(sections):
        title = (section.get("title") or "").strip()
        meta = by_title.get(title)
        if meta is None and idx < len(outline_sections):
            candidate = outline_sections[idx]
            meta = candidate if isinstance(candidate, dict) else {}
        meta = meta or {}
        item = {**meta, **section}
        item["title"] = section.get("title") or meta.get("title") or f"第{idx + 1}节"
        item["content"] = section.get("content") or meta.get("description") or ""
        if not item.get("key_message"):
            item["key_message"] = meta.get("viz_point") or meta.get("description") or item["title"]
        if not item.get("content_hints"):
            item["content_hints"] = meta.get("content_hints") or meta.get("data_points") or []
        merged.append(item)
    return merged


def build_source_registry(files: list, output_index: dict | None) -> list[dict]:
    """Build a compact, auditable source registry for Word/PPT evaluation."""
    registry: list[dict] = []
    for idx, file in enumerate(files or [], start=1):
        content = (getattr(file, "extracted_text", "") or "").strip()
        registry.append({
            "id": f"来源{idx}",
            "title": getattr(file, "original_name", "") or f"上传资料{idx}",
            "type": "uploaded_file",
            "content": content[:1200],
        })

    evidence_pack = (output_index or {}).get("evidence_pack") or {}
    evidence_items = list(evidence_pack.get("direct") or []) + list(evidence_pack.get("supporting") or [])
    for item in evidence_items[:8]:
        if not isinstance(item, dict):
            continue
        title = item.get("source") or item.get("title") or "知识库/证据包片段"
        content = item.get("text") or item.get("content") or item.get("quote") or ""
        registry.append({
            "id": f"来源{len(registry) + 1}",
            "title": str(title)[:120],
            "type": item.get("type") or "evidence_pack",
            "content": str(content)[:1200],
        })

    for item in ((output_index or {}).get("rag_results") or [])[:10]:
        if not isinstance(item, dict):
            continue
        registry.append({
            "id": f"来源{len(registry) + 1}",
            "title": item.get("doc_title") or item.get("source_id") or "知识库片段",
            "type": "knowledge_base",
            "content": str(item.get("content") or "")[:1200],
            "source_id": item.get("source_id"),
            "score": item.get("score"),
        })

    seen = set()
    deduped = []
    for item in registry:
        key = (item.get("title"), item.get("content", "")[:160])
        if key in seen:
            continue
        seen.add(key)
        item["id"] = f"来源{len(deduped) + 1}"
        deduped.append(item)
    return deduped


def append_source_appendix(markdown_content: str, source_registry: list[dict]) -> str:
    if "资料来源与引用说明" in (markdown_content or ""):
        return markdown_content
    lines = [
        "## 资料来源与引用说明",
        "",
        "以下来源用于支撑正文事实、数据表格和判断；未能直接从来源确认的内容在正文中按资料缺口或假设处理。",
    ]
    if not source_registry:
        lines.append("- 暂未登记可审计来源；正文中的事实和数字应按资料缺口/假设处理，并在交付前补充知识库或上传文件。")
    for item in source_registry:
        snippet = (item.get("content") or "").replace("\n", " ").strip()
        snippet = snippet[:140] + ("..." if len(snippet) > 140 else "")
        source_type = item.get("type") or "source"
        lines.append(f"- [{item.get('id')}] {item.get('title')}（{source_type}）：{snippet or '仅登记来源，未抽取到可展示文本。'}")
    return f"{(markdown_content or '').strip()}\n\n" + "\n".join(lines)


def strip_internal_source_markers(markdown_content: str) -> str:
    """Remove QA-only source identifiers from the final user-facing draft.

    The generation and QA phases may use source labels such as ``[来源：xxx]``
    or ``[source_id:S1]`` to verify claims. Final artifacts should not expose
    uploaded filenames, KB ids, source anchors, or confidence metadata unless
    the user explicitly asked for a bibliography. This keeps the polished report
    clean while preserving upstream auditability in ``output_index``.
    """
    if not markdown_content:
        return ""

    lines: list[str] = []
    skipping_source_section = False
    for raw in markdown_content.splitlines():
        line = raw.rstrip()
        if _SOURCE_SECTION_HEADING_RE.match(line):
            skipping_source_section = True
            continue
        if skipping_source_section:
            if re.match(r"^#{1,3}\s+\S+", line):
                skipping_source_section = False
            else:
                continue
        if _SOURCE_ONLY_LINE_RE.match(line):
            continue
        for pattern in _SOURCE_MARKER_PATTERNS:
            line = pattern.sub("", line)
        line = re.sub(r"\s+([，。；：,.!?;:])", r"\1", line)
        line = re.sub(r"[ \t]{2,}", " ", line).rstrip()
        lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def repair_ppt_sections_for_quality(sections: list[dict], issues: list[str] | None = None) -> list[dict]:
    """Deterministically compact SlideSpec sections before PPT regeneration.

    This is the delivery-time repair leg of the render-review-regenerate loop:
    it reduces text density, keeps one message per slide, and shifts unknown or
    overfull layouts to safer content-card/data layouts.
    """
    repaired = []
    issue_text = " ".join(issues or [])
    for section in sections:
        item = dict(section)
        content = item.get("content", "") or ""
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        table_lines = [l for l in lines if "|" in l and l.count("|") >= 2]
        bullet_lines = [
            re.sub(r"^[•\-*▪·]\s*", "", l).strip()
            for l in lines
            if not (l.startswith("#") or ("|" in l and l.count("|") >= 2))
        ]
        unique = []
        for line in bullet_lines:
            if line and line not in unique:
                unique.append(line[:46])
            if len(unique) >= 4:
                break

        if table_lines and item.get("slide_type") in ("data", "chart-donut", "comparison"):
            item["content"] = "\n".join(table_lines[:6] + [f"- {b}" for b in unique[:2]])
        else:
            key = item.get("key_message") or item.get("viz_point") or (unique[0] if unique else "")
            body = [key[:58]] if key else []
            body.extend(f"- {b}" for b in unique[:4] if b != key)
            item["content"] = "\n".join(body) or content[:180]

        if len(item.get("content", "")) > 260 or "密度过高" in issue_text:
            item["content"] = "\n".join(item["content"].splitlines()[:5])
        if not item.get("slide_type"):
            item["slide_type"] = "content-cards"
        if item.get("slide_type") in ("split-visual", "magazine") and "裁切" in issue_text:
            item["slide_type"] = "content-cards"
        item["content_hints"] = (item.get("content_hints") or [])[:3]
        repaired.append(item)
    return repaired
