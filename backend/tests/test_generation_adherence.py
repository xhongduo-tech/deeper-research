from app.services.orchestrator import (
    _draft_addresses_user_need,
    build_evidence_pack,
    build_quality_gate,
    build_requirement_contract,
    build_source_grounded_draft,
)
from app.services.request_intelligence import (
    chart_policy_for_request,
    normalize_requested_title,
    temporal_policy_for_request,
)


def test_source_grounded_fallback_uses_user_topic_not_first_file_heading():
    uploaded = [
        """
        2025年年终述职材料
        团支部全年完成1次推优、2次政治学习、1次主题团日活动。
        TestLLM平台累计实现50余款模型上下线，承载近亿次访问流量。
        BRDC.ai一期建设完成，二期设计进入尾声。
        """
    ]

    draft = build_source_grounded_draft(
        "围绕BRDC.ai平台商业化路径，制作面向管理层的8页PPT，突出风险、收益和行动计划",
        "专项研究",
        uploaded,
        "pptx",
    )

    assert "商业化路径" in draft or "BRDC.ai" in draft
    assert "风险" in draft or "行动建议" in draft or "行动计划" in draft
    assert "年度履职主线" not in draft
    assert "综合履职：服务大局做到实处" not in draft


def test_draft_need_guard_catches_unrelated_generic_output():
    brief = "请分析新能源车出口欧洲的合规风险和渠道策略"
    unrelated = "## 执行摘要\n\n本报告分析公司收入、成本和利润趋势，并提出经营管理建议。"
    related = "## 合规风险\n\n新能源车出口欧洲需要重点关注认证、关税和渠道策略。"

    assert not _draft_addresses_user_need(unrelated, brief)
    assert _draft_addresses_user_need(related, brief)


def test_requirement_contract_and_evidence_pack_are_request_ranked():
    brief = "请围绕新能源车出口欧洲，分析合规风险、渠道策略和上市行动计划"
    uploaded = [
        "欧洲市场要求车辆满足认证与电池法规，2025年渠道合作成本上升约12%。\n"
        "国内售后团队培训完成率达到90%，但与出口欧洲合规风险无直接关系。"
    ]

    contract = build_requirement_contract(brief, "pptx", "风险评估")
    evidence_pack = build_evidence_pack(brief, uploaded)

    assert "合规" in contract["must_cover"]
    assert "风险" in contract["must_cover"]
    assert contract["source_policy"].startswith("用户输入决定主题")
    assert evidence_pack["sources_count"] == 1
    assert evidence_pack["direct"]
    assert any("欧洲" in item["matched_terms"] for item in evidence_pack["direct"])


def test_request_intelligence_normalizes_title_year_and_chart_policy():
    brief = "生成2026年述职报告"

    assert normalize_requested_title("", brief, "述职报告") == "2026年述职报告"

    temporal = temporal_policy_for_request(brief, "述职报告")
    assert temporal["primary_year"] == "2026"
    assert "2025年" in temporal["instruction"]

    chart_policy = chart_policy_for_request(brief, "述职报告", "docx")
    assert chart_policy["allowed"] is False
    assert chart_policy["mode"] == "tables_only"

    research_policy = chart_policy_for_request("整理新能源出口欧洲专项研究报告", "专项研究", "docx")
    assert research_policy["allowed"] is True
    assert research_policy["mode"] == "rich_charting"

    reference_brief = "参考我2025年的述职报告生成2026年述职报告"
    assert normalize_requested_title("", reference_brief, "述职报告") == "2026年述职报告"
    assert temporal_policy_for_request(reference_brief, "述职报告")["primary_year"] == "2026"


def test_requirement_contract_carries_title_time_and_chart_constraints():
    contract = build_requirement_contract("生成2026年述职报告", "docx", "述职报告")

    assert contract["normalized_title"] == "2026年述职报告"
    assert contract["temporal_policy"]["primary_year"] == "2026"
    assert not contract["chart_policy"]["allowed"]


def test_quality_gate_blocks_content_that_ignores_user_need():
    gate = build_quality_gate(
        "## 执行摘要\n\n本报告分析公司收入、成本和利润趋势。",
        "请分析新能源车出口欧洲的合规风险和渠道策略",
        "docx",
        uploaded_texts=None,
    )

    assert not gate["passed"]
    assert "内容未明显覆盖用户输入框需求" in gate["blockers"]
