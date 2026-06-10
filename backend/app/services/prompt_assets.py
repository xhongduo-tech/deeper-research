from pathlib import Path
import re

from app.config import settings
from app.services.request_intelligence import wants_charts


ASSET_DIR = Path(__file__).resolve().parent.parent / "prompt_assets"
SHARED_SKILL_CONTRACT = "skills/_shared/kimi_style_skill_contract.md"
PPT_TEMPLATE_DIR = ASSET_DIR / "ppt_templates"

PPT_FORMATS = {"ppt", "pptx", "powerpoint"}
DOC_FORMATS = {"word", "doc", "docx", "wps"}
SHEET_FORMATS = {"excel", "sheet", "xlsx", "xls"}

PPT_TEMPLATE_FILE_MAP = {
    "自由风格": "free-style.pptx",
    "蔚蓝冲击": "azure-impact.pptx",
    "铅灰未来": "graphite-future.pptx",
    "清风水蓝": "aqua-breeze.pptx",
    "墨草锋线": "emerald-edge.pptx",
    "矽岩律动": "silicon-rhythm.pptx",
}

SKILL_REFERENCE_LABELS = {
    "data-grounding": {
        "evidence_priority.md": "证据优先级",
        "extraction_rules.md": "抽取规则",
    },
    "academic-paper-authoring": {
        "structure_narrative_contract.md": "顶会论文结构叙事契约",
    },
    "excel-modeling": {
        "data_modeling_rules.md": "数据建模规则",
        "workbook_contract.md": "工作簿契约",
        "chart_dashboard_rules.md": "图表与仪表板",
    },
    "advanced-charting": {
        "chart_spec_contract.md": "图表规格契约",
        "complex_chart_rules.md": "复合图表规则",
    },
    "format-conversion": {
        "conversion_matrix.md": "格式转换矩阵",
        "render_fidelity_checks.md": "渲染保真检查",
    },
    "intake-planner": {
        "input_priority.md": "输入优先级",
        "dynamic_queue.md": "动态队列",
    },
    "ppt-director": {
        "slidespec_schema.md": "SlideSpec 模式",
        "design_critic.md": "设计批判",
        "competitive_bar.md": "质量标杆",
    },
    "ppt-layout": {
        "pptd_contract.md": "PPTD 模板契约",
        "layout_selection.md": "版式选择",
        "fit_and_typography.md": "文字适配",
    },
    "ppt-narrative": {
        "storyline_contract.md": "故事线契约",
        "content_grounding.md": "内容溯源",
        "slide_writing_rules.md": "页面写作规则",
    },
    "qa-verification": {
        "fact_logic_checks.md": "事实与逻辑检查",
        "format_export_checks.md": "格式与导出检查",
        "qa_report_schema.md": "QA 报告模式",
    },
    "word-authoring": {
        "document_structure.md": "文档结构",
        "style_contract.md": "样式契约",
    },
    "document-chief-planner": {
        "planning_contract.md": "规划契约",
        "skill_routing.md": "技能路由",
        "timeline_contract.md": "流程时间线",
        "document_quality_bar.md": "文档质量标准",
        "professional_document_matrix.md": "专业文档矩阵",
        "target_derivation.md": "目标文档推导",
    },
    "reference-style-miner": {
        "style_profile_schema.md": "示例风格画像",
        "content_isolation.md": "示例内容隔离",
        "target_reference_boundary.md": "目标与参考边界",
    },
    "skill-factory": {
        "skill_file_schema.md": "Skill 文件结构",
        "skill_depth_rubric.md": "Skill 深度标准",
    },
    "citation-bibliography": {
        "citation_styles.md": "引用格式",
        "claim_source_map.md": "论点来源映射",
    },
    "table-figure-authoring": {
        "table_figure_specs.md": "图表表格规格",
        "visual_selection.md": "可视化选择",
    },
    "executive-summary": {
        "summary_patterns.md": "摘要模式",
    },
    "prd-authoring": {
        "prd_schema.md": "PRD 结构",
    },
}

