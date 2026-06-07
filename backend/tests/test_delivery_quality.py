from app.services.delivery_quality import (
    append_source_appendix,
    build_source_registry,
    merge_slidespec_sections,
    polish_final_report_markdown,
    repair_ppt_sections_for_quality,
    strip_internal_source_markers,
)
from app.services.evaluation_service import evaluate_generation
from app.services.claim_verification_service import verify_claims_against_sources
from app.services.ppt_render_qa_service import combine_ppt_quality
from app.services.document_generator import generate_xlsx
from app.services.excel_quality_service import score_xlsx_workbook
from app.services.chart_render_service import chart_spec_to_echarts_option, infer_chart_spec_from_markdown_table
import zipfile
from io import BytesIO
from PIL import Image


def test_merge_slidespec_sections_preserves_outline_metadata():
    sections = [{"title": "商业化路径", "content": "- 收入模型\n- 风险控制"}]
    outline = {
        "sections": [
            {
                "title": "商业化路径",
                "role": "turning-point",
                "slide_type": "roadmap",
                "key_message": "三阶段推进商业化",
                "transition_note": "从机会进入执行",
            }
        ]
    }

    merged = merge_slidespec_sections(sections, outline)

    assert merged[0]["slide_type"] == "roadmap"
    assert merged[0]["role"] == "turning-point"
    assert merged[0]["key_message"] == "三阶段推进商业化"
    assert merged[0]["content"] == "- 收入模型\n- 风险控制"


def test_word_source_appendix_and_registry_are_auditable():
    class Uploaded:
        original_name = "BRDC商业化调研.docx"
        extracted_text = "2025年平台调用量增长32%，管理层要求补充收益测算。"

    registry = build_source_registry([Uploaded()], {"evidence_pack": {"supporting": [{"text": "渠道成本上涨12%"}]}})
    content = append_source_appendix("## 执行摘要\n\n平台调用量增长32%。", registry)

    assert registry[0]["id"] == "来源1"
    assert "资料来源与引用说明" in content
    assert "BRDC商业化调研.docx" in content


def test_strip_internal_source_markers_after_qa():
    draft = (
        "# 研究报告\n\n"
        "欧洲渠道成本上升12% [来源：BRDC商业化调研.docx]，需要重构代理商政策[source_id:S1]。\n\n"
        "source_anchor: p.12 table 3\n"
        "## 资料来源与引用说明\n\n"
        "- [来源1] BRDC商业化调研.docx：渠道成本上涨12%。\n\n"
        "## 行动建议\n\n"
        "优先处理认证周期和售后网络。"
    )

    cleaned = strip_internal_source_markers(draft)

    assert "BRDC商业化调研.docx" not in cleaned
    assert "source_id" not in cleaned
    assert "source_anchor" not in cleaned
    assert "资料来源与引用说明" not in cleaned
    assert "欧洲渠道成本上升12%，需要重构代理商政策。" in cleaned
    assert "## 行动建议" in cleaned


def test_polish_final_report_markdown_removes_report_artifacts():
    draft = (
        "# 研究报告\n\n"
        "## 整体经营概览\n\n"
        "截至2026年12月31日，北京分行贷款余额突破19600亿元 [来源：example.xlsx]。\n\n"
        "## 整体经营概览\n\n"
        "贷款结构继续优化【来源：附件（北京分行数据）】。\n\n"
        "## 风险分析\n\n"
        "不良率维持低位，数据来源：example.xlsx。\n"
    )

    cleaned = polish_final_report_markdown(draft, "请生成北京分行2025年报告")

    assert cleaned.count("## 整体经营概览") == 1
    assert "2026年12月31日" not in cleaned
    assert "2025年12月31日" in cleaned
    assert "example.xlsx" not in cleaned
    assert "附件（北京分行数据）" not in cleaned
    assert "来源" not in cleaned


