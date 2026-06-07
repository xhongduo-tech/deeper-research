from pathlib import Path

from app.services.prompt_assets import build_generation_asset_context, build_generation_asset_manifest


def skill_names(manifest: dict) -> set[str]:
    return {item["name"] for item in manifest["skills"]}


def test_all_prompt_skills_have_kimi_style_adapter():
    skill_files = sorted(Path("backend/app/prompt_assets/skills").glob("*/SKILL.md"))

    assert skill_files
    for path in skill_files:
        assert "## Kimi-Style Contract Adapter" in path.read_text(encoding="utf-8")


def test_ppt_manifest_includes_grounding_and_quality_stack():
    manifest = build_generation_asset_manifest("pptx", "生成经营分析PPT")

    assert manifest["template"] == "generic"
    assert "_shared/kimi_style_skill_contract.md" in manifest["references"]
    assert "kimi_style_skill_execution_contract" in manifest["contracts"]
    assert "generic.pptd" in manifest["contracts"]
    assert "pptagent_reference_decomposition_contract" in manifest["contracts"]
    assert "ppteval_content_design_coherence_contract" in manifest["contracts"]
    assert "PPT 预览、PPTX 渲染、备注和下载必须同源 SlideSpec" in manifest["guards"]
    assert {
        "intake-planner/SKILL.md",
        "data-grounding/SKILL.md",
        "advanced-charting/SKILL.md",
        "ppt-director/SKILL.md",
        "ppt-narrative/SKILL.md",
        "ppt-layout/SKILL.md",
        "format-conversion/SKILL.md",
        "qa-verification/SKILL.md",
    }.issubset(skill_names(manifest))
    assert "chart_spec_to_office_render_contract" in manifest["contracts"]


def test_doc_manifest_includes_word_grounding_and_qa():
    manifest = build_generation_asset_manifest("docx", "整理专项研究报告")

    assert {
        "intake-planner/SKILL.md",
        "data-grounding/SKILL.md",
        "word-authoring/SKILL.md",
        "format-conversion/SKILL.md",
        "qa-verification/SKILL.md",
    }.issubset(skill_names(manifest))
    assert "advanced-charting/SKILL.md" in skill_names(manifest)
    assert "sota_word_generation_contract" in manifest["contracts"]
    assert "claim_level_verification_contract" in manifest["contracts"]
    assert "numeric_lineage_contract" in manifest["contracts"]
    assert "table_figure_chartspec_contract" in manifest["contracts"]
    assert "Word 每个关键 claim 必须在 QA 阶段绑定来源、计算或假设标签，最终交付前删除内部来源标识" in manifest["guards"]
    assert "研究报告/行业报告/白皮书/风险评估应输出可执行图表或图包；叙事类 Word 文档只输出必要表格，不自动生成装饰性图表" in manifest["guards"]
    assert "外网搜索由管理员开关独立控制" in manifest["guards"]
    assert "所有 Skill 必须按 Trigger/Input/Output/Workflow/Structure/QA 契约解释" in manifest["guards"]
    assert "所有输出必须高质量、凝练、结论先行，删除套话和重复铺垫" in manifest["guards"]


def test_doc_manifest_activates_advanced_charting_when_requested():
    manifest = build_generation_asset_manifest("docx", "生成包含组图和复杂图表的经营数据分析报告")

    assert "advanced-charting/SKILL.md" in skill_names(manifest)
    assert "table_figure_chartspec_contract" in manifest["contracts"]
    assert "complex_word_chart_pack_contract" in manifest["contracts"]
    assert "Word 图表必须保留 ChartSpec、图注和来源说明，并支持组图/小多图/组合图的同源渲染" in manifest["guards"]


def test_doc_manifest_infers_academic_paper_stack_from_brief():
    manifest = build_generation_asset_manifest("docx", "请写一篇 CVPR 风格 full paper，包含方法、实验和消融")

    assert "academic-paper-authoring/SKILL.md" in skill_names(manifest)
    assert "advanced-charting/SKILL.md" in skill_names(manifest)
    assert "academic-paper-authoring/structure_narrative_contract.md" in manifest["references"]
    assert "academic_conference_paper_structure_contract" in manifest["contracts"]
    assert "complex_word_chart_pack_contract" in manifest["contracts"]
    assert "claim_evidence_interpretation_contract" in manifest["contracts"]
    assert "Method 必须包含 3.1-3.4；Experiments 必须包含 4.1-4.3，资料不足时显式标注缺口" in manifest["guards"]


def test_slash_sci_paper_skill_alias_routes_to_academic_stack():
    manifest = build_generation_asset_manifest(
        "docx",
        "/sci-paper-cn前往你的技能路径下，找到该技能，帮我写一篇关于Brain-machine 和neural signal的实证研究论文，要英文的，输出给我word文件。",
    )

    names = skill_names(manifest)
    assert "academic-paper-authoring/SKILL.md" in names
    assert "sci-paper-cn/SKILL.md" not in names
    assert "advanced-charting/SKILL.md" in names
    assert "complex_word_chart_pack_contract" in manifest["contracts"]


def test_academic_asset_context_loads_structure_contract_reference():
    context = build_generation_asset_context("docx", "生成一篇 NeurIPS 风格论文，要求 Related Work、Method 和 Experiments 完整")

    assert "【academic-paper-authoring】" in context
    assert "Loaded Reference: references/structure_narrative_contract.md" in context
    assert "Complete Section Hierarchy" in context


def test_sheet_manifest_includes_excel_modeling():
    manifest = build_generation_asset_manifest("xlsx", "分析销售明细并生成仪表板")

    assert {
        "intake-planner/SKILL.md",
        "data-grounding/SKILL.md",
        "excel-modeling/SKILL.md",
        "advanced-charting/SKILL.md",
        "format-conversion/SKILL.md",
        "qa-verification/SKILL.md",
    }.issubset(skill_names(manifest))
    assert "sota_excel_analysis_contract" in manifest["contracts"]
    assert "spreadsheetllm_sheet_encoding_contract" in manifest["contracts"]
    assert "lida_visualization_pipeline_contract" in manifest["contracts"]
    assert "complex_chartspec_echarts_office_contract" in manifest["contracts"]
    assert "Excel 关键指标必须保留口径、公式/代码和单元格/字段来源" in manifest["guards"]


def test_asset_context_loads_existing_references():
    context = build_generation_asset_context("docx", "生成Word研究报告")

    assert "【SOTA Word 生成架构契约】" in context
    assert "【Kimi-style 全局 Skill 运行契约】" in context
    assert "Universal Generation Funnel" in context
    assert "【data-grounding】" in context
    assert "Loaded Reference: references/evidence_priority.md" in context
    assert "【word-authoring】" in context
    assert "Claim-first factuality" in context


def test_sheet_asset_context_includes_spreadsheet_sota_contract():
    context = build_generation_asset_context("xlsx", "上传Excel后分析收入、成本并生成仪表板")

    assert "【SOTA Excel/数据分析生成架构契约】" in context
    assert "SpreadsheetLLM-style encoding" in context
    assert "LIDA-style visual pipeline" in context
    assert "Workbook delivery QA" in context