SKILL_PURPOSES = {
    "data-grounding": ("Remy / Vera", "从上传文件、知识库和表格中抽取事实、数字、章节与不确定性"),
    "excel-modeling": ("Quinn / Iris", "建立指标口径、分析台账、透视结构、图表和导出工作簿规则"),
    "advanced-charting": ("Iris / Milo", "把表格、指标和分析目标转成饼图、柱状图、折线图、组合图与 ECharts/Office 图表规格"),
    "format-conversion": ("Milo / Orin", "执行 DOCX/PPTX/XLSX/PDF/HTML/Markdown 的离线格式转换、渲染保真和交付回读检查"),
    "intake-planner": ("Elin", "把用户输入、附件、模板和输出格式转成动态任务队列，锁定格式轨道"),
    "ppt-director": ("Milo / Sage", "生成 SlideSpec、选择页面角色、执行设计批判并约束预览导出同源"),
    "ppt-narrative": ("Li Bai / Echo", "生成页级故事线、结论式标题、短要点和备注"),
    "ppt-layout": ("Milo / Nash", "按 .pptd 契约完成版式选择、文字适配和 PPTX 导出"),
    "qa-verification": ("Sage / Adler / Orin", "执行事实、逻辑、格式、合规和交付完整性终检"),
    "word-authoring": ("Li Bai / Sage", "规划章节、撰写正文、处理表格图表并导出 DOCX"),
    "academic-paper-authoring": ("Li Bai / Sage", "生成学术论文结构、顶会叙事契约、引用规则、方法/实验/结论和学术 QA"),
    "research-report-authoring": ("Remy / Li Bai", "生成研究框架、方法论、洞察、趋势、建议矩阵和报告 QA"),
    "official-document-authoring": ("Elin / Sage", "生成公文、会议纪要、新闻稿和行政商务材料的正式结构与责任闭环"),
    "legal-document-authoring": ("Adler / Sage", "生成合同、协议、招投标等条款结构、风险提示和法务格式检查"),
    "business-document-authoring": ("Quinn / Li Bai", "生成商业计划、可研、述职、经营方案中的业务逻辑、数据口径和行动计划"),
    "technical-document-authoring": ("Vera / Quinn / Li Bai", "生成技术方案、PRD、培训手册和实施文档的规格、架构、验收与运维说明"),
    "document-chief-planner": ("Elin / Vera", "将问题、附件、参考示例、输出格式和 skills 转成可执行规划与动态队列"),
    "reference-style-miner": ("Vera / Milo", "分析参考示例的结构、版式、图表、语气和内容隔离规则"),
    "skill-factory": ("Sage / Vera", "从用户上传参考文档生成完整 SKILL.md 并给出路由、测试和安全规则"),
    "citation-bibliography": ("Sage / Remy", "管理引用、脚注、来源标注、论点来源映射和杜绝伪造引用"),
    "table-figure-authoring": ("Quinn / Iris / Milo", "生成 Word 表格、图表、图注、来源说明和版面适配策略"),
    "executive-summary": ("Li Bai / Sage", "提炼管理层摘要、核心发现、影响和行动建议"),
    "meeting-minutes-authoring": ("Elin / Sage", "生成会议纪要、议题摘要、决议清单和行动跟踪表"),
    "press-release-authoring": ("Echo / Sage", "生成新闻稿导语、主体、引语、背景和事实核验清单"),
    "bid-proposal-authoring": ("Adler / Vera / Li Bai", "生成招投标响应矩阵、技术商务响应、附件清单和合规检查"),
    "prd-authoring": ("Vera / Quinn", "生成 PRD 的用户故事、流程、数据埋点、非功能需求和验收标准"),
    "training-manual-authoring": ("Li Bai / Sage", "生成培训手册、SOP、练习题、案例和操作检查表"),
    "feasibility-study-authoring": ("Quinn / Li Bai", "生成可行性研究的技术、经济、组织、法律、风险和结论建议"),
    "performance-review-authoring": ("Li Bai / Sage", "生成述职报告的 KPI、项目复盘、问题反思和下一阶段计划"),
    "project-retrospective-authoring": ("Quinn / Sage", "生成项目复盘的目标-过程-结果-偏差-根因-沉淀-行动闭环"),
    "policy-document-authoring": ("Elin / Adler", "生成政策解读、制度方案、实施意见、职责流程和合规检查"),
    "financial-research-authoring": ("Quinn / Li Bai / Sage", "生成卖方研报级别的业绩点评、投资简报、深度报告：盈利预测三年表、可比公司估值、情景分析概率加权目标价、催化剂日历、风险量化"),
}