def test_docx_uses_simplified_chinese_font_and_locale():
    from app.services.document_generator import generate_docx

    data = generate_docx(
        title="2026年述职报告",
        report_type="述职报告",
        sections=[{"title": "年度总结", "content": "风险数据服务、人工智能技术攻坚与团队建设。"}],
    )
    with zipfile.ZipFile(BytesIO(data)) as zf:
        document_xml = zf.read("word/document.xml").decode("utf-8")
        styles_xml = zf.read("word/styles.xml").decode("utf-8")
        settings_xml = zf.read("word/settings.xml").decode("utf-8")

    assert 'w:eastAsia="SimSun"' in document_xml
    assert 'w:eastAsia="SimSun"' in styles_xml
    assert 'w:ascii="Times New Roman"' in document_xml
    assert 'w:hAnsi="Times New Roman"' in styles_xml
    assert 'w:eastAsia="zh-CN"' in document_xml
    assert 'w:eastAsia="zh-CN"' in settings_xml
    assert "生成工具：DataAgent Studio" not in document_xml
    assert 'w:type="page"' not in document_xml


def test_docx_does_not_auto_render_charts_for_narrative_reports():
    from app.services.document_generator import generate_docx, _docx_should_render_charts

    sections = [{
        "title": "年度总结",
        "content": (
            "| 工作项 | 完成数 |\n"
            "| --- | --- |\n"
            "| 平台建设 | 12 |\n"
            "| 风险治理 | 8 |\n"
        ),
    }]

    assert not _docx_should_render_charts("2026年述职报告", sections, "述职报告")

    data = generate_docx(title="2026年述职报告", report_type="述职报告", sections=sections)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()

    assert not any(name.startswith("word/media/") for name in names)


def test_docx_chart_gate_opens_for_explicit_chart_reports():
    from app.services.document_generator import _docx_should_render_charts

    sections = [{"title": "经营数据", "content": "| 年份 | 收入 |\n| --- | --- |\n| 2025 | 100 |"}]

    assert _docx_should_render_charts("经营数据分析报告", sections, "图表分析报告")
    assert _docx_should_render_charts("2026年述职报告", sections, "述职报告", render_charts=True)


def test_docx_chart_gate_opens_for_research_reports_and_markers():
    from app.services.document_generator import _docx_should_render_charts

    assert _docx_should_render_charts(
        "新能源出口欧洲专项研究报告",
        [{"title": "风险趋势", "content": "认证、关税、渠道成本是核心变量。"}],
        "专项研究",
    )
    assert _docx_should_render_charts(
        "普通述职",
        [{"title": "年度总结", "content": "[CHART: bar | title=\"完成情况\" | labels=\"A,B\" | values=\"1,2\"]"}],
        "述职报告",
    )


def test_docx_toc_is_static_for_preview_renderers():
    from app.services.document_generator import generate_docx

    sections = [
        {"title": "执行摘要", "content": "核心结论。"},
        {"title": "经营概览", "content": "经营分析。"},
        {"title": "风险分析", "content": "风险分析。"},
        {"title": "行动建议", "content": "行动建议。"},
    ]

    data = generate_docx(title="北京分行2025年报告", report_type="研究报告", sections=sections)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert "w:instrText" not in document_xml
    assert "目  录" in document_xml


def test_docx_chart_gate_opens_for_empirical_academic_papers():
    from app.services.document_generator import _docx_should_render_charts

    sections = [{
        "title": "Experiments",
        "content": "We report benchmark and ablation experiments for neural signal decoding.",
    }]

    assert _docx_should_render_charts(
        "An Empirical Study of Brain-Machine Interface Neural Signal Decoding",
        sections,
        "学术论文",
    )


