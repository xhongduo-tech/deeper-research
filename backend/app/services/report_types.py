"""
Built-in report type registry.

Each entry defines:
  - id / label / description
  - the default section skeleton (used to render the Output Preview and
    to guide Structured Writer)
  - the default team roster (employee ids) — Supervisor may adjust at runtime

See DESIGN.md §3 for the product rationale of each type.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.agents.employees.registry import (
    RT_INTERNAL_RESEARCH,
    RT_OPS_REVIEW,
    RT_REGULATORY_FILING,
    RT_RISK_ASSESSMENT,
    RT_TRAINING_MATERIAL,
)


REPORT_TYPES: Dict[str, Dict[str, Any]] = {
    RT_OPS_REVIEW: {
        "id": RT_OPS_REVIEW,
        "label": "经营分析报告",
        "label_en": "Operating Review",
        "description": "按部门/分行/产品线拆解经营情况,围绕数据与图表给出判断与建议。",
        "typical_inputs": ["经营数据 Excel", "历史经营分析报告", "业务口径说明"],
        "typical_output": "月度/季度经营分析 Word(含图表)",
        "default_team": [
            "intake_officer",
            "material_analyst",
            "data_wrangler",
            "chart_maker",
            "structured_writer",
            "qa_reviewer",
            "layout_designer",
        ],
        "section_skeleton": [
            {"id": "exec_summary", "title": "执行摘要", "kind": "narrative"},
            {"id": "business_overview", "title": "整体经营概览", "kind": "narrative_with_chart"},
            {"id": "revenue_analysis", "title": "收入与盈利分析", "kind": "narrative_with_chart"},
            {"id": "cost_analysis", "title": "成本与效率分析", "kind": "narrative_with_chart"},
            {"id": "segment_breakdown", "title": "分板块/分行表现", "kind": "table_with_narrative"},
            {"id": "risks_and_focus", "title": "重点风险与关注事项", "kind": "narrative"},
            {"id": "next_actions", "title": "下阶段行动建议", "kind": "narrative"},
        ],
    },
    RT_INTERNAL_RESEARCH: {
        "id": RT_INTERNAL_RESEARCH,
        "label": "内部专题研究报告",
        "label_en": "Internal Research",
        "description": "针对某个主题/行业/产品的专题研究,依赖用户提供的资料,不联网检索。",
        "typical_inputs": ["行业研究资料", "内部政策文件", "历史研究报告"],
        "typical_output": "专题研究 Word",
        "default_team": [
            "intake_officer",
            "material_analyst",
            "chart_maker",
            "structured_writer",
            "compliance_checker",
            "qa_reviewer",
            "layout_designer",
        ],
        "section_skeleton": [
            {"id": "background", "title": "研究背景与目的", "kind": "narrative"},
            {"id": "scope", "title": "研究范围与方法", "kind": "narrative"},
            {"id": "market_landscape", "title": "行业/市场格局", "kind": "narrative_with_chart"},
            {"id": "key_findings", "title": "核心发现", "kind": "narrative"},
            {"id": "comparative_analysis", "title": "对比分析", "kind": "table_with_narrative"},
            {"id": "implications", "title": "对我行的启示", "kind": "narrative"},
            {"id": "appendix", "title": "附录与参考材料", "kind": "evidence_list"},
        ],
    },
    RT_RISK_ASSESSMENT: {
        "id": RT_RISK_ASSESSMENT,
        "label": "风险评估报告",
        "label_en": "Risk Assessment",
        "description": "针对单一授信/业务/事件的风险评估,产出风险矩阵 + 叙事 + 建议。",
        "typical_inputs": ["授信/业务材料", "财务报表", "历史风险档案"],
        "typical_output": "风险评估 Word(含风险矩阵)",
        "default_team": [
            "intake_officer",
            "material_analyst",
            "data_wrangler",
            "risk_auditor",
            "structured_writer",
            "compliance_checker",
            "qa_reviewer",
            "layout_designer",
        ],
        "section_skeleton": [
            {"id": "subject_profile", "title": "评估对象画像", "kind": "narrative"},
            {"id": "financial_snapshot", "title": "财务状况快照", "kind": "narrative_with_chart"},
            {"id": "risk_matrix", "title": "风险矩阵", "kind": "matrix"},
            {"id": "credit_risk", "title": "信用风险", "kind": "narrative"},
            {"id": "market_risk", "title": "市场风险", "kind": "narrative"},
            {"id": "operational_risk", "title": "操作与合规风险", "kind": "narrative"},
            {"id": "mitigation", "title": "缓释措施与建议", "kind": "narrative"},
            {"id": "conclusion", "title": "综合评级与结论", "kind": "narrative"},
        ],
    },
    RT_REGULATORY_FILING: {
        "id": RT_REGULATORY_FILING,
        "label": "合规/监管报送材料",
        "label_en": "Regulatory Filing",
        "description": "严格按监管模板填写,字段与口径不可偏离模板。",
        "typical_inputs": ["监管模板(Word/Excel)", "源数据 Excel", "既有报送材料"],
        "typical_output": "与模板同构的 Word/Excel",
        "default_team": [
            "intake_officer",
            "material_analyst",
            "template_filler",
            "compliance_checker",
            "qa_reviewer",
            "layout_designer",
        ],
        "section_skeleton": [
            {"id": "template_mirror", "title": "按模板填写(结构由模板决定)", "kind": "template_driven"},
        ],
    },
    RT_TRAINING_MATERIAL: {
        "id": RT_TRAINING_MATERIAL,
        "label": "内部培训/学习材料",
        "label_en": "Training Material",
        "description": "面向内部员工的学习材料,语言通俗、逻辑清晰、配合例子。",
        "typical_inputs": ["政策原文", "业务手册", "历史培训材料"],
        "typical_output": "培训手册 Word",
        "default_team": [
            "intake_officer",
            "material_analyst",
            "structured_writer",
            "qa_reviewer",
            "layout_designer",
        ],
        "section_skeleton": [
            {"id": "learning_goals", "title": "学习目标", "kind": "narrative"},
            {"id": "key_concepts", "title": "核心概念", "kind": "narrative"},
            {"id": "process_walkthrough", "title": "流程详解", "kind": "narrative"},
            {"id": "cases", "title": "案例演练", "kind": "narrative"},
            {"id": "faq", "title": "常见问题", "kind": "qa_list"},
            {"id": "self_check", "title": "自测题", "kind": "qa_list"},
        ],
    },
}


def list_report_types() -> List[Dict[str, Any]]:
    return list(REPORT_TYPES.values())


def get_report_type(rt: str) -> Dict[str, Any] | None:
    """Synchronous lookup for the 5 built-in types only.

    Custom types (``custom:<id>``) must be resolved asynchronously via
    :meth:`CustomReportTypeService.as_registry_entry`. Callers that also
    want to support custom types should use :func:`resolve_report_type`.
    """
    return REPORT_TYPES.get(rt)


async def resolve_report_type(db, rt: str) -> Dict[str, Any] | None:
    """Resolve either a built-in or a ``custom:<id>`` report type."""
    builtin = REPORT_TYPES.get(rt)
    if builtin:
        return builtin
    # Lazy import to avoid a circular dependency.
    from app.services.custom_report_type_service import CustomReportTypeService

    raw_id = CustomReportTypeService.parse_report_type_id(rt)
    if raw_id is None:
        return None
    return await CustomReportTypeService.as_registry_entry(db, raw_id)