REQUESTED_SKILL_ALIASES = {
    "sci-paper-cn": "academic-paper-authoring",
    "sci-paper": "academic-paper-authoring",
}


def _read_text(path: Path, max_chars: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except FileNotFoundError:
        return ""


def extract_visual_template(brief: str) -> str:
    for prefix in ("视觉模板：", "引用样式：", "模板："):
        if prefix in brief:
            value = brief.split(prefix, 1)[1].split("\n", 1)[0]
            return value.split("（", 1)[0].strip()
    return ""


def load_ppt_template_path(template_name: str) -> str | None:
    """Return an absolute bundled PPTX template path for a selected visual style."""
    name = (template_name or "").strip()
    if not name or name.startswith("自定义模板"):
        return None
    filename = PPT_TEMPLATE_FILE_MAP.get(name)
    if not filename:
        return None
    path = PPT_TEMPLATE_DIR / filename
    return str(path) if path.is_file() else None


def extract_requested_skills(brief: str) -> list[str]:
    """Extract explicit custom prompt skills from the generation brief.

    The frontend writes these as a readable line so the backend can load user
    custom skills without coupling generation to UI state.
    """
    names: list[str] = []
    for raw in re.findall(r"(?<!\S)/([a-zA-Z0-9][a-zA-Z0-9_-]{1,79})", brief or ""):
        names.append(raw)
    for prefix in ("自定义技能：", "选择技能：", "Skill 栈：", "Skill Stack:"):
        if prefix not in (brief or ""):
            continue
        value = brief.split(prefix, 1)[1].split("\n", 1)[0]
        for raw in re.split(r"[,，、;；\s]+", value):
            name = raw.strip().strip("`")
            if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,79}$", name):
                names.append(name)
    normalized = [REQUESTED_SKILL_ALIASES.get(name, name) for name in names]
    return list(dict.fromkeys(normalized))


def _safe_skill_name(name: str) -> str:
    return name if re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{1,79}$", name or "") else ""


def _user_skill_dir(user_id: int | None, name: str) -> Path | None:
    if user_id is None:
        return None
    safe_name = _safe_skill_name(name)
    if not safe_name:
        return None
    base = (Path(settings.user_skills_dir) / str(user_id)).resolve()
    target = (base / safe_name).resolve()
    if base not in target.parents:
        return None
    return target


def load_skill(name: str, max_chars: int = 4000, user_id: int | None = None) -> str:
    safe_name = _safe_skill_name(name)
    if not safe_name:
        return ""
    user_dir = _user_skill_dir(user_id, safe_name)
    skill_dir = user_dir if user_dir and (user_dir / "SKILL.md").exists() else ASSET_DIR / "skills" / safe_name
    body = _read_text(skill_dir / "SKILL.md", max_chars=max_chars)
    if not body:
        return ""

    refs: list[str] = []
    ref_paths = re.findall(r"`(references/[^`]+\.md)`", body)
    ref_paths += re.findall(r"\]\((references/[^)]+\.md)\)", body)
    ref_paths += [
        f"references/{filename}"
        for filename in SKILL_REFERENCE_LABELS.get(safe_name, {})
    ]
    for rel in dict.fromkeys(ref_paths):
        ref_text = _read_text(skill_dir / rel, max_chars=2600)
        if ref_text:
            refs.append(f"\n\n## Loaded Reference: {rel}\n{ref_text}")
    return body + "".join(refs)


