"""Deterministic generation evaluation for PPT/Word delivery artifacts."""
from __future__ import annotations

import re
from typing import Any


def _contains_number(text: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|％|万|亿|元|年|月|项|个|次|倍)?", text or ""))


def _score(items: list[dict[str, Any]]) -> float:
    if not items:
        return 1.0
    return sum(1 for item in items if item["passed"]) / len(items)


def evaluate_generation(
    *,
    output_format: str,
    brief: str,
    sections: list[dict],
    source_registry: list[dict] | None = None,
    artifact_metrics: dict | None = None,
) -> dict:
    """Evaluate generated content using a PresentBench-style checklist.

    This is intentionally deterministic and cheap: it gives the pipeline a
    repeatable quality signal even when no judge model is available.
    """
    fmt = (output_format or "").lower()
    normalized_sections = [
        s if isinstance(s, dict) else {"title": f"Section {idx + 1}", "content": str(s or "")}
        for idx, s in enumerate(sections or [])
    ]
    text = "\n\n".join(
        f"{s.get('title', '')}\n{s.get('content', '')}" for s in normalized_sections
    )
    source_registry = source_registry or []
    artifact_metrics = artifact_metrics or {}
    is_ppt = fmt in {"ppt", "pptx", "powerpoint"}
    is_doc = fmt in {"word", "doc", "docx", "wps"}
    is_sheet = fmt in {"excel", "sheet", "xlsx", "xls"}

    fundamentals = [
        {"id": "F001", "name": "has_sections", "passed": len(normalized_sections) >= (4 if is_ppt else 3)},
        {"id": "F002", "name": "answers_user_need", "passed": bool(brief and any(token in text for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", brief)[:8]))},
        {"id": "F003", "name": "no_empty_sections", "passed": all((s.get("content") or "").strip() for s in normalized_sections)},
    ]

    grounding = [
        {"id": "G001", "name": "source_registry_exists", "passed": bool(source_registry)},
        {"id": "G002", "name": "numbers_have_source_context", "passed": (not _contains_number(text)) or bool(source_registry)},
        {"id": "G003", "name": "no_failure_placeholders", "passed": not any(marker in text for marker in ("章节生成失败", "LLM 不可用", "需要人工补充"))},
    ]

    if is_ppt:
        visual_qa = artifact_metrics.get("render_visual_qa") or {}
        visual_rendered = visual_qa.get("rendered") is True
        visual_score = visual_qa.get("overall_score")
        layout_items = [
            {"id": "P001", "name": "slidespec_metadata_present", "passed": any(s.get("slide_type") or s.get("role") for s in normalized_sections)},
            {"id": "P002", "name": "one_message_density", "passed": all(len((s.get("content") or "").splitlines()) <= 12 for s in normalized_sections)},
            {"id": "P003", "name": "aesthetic_score_passed", "passed": artifact_metrics.get("overall_score", 0) >= 70 if artifact_metrics else False},
            {"id": "P004", "name": "render_visual_qa_available", "passed": visual_rendered or bool(visual_qa.get("issues"))},
            {"id": "P005", "name": "render_visual_score_passed", "passed": (not visual_rendered) or (visual_score is not None and visual_score >= 72)},
        ]
    elif is_doc:
        claim_verification = artifact_metrics.get("claim_verification") or {}
        layout_items = [
            {"id": "W001", "name": "source_appendix_present", "passed": "资料来源" in text or "引用说明" in text},
            {"id": "W002", "name": "tables_have_source_guidance", "passed": ("|" not in text) or ("来源" in text)},
            {"id": "W003", "name": "document_has_substructure", "passed": len(normalized_sections) >= 3 and len(text) >= 500},
            {"id": "W004", "name": "numeric_claims_verified", "passed": claim_verification.get("passed", True)},
            {"id": "W005", "name": "claim_source_map_present", "passed": bool(claim_verification.get("claim_source_map")) or not _contains_number(text)},
        ]
    elif is_sheet:
        excel_quality = artifact_metrics.get("excel_quality") or {}
        layout_items = [
            {"id": "X001", "name": "artifact_nonempty", "passed": bool(text.strip())},
            {"id": "X002", "name": "workbook_qa_passed", "passed": excel_quality.get("passed") is True},
            {"id": "X003", "name": "formula_or_table_model_present", "passed": excel_quality.get("formula_count", 0) > 0 or excel_quality.get("table_like_sheet_count", 0) > 0},
            {"id": "X004", "name": "provenance_present", "passed": bool(source_registry) or excel_quality.get("source_note_count", 0) > 0},
            {"id": "X005", "name": "numeric_cells_or_analysis_present", "passed": excel_quality.get("numeric_cell_count", 0) > 0 or _contains_number(text)},
        ]
    else:
        layout_items = [
            {"id": "X001", "name": "artifact_nonempty", "passed": bool(text.strip())},
        ]

    dimensions = {
        "fundamentals": {"score": round(_score(fundamentals) * 100, 1), "items": fundamentals},
        "grounding": {"score": round(_score(grounding) * 100, 1), "items": grounding},
        "layout_and_export": {"score": round(_score(layout_items) * 100, 1), "items": layout_items},
    }
    overall = sum(v["score"] for v in dimensions.values()) / len(dimensions)
    blockers = [
        item["id"]
        for dim in dimensions.values()
        for item in dim["items"]
        if not item["passed"] and item["id"] in {"G003", "P003", "P005", "W001", "W004", "X002", "X004"}
    ]

    return {
        "overall_score": round(overall, 1),
        "passed": not blockers and overall >= 75,
        "blockers": blockers,
        "dimensions": dimensions,
        "artifact_metrics": artifact_metrics,
    }


def build_delivery_gate(
    *,
    output_format: str,
    evaluation: dict,
    artifact_metrics: dict | None = None,
) -> dict:
    """Convert evaluation into a delivery gate with block/warn decisions."""
    fmt = (output_format or "").lower()
    artifact_metrics = artifact_metrics or {}
    blockers = list(evaluation.get("blockers") or [])
    warnings: list[str] = []

    if fmt in {"ppt", "pptx", "powerpoint"}:
        visual_qa = artifact_metrics.get("render_visual_qa") or {}
        if visual_qa.get("rendered") is False:
            warnings.append("真实渲染图像QA不可用，已退回几何质量门禁")
        if artifact_metrics.get("overall_score", 100) < 60:
            blockers.append("PPT_GEOMETRY_CRITICAL")
        if visual_qa.get("rendered") is True and (visual_qa.get("overall_score") or 0) < 62:
            blockers.append("PPT_RENDER_CRITICAL")
    elif fmt in {"word", "doc", "docx", "wps"}:
        claims = artifact_metrics.get("claim_verification") or {}
        if claims.get("severe_unverified_count", 0) > 0:
            blockers.append("WORD_NUMERIC_CLAIMS_UNVERIFIED")
        elif claims.get("unverified_count", 0) > 0:
            warnings.append("存在弱匹配数字声明，已写入逐项数字核验说明")
    elif fmt in {"excel", "sheet", "xlsx", "xls"}:
        excel_quality = artifact_metrics.get("excel_quality") or {}
        if excel_quality.get("passed") is False:
            blockers.extend(excel_quality.get("blockers") or ["EXCEL_WORKBOOK_QA_FAILED"])
        for warning in excel_quality.get("warnings") or []:
            warnings.append(f"Excel QA: {warning}")

    # Keep downloads possible for soft warnings, block only correctness or severe
    # rendering failures.
    unique_blockers = []
    for item in blockers:
        if item not in unique_blockers:
            unique_blockers.append(item)
    return {
        "passed": not unique_blockers,
        "blockers": unique_blockers,
        "warnings": warnings,
        "policy": "block_on_correctness_or_severe_render_failure",
    }