def test_docx_renders_executable_chart_and_figure_markers():
    from app.services.document_generator import generate_docx

    sections = [{
        "title": "Experiments",
        "content": (
            "[FIGURE: architecture | title=\"BMI decoding pipeline\" | "
            "nodes=\"Raw EEG -> Preprocessing -> Spatial filtering -> Decoder -> Command\" | source=\"Method design\"]\n"
            "[CHART: bar | title=\"ResNet-EEG improves benchmark accuracy\" | "
            "labels=\"BCI IV-2a,BCI IV-2b,OpenBMI\" | "
            "series=\"EEGNet:76.2,80.1,71.4;ResNet-EEG:82.5,85.1,79.6\" | unit=\"%\" | source=\"Table 2\"]"
        ),
    }]

    data = generate_docx(
        title="An Empirical Study of BMI Neural Signal Decoding",
        report_type="学术论文",
        sections=sections,
    )

    with zipfile.ZipFile(BytesIO(data)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert len(media) >= 2
    assert "BMI decoding pipeline" in document_xml
    assert "ResNet-EEG improves benchmark accuracy" in document_xml


def test_docx_word_tables_use_explicit_geometry_and_repeating_header():
    from app.services.document_generator import generate_docx

    sections = [{
        "title": "Main Results",
        "content": (
            "| Method | BCI IV-2a | BCI IV-2b | Params (M) |\n"
            "|---|---:|---:|---:|\n"
            "| EEGNet | 76.2+-5.4 | 80.1+-4.9 | 0.02 |\n"
            "| ResNet-EEG (Ours) | 82.5+-4.3 | 85.1+-3.8 | 1.84 |\n"
        ),
    }]

    data = generate_docx(title="BMI Empirical Paper", report_type="学术论文", sections=sections)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert 'w:tblHeader w:val="true"' in document_xml
    assert '<w:tblGrid>' in document_xml
    assert 'w:tblLayout w:type="fixed"' in document_xml or 'w:tblW w:type="dxa"' in document_xml
    assert "82.5±4.3" in document_xml


def test_academic_figure_pack_renders_multi_panel_png():
    from app.services.chart_render_service import render_academic_figure_pack

    png = render_academic_figure_pack("ablation_subject", {
        "title": "Ablation and subject-wise analysis",
        "variants": "Full Model,w/o Adaptive Filtering,w/o Residual Connections,Single-scale CNN",
        "ablation_values": "82.5,78.3,76.1,73.2",
        "subjects": "S01,S02,S03,S04,S05",
        "baseline_values": "68.2,77.5,74.6,66.4,70.5",
        "ours_values": "79.4,87.6,85.0,78.3,78.0",
        "caption": "Figure 4. Ablation and subject-wise analysis.",
    })

    assert png
    img = Image.open(BytesIO(png))
    assert img.width >= 1800
    assert img.height >= 700


def test_academic_figure_pack_renders_ablation_bar_png():
    from app.services.chart_render_service import render_academic_figure_pack

    png = render_academic_figure_pack("ablation_bar", {
        "title": "Ablation study",
        "variants": "Full Model,w/o Spatial Filter,w/o Residual,Single-scale CNN",
        "ablation_values": "82.5,78.3,76.1,73.2",
    })

    assert png
    img = Image.open(BytesIO(png))
    assert img.width >= 1600
    assert img.height >= 700


def test_general_chart_packs_render_offline_pngs():
    from app.services.chart_render_service import render_academic_figure_pack

    business = render_academic_figure_pack("business_overview", {
        "title": "Enterprise revenue drives acceleration",
        "periods": "Q1,Q2,Q3,Q4",
        "revenue_values": "120,138,156,184",
        "growth_values": "8,15,13,18",
        "categories": "Enterprise,SMB,Channel,Other",
        "category_values": "96,54,28,6",
        "kpis": "ARR:184;Gross margin:72;Net retention:118;New logos:42",
        "caption": "Figure. Operating dashboard.",
    })
    funnel = render_academic_figure_pack("conversion_funnel", {
        "title": "Trial conversion is the bottleneck",
        "stages": "Visitors,Signups,Trials,Qualified,Customers",
        "values": "50000,8200,3100,1240,560",
        "series": "Organic:18000,3800,1600,720,360;Paid:22000,3000,980,330,120",
        "caption": "Figure. Funnel analysis.",
    })
    risk = render_academic_figure_pack("risk_matrix", {
        "title": "Risk exposure matrix",
        "risks": "Data quality,Model drift,Vendor lock-in,Compliance",
        "probability": "4.2,3.6,3.8,2.8",
        "impact": "4.6,4.0,4.3,4.8",
        "categories": "Technology,Compliance,Operations",
        "category_values": "38,24,18",
        "caption": "Figure. Risk matrix.",
    })

    for png in (business, funnel, risk):
        assert png
        img = Image.open(BytesIO(png))
        assert img.width >= 1600
        assert img.height >= 700


def test_docx_renders_academic_figure_pack_marker_and_table_caption():
    from app.services.document_generator import generate_docx

    sections = [{
        "title": "Experiments",
        "content": (
            "Table 2. Classification accuracy (%) on public EEG datasets.\n"
            "| Method | BCI IV-2a | BCI IV-2b | OpenBMI |\n"
            "|---|---:|---:|---:|\n"
            "| EEGNet | 78.3+-5.2 | 81.2+-4.5 | 73.5+-4.6 |\n"
            "| ResNet-EEG (Ours) | 82.5+-4.3 | 85.1+-3.8 | 77.8+-4.1 |\n"
            "[ACADEMIC_FIGURE: benchmark_comparison | title=\"Cross-dataset performance comparison\" | "
            "datasets=\"BCI IV-2a,BCI IV-2b,OpenBMI\" | "
            "series=\"EEGNet:78.3,81.2,73.5;ResNet-EEG (Ours):82.5,85.1,77.8\" | "
            "caption=\"Figure 3. Cross-dataset performance comparison across benchmark datasets.\" | source=\"Table 2\"]"
        ),
    }]

    data = generate_docx(title="An Empirical Study of BMI Neural Signal Decoding", report_type="学术论文", sections=sections)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert media
    assert "Table 2." in document_xml
    assert "Figure 3." in document_xml
    assert "Cross-dataset performance comparison" in document_xml


def test_docx_renders_general_chart_pack_marker():
    from app.services.document_generator import generate_docx

    sections = [{
        "title": "Operating Dashboard",
        "content": (
            "Figure 2 summarizes the operating dashboard.\n"
            "[CHART_PACK: business_overview | title=\"Enterprise revenue drives acceleration\" | "
            "periods=\"Q1,Q2,Q3,Q4\" | revenue_values=\"120,138,156,184\" | growth_values=\"8,15,13,18\" | "
            "categories=\"Enterprise,SMB,Channel,Other\" | category_values=\"96,54,28,6\" | "
            "kpis=\"ARR:184;Gross margin:72;Net retention:118;New logos:42\" | "
            "caption=\"Figure 2. Operating dashboard combining trend, mix, growth and KPI snapshot.\" | source=\"Management data\"]"
        ),
    }]

    data = generate_docx(title="经营分析图表报告", report_type="经营分析", sections=sections, render_charts=True)
    with zipfile.ZipFile(BytesIO(data)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert media
    assert "Figure 2." in document_xml
    assert "Operating dashboard" in document_xml


def test_academic_docx_auto_charts_only_result_tables():
    from app.services.document_generator import generate_docx

    data = generate_docx(
        title="An Empirical Study of BMI Neural Signal Decoding",
        report_type="学术论文",
        sections=[{
            "title": "Method and Results",
            "content": (
                "Table 1. Architecture configuration for the proposed decoder.\n"
                "| Layer / Block | Output Shape | Kernel / Stride | Params |\n"
                "|---|---|---|---:|\n"
                "| Input | C x T | — | 0 |\n"
                "| Temporal Conv | F x T | 7 / 2 | 12000 |\n"
                "\n"
                "Table 2. Classification accuracy (%) across benchmark datasets.\n"
                "| Method | BCI IV-2a | BCI IV-2b | OpenBMI |\n"
                "|---|---:|---:|---:|\n"
                "| EEGNet | 78.3+-5.2 | 81.2+-4.5 | 73.5+-4.6 |\n"
                "| DeepConvNet | 72.5+-6.8 | 75.8+-5.5 | 68.1+-5.5 |\n"
                "| ResNet-EEG (Ours) | 82.5+-4.3 | 85.1+-3.8 | 77.8+-4.1 |\n"
            ),
        }],
    )

    with zipfile.ZipFile(BytesIO(data)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert len(media) == 1
    assert "Architecture configuration" in document_xml
    assert "Cross-dataset performance comparison derived from the main results table" in document_xml


def test_academic_docx_autocompletes_missing_complex_figure_packs():
    from app.services.document_generator import generate_docx

    data = generate_docx(
        title="An Empirical Study of BMI Neural Signal Decoding",
        report_type="学术论文",
        sections=[{
            "title": "Experimental Results",
            "content": (
                "Figure 2 shows the training loss and validation accuracy curves on BCI IV-2a.\n\n"
                "Table 2. Classification accuracy (%) across benchmark datasets.\n"
                "| Method | BCI IV-2a | BCI IV-2b | OpenBMI |\n"
                "|---|---:|---:|---:|\n"
                "| CNN Baseline | 73.2+-6.1 | 78.0+-5.3 | 70.4+-5.1 |\n"
                "| EEGNet | 78.3+-5.2 | 81.2+-4.5 | 73.5+-4.6 |\n"
                "| ResNet-EEG (Ours) | 82.5+-4.3 | 85.1+-3.8 | 77.8+-4.1 |\n\n"
                "Figure 5 shows temporal decoding analysis and frequency band importance.\n"
            ),
        }],
    )

    with zipfile.ZipFile(BytesIO(data)) as zf:
        media = [name for name in zf.namelist() if name.startswith("word/media/")]
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert len(media) >= 3
    assert "Figure 2." in document_xml
    assert "Figure 5." in document_xml
    assert "Training dynamics" in document_xml
    assert "frequency band importance" in document_xml


def test_docx_and_evaluation_tolerate_string_sections():
    from app.services.document_generator import generate_docx

    data = generate_docx(
        title="字符串章节容错",
        report_type="测试",
        sections=["这是一段直接返回的章节文本。"],
    )
    result = evaluate_generation(
        output_format="docx",
        brief="字符串章节容错",
        sections=["这是一段直接返回的章节文本。"],
        source_registry=[],
    )

    with zipfile.ZipFile(BytesIO(data)) as zf:
        document_xml = zf.read("word/document.xml").decode("utf-8")

    assert "这是一段直接返回的章节文本" in document_xml
    assert "overall_score" in result


def test_word_source_appendix_marks_missing_sources():
    content = append_source_appendix("## 执行摘要\n\n需要补齐来源。", [])

    assert "资料来源与引用说明" in content
    assert "暂未登记可审计来源" in content


def test_generation_evaluation_blocks_missing_quality_signals():
    sections = [{"title": "执行摘要", "content": "收入增长32%，但未标注来源。"}]

    result = evaluate_generation(
        output_format="docx",
        brief="请分析收入增长和风险",
        sections=sections,
        source_registry=[],
        artifact_metrics={
            "claim_verification": {
                "passed": False,
                "severe_unverified_count": 1,
                "unverified_count": 1,
            }
        },
    )

    assert not result["passed"]
    assert "W001" in result["blockers"]
    assert "W004" in result["blockers"]


def test_generation_evaluation_accepts_ppt_with_slidespec_and_aesthetic_score():
    sections = [
        {"title": "开场", "content": "增长32%。", "slide_type": "number-showcase", "role": "hook"},
        {"title": "风险", "content": "合规与渠道风险。", "slide_type": "comparison"},
        {"title": "路径", "content": "三阶段推进。", "slide_type": "roadmap"},
        {"title": "行动", "content": "明确负责人。", "slide_type": "quote-cinematic"},
    ]

    result = evaluate_generation(
        output_format="pptx",
        brief="请分析增长、风险和行动路径",
        sections=sections,
        source_registry=[{"id": "来源1", "title": "调研", "content": "增长32%"}],
        artifact_metrics={
            "overall_score": 82,
            "passed": True,
            "render_visual_qa": {
                "rendered": True,
                "overall_score": 78,
                "passed": True,
                "issues": [],
            },
        },
    )

    assert result["passed"]
    assert result["dimensions"]["layout_and_export"]["score"] == 100.0


def test_claim_verification_matches_uploaded_excel_like_numbers():
    text = "2025年收入增长32%，成本上涨12%。（来源：上传Excel）"
    sources = [{
        "id": "来源1",
        "title": "经营数据.xlsx",
        "type": "uploaded_file",
        "content": "年度,收入增长,成本上涨\n2025年,32%,12%",
    }]

    result = verify_claims_against_sources(text, sources)

    assert result["passed"]
    assert result["verified_count"] >= 1
    assert result["claim_source_map"][0]["support_level"] in {"direct", "calculated"}
    assert result["claim_source_map"][0]["numeric_lineage"]["source_id"] == "来源1"


def test_claim_verification_blocks_high_stakes_partial_number_mismatch():
    text = "2025年收入增长32%，利润率提升18%。"
    sources = [{
        "id": "来源1",
        "title": "经营数据.xlsx",
        "type": "uploaded_file",
        "content": "年度,收入增长,利润率\n2025年,32%,12%",
    }]

    result = verify_claims_against_sources(text, sources)

    assert not result["passed"]
    assert result["severe_unverified_count"] >= 1


def test_ppt_quality_combines_rendered_visual_score():
    combined = combine_ppt_quality(
        {"overall_score": 80, "passed": True, "slide_count": 4, "worst_slides": []},
        {"rendered": True, "overall_score": 76, "passed": True, "slide_count": 4, "worst_slides": [], "issues": []},
    )

    assert combined["passed"]
    assert combined["render_visual_score"] == 76


def test_repair_ppt_sections_compacts_dense_content():
    sections = [{
        "title": "复杂页",
        "slide_type": "split-visual",
        "content": "\n".join([f"- 很长的要点{i}，包含大量说明文字和解释" for i in range(8)]),
    }]

    repaired = repair_ppt_sections_for_quality(sections, ["密度过高", "裁切"])

    assert repaired[0]["slide_type"] == "content-cards"
    assert len(repaired[0]["content"].splitlines()) <= 5


def test_excel_workbook_quality_scores_real_xlsx_artifact():
    data = generate_xlsx(
        title="经营数据分析",
        report_type="数据分析",
        sections=[{
            "title": "区域收入分析",
            "content": (
                "| 区域 | 收入（万元） | 成本（万元） |\n"
                "| --- | ---: | ---: |\n"
                "| 华北 | 120 | 80 |\n"
                "| 华东 | 150 | 90 |\n"
                "| 华南 | 90 | 70 |"
            ),
        }],
    )

    quality = score_xlsx_workbook(data, source_registry=[{"id": "来源1", "title": "经营数据.xlsx"}])

    assert quality["passed"]
    assert quality["formula_count"] > 0
    assert quality["table_like_sheet_count"] >= 1
    assert quality["frozen_panes_count"] > 0


def test_chart_spec_infers_pie_and_line_from_markdown_tables():
    share_spec = infer_chart_spec_from_markdown_table([
        "| 渠道 | 收入占比 |",
        "| --- | ---: |",
        "| 直营 | 52% |",
        "| 渠道 | 31% |",
        "| 生态 | 17% |",
    ], title_hint="渠道结构")
    trend_spec = infer_chart_spec_from_markdown_table([
        "| 年份 | 收入（万元） |",
        "| --- | ---: |",
        "| 2023年 | 100 |",
        "| 2024年 | 126 |",
        "| 2025年 | 168 |",
    ], title_hint="收入趋势")

    assert share_spec.chart_type in {"pie", "donut"}
    assert share_spec.unit == "%"
    assert trend_spec.chart_type == "line"
    assert trend_spec.series[0].values == [100, 126, 168]


def test_chart_spec_infers_combo_chart_and_echarts_option():
    spec = infer_chart_spec_from_markdown_table([
        "| 年份 | 收入（万元） | 同比增长率 |",
        "| --- | ---: | ---: |",
        "| 2023年 | 100 | 8% |",
        "| 2024年 | 126 | 26% |",
        "| 2025年 | 168 | 33% |",
    ], title_hint="收入增长")

    option = chart_spec_to_echarts_option(spec)

    assert spec.chart_type == "combo"
    assert spec.unit == "万元"
    assert spec.secondary_unit == "%"
    assert option["series"][0]["type"] == "bar"
    assert option["series"][1]["type"] == "line"
    assert option["series"][1]["yAxisIndex"] == 1


def test_generation_evaluation_blocks_failed_excel_workbook_qa():
    result = evaluate_generation(
        output_format="xlsx",
        brief="分析销售明细",
        sections=[{"title": "摘要", "content": "收入增长32%。"} for _ in range(3)],
        source_registry=[],
        artifact_metrics={
            "excel_quality": {
                "passed": False,
                "overall_score": 50,
                "blockers": ["XLSX-P001"],
                "warnings": [],
            }
        },
    )

    assert not result["passed"]
    assert "X002" in result["blockers"]
    assert "X004" in result["blockers"]