REPORT_TYPE_AUTHORING_SKILLS: dict[str, str] = {
    # Business / commercial documents
    "经营分析": "business-document-authoring",
    "业务分析": "business-document-authoring",
    "商业计划": "business-document-authoring",
    "可行性研究": "feasibility-study-authoring",
    "可研报告": "feasibility-study-authoring",
    # Research reports and white papers
    "专项研究": "research-report-authoring",
    "研究报告": "research-report-authoring",
    "白皮书": "research-report-authoring",
    "行业报告": "research-report-authoring",
    "风险评估": "research-report-authoring",
    # Financial research reports
    "股票研报": "financial-research-authoring",
    "研报": "financial-research-authoring",
    "业绩点评": "financial-research-authoring",
    "投资简报": "financial-research-authoring",
    "投资报告": "financial-research-authoring",
    "深度报告": "financial-research-authoring",
    "公司研究": "financial-research-authoring",
    "卖方研报": "financial-research-authoring",
    "年报点评": "financial-research-authoring",
    "季报点评": "financial-research-authoring",
    # Academic papers
    "学术论文": "academic-paper-authoring",
    "论文": "academic-paper-authoring",
    "期刊论文": "academic-paper-authoring",
    # Legal / compliance
    "法律文件": "legal-document-authoring",
    "合同": "legal-document-authoring",
    "协议": "legal-document-authoring",
    "招投标": "bid-proposal-authoring",
    "标书": "bid-proposal-authoring",
    "投标方案": "bid-proposal-authoring",
    "合规报送": "policy-document-authoring",
    "政策文件": "policy-document-authoring",
    "政策解读": "policy-document-authoring",
    # Official / government documents
    "公文": "official-document-authoring",
    "政务文件": "official-document-authoring",
    "行政公文": "official-document-authoring",
    "通知": "official-document-authoring",
    # Meeting and review
    "会议纪要": "meeting-minutes-authoring",
    "述职报告": "performance-review-authoring",
    "绩效评估": "performance-review-authoring",
    "项目复盘": "project-retrospective-authoring",
    "复盘报告": "project-retrospective-authoring",
    # Technical documents
    "技术文档": "technical-document-authoring",
    "技术方案": "technical-document-authoring",
    "架构设计": "technical-document-authoring",
    "PRD": "prd-authoring",
    "产品需求": "prd-authoring",
    "产品需求文档": "prd-authoring",
    # Marketing / PR / training
    "新闻稿": "press-release-authoring",
    "对外公告": "press-release-authoring",
    "培训手册": "training-manual-authoring",
    "操作手册": "training-manual-authoring",
    "SOP": "training-manual-authoring",
}

AUTHORING_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "academic-paper-authoring": (
        "学术论文",
        "期刊论文",
        "会议论文",
        "论文",
        "投稿",
        "顶会",
        "cvpr",
        "iccv",
        "eccv",
        "neurips",
        "nips",
        "icml",
        "iclr",
        "acl",
        "emnlp",
        "aaai",
        "ijcai",
        "sigir",
        "kdd",
        "paper",
        "full paper",
        "related work",
        "method section",
        "experiments section",
    ),
    "research-report-authoring": (
        "专项研究",
        "研究报告",
        "白皮书",
        "行业报告",
        "调研报告",
        "风险评估",
        "趋势分析",
    ),
    "business-document-authoring": (
        "经营分析",
        "业务分析",
        "商业计划",
        "商业方案",
        "商业模式",
        "市场进入",
    ),
    "feasibility-study-authoring": (
        "可行性研究",
        "可研报告",
        "可研",
        "立项论证",
        "项目论证",
    ),
    "legal-document-authoring": (
        "法律文件",
        "合同",
        "协议",
        "条款",
        "法律意见",
    ),
    "bid-proposal-authoring": (
        "招投标",
        "标书",
        "投标方案",
        "投标文件",
        "响应文件",
    ),
    "policy-document-authoring": (
        "合规报送",
        "政策文件",
        "政策解读",
        "制度",
        "管理办法",
    ),
    "official-document-authoring": (
        "公文",
        "政务文件",
        "行政公文",
        "通知",
        "请示",
        "函",
    ),
    "meeting-minutes-authoring": (
        "会议纪要",
        "会议记录",
        "纪要",
        "行动项",
    ),
    "performance-review-authoring": (
        "述职报告",
        "绩效评估",
        "年度总结",
        "工作总结",
    ),
    "project-retrospective-authoring": (
        "项目复盘",
        "复盘报告",
        "复盘材料",
        "复盘总结",
        "postmortem",
        "post-mortem",
        "retrospective",
    ),
    "technical-document-authoring": (
        "技术文档",
        "技术方案",
        "架构设计",
        "实施方案",
        "接口文档",
    ),
    "prd-authoring": (
        "prd",
        "产品需求",
        "产品需求文档",
        "需求文档",
        "用户故事",
    ),
    "press-release-authoring": (
        "新闻稿",
        "对外公告",
        "发布稿",
        "通稿",
    ),
    "training-manual-authoring": (
        "培训手册",
        "操作手册",
        "sop",
        "教程",
        "作业指导书",
    ),
    "financial-research-authoring": (
        "股票研报",
        "研报",
        "业绩点评",
        "投资简报",
        "投资报告",
        "卖方研报",
        "券商研报",
        "深度报告",
        "公司研究",
        "个股分析",
        "上市公司分析",
        "年报点评",
        "季报点评",
        "盈利预测",
        "目标价",
        "股票分析",
        "investment brief",
        "equity research",
        "earnings review",
        "financial research",
        "target price",
        "PE估值",
        "PB估值",
        "dcf估值",
    ),
}

AUTHORING_SKILL_NEGATIONS: dict[str, tuple[str, ...]] = {
    "academic-paper-authoring": (
        "不是论文",
        "非论文",
        "不要论文",
        "不用论文",
        "不是学术论文",
        "非学术",
    ),
}


def _normalize_format(output_format: str) -> str:
    return (output_format or "").lower() or "word"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    haystack = (text or "").lower()
    return any(needle.lower() in haystack for needle in needles)


def _infer_authoring_skill(brief: str = "", report_type: str = "") -> str:
    """Infer the specialized document skill from explicit type first, then brief.

    The UI does not always pass a normalized report_type. Letting the brief
    participate keeps user language such as "写一篇 CVPR 风格论文" on the academic
    paper path without requiring another frontend selector.
    """
    explicit = REPORT_TYPE_AUTHORING_SKILLS.get(report_type or "")
    if explicit:
        return explicit

    text = f"{report_type or ''}\n{brief or ''}"
    for skill_name, blocked_phrases in AUTHORING_SKILL_NEGATIONS.items():
        if _contains_any(text, blocked_phrases):
            # Skip only the negated skill; other aliases may still match.
            continue
        if _contains_any(text, AUTHORING_SKILL_ALIASES.get(skill_name, ())):
            return skill_name

    for skill_name, aliases in AUTHORING_SKILL_ALIASES.items():
        if skill_name in AUTHORING_SKILL_NEGATIONS and _contains_any(text, AUTHORING_SKILL_NEGATIONS[skill_name]):
            continue
        if _contains_any(text, aliases):
            return skill_name
    return ""


def _skill_stack_for_format(output_format: str, brief: str = "", report_type: str = "") -> list[str]:
    fmt = _normalize_format(output_format)
    charting_needed = wants_charts(brief, report_type, fmt)
    if fmt in PPT_FORMATS:
        stack = [
            "intake-planner",
            "data-grounding",
            "advanced-charting",
            "ppt-director",
            "ppt-narrative",
            "ppt-layout",
            "format-conversion",
            "qa-verification",
        ]
    elif fmt in DOC_FORMATS:
        domain_skill = _infer_authoring_skill(brief, report_type)
        base_stack = [
            "intake-planner",
            "document-chief-planner",
            "data-grounding",
            "reference-style-miner",
        ]
        if domain_skill:
            base_stack.append(domain_skill)
        base_stack.extend([
            "table-figure-authoring",
            "citation-bibliography",
            "word-authoring",
            "format-conversion",
            "qa-verification",
        ])
        # Financial research always needs advanced charting (stock perf, valuation bands)
        is_financial = domain_skill == "financial-research-authoring"
        if charting_needed or is_financial:
            if "advanced-charting" not in base_stack:
                base_stack.insert(base_stack.index("citation-bibliography"), "advanced-charting")
        stack = base_stack
    elif fmt in SHEET_FORMATS:
        stack = [
            "intake-planner",
            "data-grounding",
            "excel-modeling",
            "advanced-charting",
            "format-conversion",
            "qa-verification",
        ]
    else:
        stack = [
            "intake-planner",
            "data-grounding",
            "advanced-charting",
            "word-authoring",
            "format-conversion",
            "qa-verification",
        ]
    # Honor user-explicitly-requested custom skills from the brief
    for name in extract_requested_skills(brief):
        safe_name = _safe_skill_name(name)
        if not safe_name:
            continue
        insert_at = max(1, len(stack) - 1)
        if safe_name not in stack:
            stack.insert(insert_at, safe_name)
    return stack


def load_pptd(template_name: str, max_chars: int = 3000) -> str:
    if not template_name:
        return _read_text(ASSET_DIR / "pptd" / "generic.pptd", max_chars=max_chars)
    return (
        _read_text(ASSET_DIR / "pptd" / f"{template_name}.pptd", max_chars=max_chars)
        or _read_text(ASSET_DIR / "pptd" / "generic.pptd", max_chars=max_chars)
    )


def _architecture_contract_for_format(fmt: str) -> str:
    """SOTA-inspired generation contract for document and deck pipelines."""
    if fmt in PPT_FORMATS:
        return """【SOTA PPT 生成架构契约】
1. Grounding first：先建立用户需求契约、证据包和来源优先级；外网搜索只在管理员开启时作为低优先级补充，关闭时完整走内网知识库与上传文件。
2. PPTAgent-style reference mining：先分析参考 PPT 的 slide-level functional type、content schema、版式密度和视觉节奏，只迁移结构和设计模式，不迁移示例事实。
3. SlideSpec before prose：先输出每页 role、claim、evidence、visual_intent、layout_family、density、speaker_note、render_risk，再写页面正文。
4. ChartSpec single source of truth：所有饼图、柱状图、折线图、组合图先生成 ChartSpec；预览用 ECharts option，PPT/DOCX 用 PNG 或原生 Office 图表，XLSX 用原生图表，数据和标题必须同源。
5. SlideSpec single source of truth：前端预览、PPTX 渲染、备注、下载和 QA 必须读取同一份 SlideSpec，不允许另起一套页面结构。
6. Hierarchical layout RAG：版式选择必须受 .pptd 模板、参考样式画像、页面角色和内容密度约束，不允许把正文直接塞进通用页。
7. PPTEval-style scoring：评测至少覆盖 Content、Design、Coherence 三维；Design 必须以真实渲染图像或离线渲染结果为主，几何指标只能作为降级信号。
8. Generate-evaluate-repair：PPTX 导出后必须执行渲染级 QA；发现溢出、遮挡、低对比、空白页、图表不可读时回写 SlideSpec/ChartSpec 并重渲染，强门禁失败默认阻断下载。
9. Render-safe delivery：最终 PPTX 应可编辑、字体可用、文本不溢出；若无法证明实时事实，标注假设或资料缺口。"""
    if fmt in DOC_FORMATS:
        return """【SOTA Word 生成架构契约】
1. Grounding first：先建立目标文档、受众、证据包、章节预算和引用边界；外网搜索只在管理员开启时作为低优先级补充，关闭时依赖内网知识库、上传文件和离线技能。
2. Plan before draft：先生成章节级 DocumentPlan，包括每章论点、证据、表格/图、引用需求、风险和完成标准。
3. Claim-first factuality：长文先拆成可核验 claims；每个数字、趋势、因果、政策、市场结论都必须有 source_id、source_anchor、support_level 和 confidence。
4. Numeric lineage：来自 Excel/CSV 的数字必须保留字段名、筛选条件、聚合公式、单位、时间口径和原始来源；推导数字必须写明公式或代码口径。
5. Self-RAG/SAFE-style critique：按“检索是否需要→证据是否相关→claim 是否被支持→答案是否回应需求”做反思式核验，不支持的 claim 改写为假设、删除或进入风险附录。
6. Multi-pass authoring：按“规划→分章起草→交叉核验→风格统一→导出自检”执行，避免一次性长文失焦。
7. Citation discipline：事实、数字、政策、市场结论必须可追溯到上传文件、知识库、明确搜索来源或标注为假设；source_id/source_anchor/[来源：...] 仅作为内部校验锚点，最终成稿必须删除这些标识。
8. Table/Figure authoring：Word 图表必须由用户显式要求、研究报告/行业报告/白皮书/风险评估、数据分析型任务或章节计划触发；普通述职、总结、发言稿等叙事文档默认只保留必要表格，不自动生成装饰性图表。触发后，表格、饼图、柱状图、折线图、组合图和组图必须先声明字段、单位、来源、图表意图和图注；导出层必须把可执行图表/图片 marker 渲染为真实图片。
9. Quality bar：所有生成内容必须高质量、凝练、结论先行；删除泛泛背景、重复铺垫和套话，每段只保留能推进结论的事实、判断或行动含义。
10. DOCX/PDF-safe formatting：标题层级、表格宽度、图注、脚注/参考文献、分页和字体必须适合 Word/PDF 交付，并经 LibreOffice/Pandoc 转换回读检查。"""
    if fmt in SHEET_FORMATS:
        return """【SOTA Excel/数据分析生成架构契约】
1. SpreadsheetLLM-style encoding：先识别工作簿/工作表/区域/表头/格式/公式/合并单元格/结构锚点，压缩成结构化 sheet map，再交给模型分析。
2. Data contract first：建立数据字典、字段类型、单位、时间范围、主键、空值、重复值、异常值、口径假设和清洗日志；原始数据不可覆盖。
3. Columnar analytics runtime：大表优先使用 DuckDB/Polars/Arrow 做本地列式读取、类型推断、SQL 聚合和异常检测；小表可退回 pandas/openpyxl。
4. LIDA-style visual pipeline：数据摘要 → 分析目标 → 可视化规格/代码 → 执行与过滤 → 图表说明；图表标题必须是结论句并绑定字段口径。
5. Complex ChartSpec：饼图/环图用于构成，柱状图用于对比，折线图用于趋势，组合图用于“绝对值 + 比率/增速”，所有图表必须能转为 ECharts option 与 Office 原生图表或 PNG。
6. Chain-of-Spreadsheet reasoning：复杂问题拆为检索相关区域、解释字段、执行计算、核对结果、写入报告/工作簿的多步链路。
7. Numeric lineage：每个关键指标必须保留 numerator、denominator、unit、period、filter、aggregation、source_range 或 source_field。
8. Workbook delivery QA：导出后读取真实 xlsx，检查摘要页、描述性 sheet 名、冻结窗格、公式、图表、口径说明和来源说明；强门禁失败默认阻断下载。
9. Offline-first：所有分析、渲染、QA 和门禁必须能在内网离线运行；联网搜索只在管理员开启时作为补充。"""
    return """【SOTA 生成架构契约】
1. 用户需求契约优先于模板和示例。
2. 证据、结构、写作、格式和 QA 分阶段执行。
3. 外网搜索只在管理员开启时作为可选补充，关闭时系统必须完整走内网知识库与离线技能。"""


def _shared_skill_contract(max_chars: int = 7000) -> str:
    return _read_text(ASSET_DIR / SHARED_SKILL_CONTRACT, max_chars=max_chars)


def build_generation_asset_context(
    output_format: str,
    brief: str,
    report_type: str = "",
    user_id: int | None = None,
) -> str:
    fmt = _normalize_format(output_format)
    chunks: list[str] = []
    chunks.append(_architecture_contract_for_format(fmt))
    shared_contract = _shared_skill_contract()
    if shared_contract:
        chunks.append("【Kimi-style 全局 Skill 运行契约】\n" + shared_contract)
    if fmt in PPT_FORMATS:
        template_name = extract_visual_template(brief)
        chunks.append("【PPT 模板定义 .pptd】\n" + load_pptd(template_name))

    for skill_name in _skill_stack_for_format(fmt, brief, report_type):
        max_chars = 6000 if skill_name == "intake-planner" else 9000
        skill_body = load_skill(skill_name, max_chars=max_chars, user_id=user_id)
        if skill_body:
            chunks.append(f"【{skill_name}】\n{skill_body}")
    return "\n\n".join(c for c in chunks if c.strip())


def build_generation_asset_manifest(
    output_format: str,
    brief: str,
    report_type: str = "",
    user_id: int | None = None,
) -> dict:
    """Return the explicit capability stack used by the generation pipeline.

    This is intentionally compact and serializable: it lets the backend keep a
    trace of which skills/assets were selected, and lets the UI show a credible
    execution runbook instead of a vague loading timeline.
    """
    fmt = _normalize_format(output_format)
    template_name = extract_visual_template(brief)
    manifest = {
        "output_format": fmt,
        "template": template_name or ("generic" if fmt in PPT_FORMATS else ""),
        "skills": [],
        "contracts": [],
        "references": [f"_shared/{Path(SHARED_SKILL_CONTRACT).name}"],
        "guards": [
            "用户显式要求优先",
            "上传文件事实优先",
            "模板仅作为视觉规则",
            "禁止示例内容进入成稿",
            "外网搜索由管理员开关独立控制",
            "所有 Skill 必须按 Trigger/Input/Output/Workflow/Structure/QA 契约解释",
            "所有输出必须高质量、凝练、结论先行，删除套话和重复铺垫",
            "来源/证据标识只用于内部 QA，最终成稿必须删除 source_id/source_anchor/[来源：...] 等标识",
        ],
    }

    def add_skill(name: str):
        owner, purpose = SKILL_PURPOSES.get(name, ("Li Bai", "执行专项生成能力"))
        refs = list(SKILL_REFERENCE_LABELS.get(name, {}).keys())
        source = "user" if _user_skill_dir(user_id, name) and (_user_skill_dir(user_id, name) / "SKILL.md").exists() else "official"
        manifest["skills"].append({"name": f"{name}/SKILL.md", "owner": owner, "purpose": purpose, "source": source})
        for ref in refs:
            ref_id = f"{name}/{ref}"
            if ref_id not in manifest["references"]:
                manifest["references"].append(ref_id)

    selected_stack = _skill_stack_for_format(fmt, brief, report_type)
    for skill_name in selected_stack:
        add_skill(skill_name)

    manifest["contracts"].append("kimi_style_skill_execution_contract")

    if fmt in PPT_FORMATS:
        manifest["contracts"].append(f"{template_name or 'generic'}.pptd")
        manifest["contracts"].append("sota_ppt_generation_contract")
        manifest["contracts"].append("pptagent_reference_decomposition_contract")
        manifest["contracts"].append("ppteval_content_design_coherence_contract")
        manifest["contracts"].append("chart_spec_to_office_render_contract")
        manifest["contracts"].append("libreoffice_pdf_render_fidelity_contract")
        manifest["guards"].extend([
            "PPT 预览、PPTX 渲染、备注和下载必须同源 SlideSpec",
            "PPT 图表必须由 ChartSpec 同源生成，组合图不支持原生时必须使用渲染 PNG 降级",
            "PPT 必须执行渲染图像级 QA；无离线渲染组件时写入 warning 并退回几何 QA",
            "PPT 交付门禁失败默认阻断下载",
        ])
    elif fmt in DOC_FORMATS:
        manifest["contracts"].append("sota_word_generation_contract")
        manifest["contracts"].append("claim_level_verification_contract")
        manifest["contracts"].append("numeric_lineage_contract")
        manifest["contracts"].append("docx_pdf_conversion_fidelity_contract")
        manifest["guards"].extend([
            "Word 每个关键 claim 必须在 QA 阶段绑定来源、计算或假设标签，最终交付前删除内部来源标识",
            "Excel/CSV 派生数字必须保留字段、公式、筛选口径和单位",
            "研究报告/行业报告/白皮书/风险评估应输出可执行图表或图包；叙事类 Word 文档只输出必要表格，不自动生成装饰性图表",
            "Word 交付门禁失败默认阻断下载",
        ])
        if "advanced-charting" in selected_stack:
            manifest["contracts"].append("table_figure_chartspec_contract")
            manifest["contracts"].append("complex_word_chart_pack_contract")
            manifest["guards"].append("Word 图表必须保留 ChartSpec、图注和来源说明，并支持组图/小多图/组合图的同源渲染")
        if "academic-paper-authoring" in selected_stack:
            manifest["contracts"].append("academic_conference_paper_structure_contract")
            manifest["contracts"].append("claim_evidence_interpretation_contract")
            manifest["guards"].extend([
                "顶会/full paper 必须保留 Title/Abstract/Introduction/Related Work/Method/Experiments/Conclusion/References",
                "Method 必须包含 3.1-3.4；Experiments 必须包含 4.1-4.3，资料不足时显式标注缺口",
                "实验论断必须遵循 Claim-Evidence-Interpretation，并先引用图表再放置图表",
            ])
    elif fmt in SHEET_FORMATS:
        manifest["contracts"].append("sota_excel_analysis_contract")
        manifest["contracts"].append("spreadsheetllm_sheet_encoding_contract")
        manifest["contracts"].append("lida_visualization_pipeline_contract")
        manifest["contracts"].append("chain_of_spreadsheet_reasoning_contract")
        manifest["contracts"].append("duckdb_polars_arrow_columnar_runtime_contract")
        manifest["contracts"].append("complex_chartspec_echarts_office_contract")
        manifest["guards"].extend([
            "Excel 关键指标必须保留口径、公式/代码和单元格/字段来源",
            "Excel 图表必须支持饼图、柱状图、折线图和绝对值+比率组合图",
            "Excel 导出后必须执行真实工作簿 QA",
            "Excel 交付门禁失败默认阻断下载",
        ])

    return manifest
