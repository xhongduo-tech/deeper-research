"""Document template standards used by Word generation.

These standards are deliberately more concrete than prompt hints: they define
required section structure and renderer-facing style metadata for common
document templates selected in the UI.
"""
from __future__ import annotations

from copy import deepcopy


_STANDARDS: dict[str, dict] = {
    "学术论文": {
        "key": "academic_paper",
        "display": "学术论文",
        "strict": True,
        "sections_zh": [
            "摘要",
            "关键词",
            "1 引言",
            "2 相关研究",
            "3 研究方法",
            "4 实验与结果",
            "5 讨论",
            "6 结论",
            "参考文献",
        ],
        "sections_en": [
            "Abstract",
            "Keywords",
            "1 Introduction",
            "2 Related Work",
            "3 Methodology",
            "4 Experiments and Results",
            "5 Discussion",
            "6 Conclusion",
            "References",
        ],
        "style_rules": [
            "必须采用学术论文结构：题名、摘要、关键词、引言、相关研究、研究方法、实验与结果、讨论、结论、参考文献。",
            "除非用户明确要求英文论文/英文摘要/英文关键词，否则章节标题和正文全部使用中文；不要输出 Abstract、Keywords、Introduction 等英文标题。",
            "摘要和关键词独立成节，参考文献为独立列表，不得省略。",
            "正文使用客观学术语气，图表必须有编号、标题和正文引用。",
        ],
        "render": {"kind": "academic", "body_font": "Times New Roman", "body_size": 10.5},
    },
    "论文": {
        "alias_of": "学术论文",
    },
    "法定公文": {
        "key": "official_document",
        "display": "法定公文",
        "strict": True,
        "sections": [
            "版头",
            "发文字号",
            "签发人",
            "标题",
            "主送机关",
            "正文",
            "附件",
            "发文机关署名",
            "成文日期",
            "印发机关和印发日期",
        ],
        "style_rules": [
            "必须符合党政机关公文基本结构：版头/发文字号/签发人/标题/主送机关/正文/附件/落款/成文日期/版记。",
            "版头使用红色大字号居中，正文使用正式公文语体，段首缩进，层级序号按 一、（一）1.（1） 组织。",
            "主送机关、附件说明、发文机关署名、成文日期位置必须完整，不能写成普通报告结构。",
        ],
        "render": {"kind": "official", "body_font": "仿宋_GB2312", "body_size": 16},
    },
    "公文": {"alias_of": "法定公文"},
    "行政公文": {"alias_of": "法定公文"},
    "实验报告": {
        "key": "lab_report",
        "display": "实验报告",
        "strict": True,
        "sections": ["实验目的", "实验原理", "实验设备与材料", "实验步骤", "实验数据与结果", "结果分析", "结论", "思考与改进"],
        "style_rules": ["实验报告必须体现目的、原理、步骤、数据、分析、结论闭环，数据表格优先于泛泛描述。"],
        "render": {"kind": "technical", "body_font": "宋体", "body_size": 11},
    },
    "教学材料": {
        "key": "teaching_material",
        "display": "教学材料",
        "strict": True,
        "sections": ["教学目标", "重点难点", "知识导入", "核心内容", "课堂活动", "练习与评价", "课后拓展"],
        "style_rules": ["教学材料必须区分目标、重难点、教学过程、练习评价，语言面向学习者。"],
        "render": {"kind": "teaching", "body_font": "宋体", "body_size": 11},
    },
    "述职报告": {
        "key": "performance_review",
        "display": "述职报告",
        "strict": True,
        "sections": ["基本情况", "履职情况", "重点工作与成效", "存在问题与原因", "下一步计划", "总结表态"],
        "style_rules": ["述职报告必须围绕职责、业绩、不足、计划组织，避免写成行业研究或泛泛总结。"],
        "render": {"kind": "report", "body_font": "宋体", "body_size": 11},
    },
    "项目复盘": {
        "key": "project_retrospective",
        "display": "项目复盘",
        "strict": True,
        "sections": ["项目背景与目标", "过程回顾", "结果达成情况", "偏差与根因分析", "经验沉淀", "改进措施与行动计划", "附录与证据"],
        "style_rules": [
            "项目复盘必须形成目标、过程、结果、偏差、根因、经验和行动闭环，避免写成普通项目介绍。",
            "所有结论应绑定证据、责任边界和可执行改进项；问题复盘应聚焦机制和事实，不做泛泛归因。",
        ],
        "render": {"kind": "report", "body_font": "宋体", "body_size": 11},
    },
    "复盘报告": {"alias_of": "项目复盘"},
    "商业计划": {
        "key": "business_plan",
        "display": "商业计划",
        "strict": True,
        "sections": ["执行摘要", "市场机会", "产品与服务", "商业模式", "竞争分析", "营销与增长", "运营计划", "财务预测", "风险与对策"],
        "style_rules": ["商业计划必须有市场、产品、模式、增长、财务和风险，不得只写愿景。"],
        "render": {"kind": "business", "body_font": "宋体", "body_size": 11},
    },
    "会议总结": {
        "key": "meeting_summary",
        "display": "会议总结",
        "strict": True,
        "sections": ["会议基本信息", "会议议题", "讨论要点", "形成决议", "行动项与责任人", "后续安排"],
        "style_rules": ["会议总结必须有决议、行动项、责任人和截止时间。"],
        "render": {"kind": "meeting", "body_font": "宋体", "body_size": 11},
    },
    "个人简历": {
        "key": "resume",
        "display": "个人简历",
        "strict": True,
        "sections": ["个人信息", "求职意向", "教育背景", "工作经历", "项目经历", "技能证书", "自我评价"],
        "style_rules": ["简历必须信息密集、条目化、强调成果量化，不写长篇散文。"],
        "render": {"kind": "resume", "body_font": "微软雅黑", "body_size": 10.5},
    },
    "企业制度": {
        "key": "policy",
        "display": "企业制度",
        "strict": True,
        "sections": ["总则", "适用范围", "职责分工", "管理要求", "流程规范", "监督考核", "附则"],
        "style_rules": ["制度文件必须条款化，明确适用范围、职责、流程、监督和附则。"],
        "render": {"kind": "policy", "body_font": "宋体", "body_size": 11},
    },
    "产品文档": {
        "key": "product_doc",
        "display": "产品文档",
        "strict": True,
        "sections": ["背景与目标", "用户与场景", "功能范围", "业务流程", "交互与页面", "数据与接口", "验收标准", "风险与依赖"],
        "style_rules": ["产品文档必须包含场景、范围、流程、交互、数据接口和验收标准。"],
        "render": {"kind": "product", "body_font": "宋体", "body_size": 11},
    },
    "测试报告": {
        "key": "test_report",
        "display": "测试报告",
        "strict": True,
        "sections": ["测试概述", "测试范围", "测试环境", "测试用例执行", "缺陷统计", "风险评估", "结论与建议"],
        "style_rules": ["测试报告必须有范围、环境、用例、缺陷统计和结论，不得只写描述性总结。"],
        "render": {"kind": "technical", "body_font": "宋体", "body_size": 11},
    },
    "运维报告": {
        "key": "ops_report",
        "display": "运维报告",
        "strict": True,
        "sections": ["运维概况", "系统运行状态", "事件与故障", "容量与性能", "安全与合规", "优化措施", "下期计划"],
        "style_rules": ["运维报告必须包含运行状态、事件、容量性能、安全和优化计划。"],
        "render": {"kind": "technical", "body_font": "宋体", "body_size": 11},
    },
    "文学创作": {
        "key": "creative_writing",
        "display": "文学创作",
        "strict": False,
        "sections": ["创作设定", "人物与视角", "情节结构", "正文创作", "风格打磨"],
        "style_rules": ["文学创作应优先保持叙事风格、人物视角和节奏，不套商业报告结构。"],
        "render": {"kind": "creative", "body_font": "宋体", "body_size": 11},
    },
}


def get_document_standard(report_type: str = "", brief: str = "") -> dict | None:
    text = f"{report_type or ''}\n{brief or ''}"
    for name, profile in _STANDARDS.items():
        if name and name in text:
            resolved = profile
            if "alias_of" in profile:
                resolved = _STANDARDS.get(profile["alias_of"], profile)
            standard = deepcopy(resolved)
            standard["matched_name"] = name
            standard["language"] = "en" if _explicit_english_requested(text) else "zh"
            if standard.get("key") == "academic_paper":
                standard["sections"] = (
                    standard.get("sections_en")
                    if standard["language"] == "en"
                    else standard.get("sections_zh")
                )
                if standard["language"] == "zh":
                    standard["render"] = {"kind": "academic", "body_font": "宋体", "body_size": 10.5}
            return standard
    return None


def format_standard_for_prompt(standard: dict | None) -> str:
    if not standard:
        return ""
    sections = standard.get("sections") or []
    rules = standard.get("style_rules") or []
    lines = [
        f"【所选文档模板标准：{standard.get('display') or standard.get('matched_name')}】",
        "这不是普通提示词偏好，而是必须执行的结构与版式标准。",
        "默认语言：中文。除非用户明确要求英文，否则所有标题、正文、摘要、关键词、图表说明和总结均使用中文。",
    ]
    if sections:
        lines.append("必须包含并优先按以下顺序组织章节：")
        lines.extend(f"{i + 1}. {title}" for i, title in enumerate(sections))
    if rules:
        lines.append("结构/格式/语体规则：")
        lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines)


def apply_standard_sections(sections: list[dict], standard: dict | None, output_format: str) -> list[dict]:
    if not standard or output_format not in ("word", "doc", "docx", "wps"):
        return sections
    required = [str(s).strip() for s in standard.get("sections") or [] if str(s).strip()]
    if not required:
        return sections

    by_title = {_norm_title(str(s.get("title", ""))): s for s in sections if isinstance(s, dict)}
    strict = bool(standard.get("strict"))
    next_sections: list[dict] = []
    for idx, title in enumerate(required):
        matched = by_title.get(_norm_title(title))
        sec = dict(matched or {})
        sec["id"] = f"s{idx + 1}"
        sec["title"] = title
        sec.setdefault("content_type", "mixed" if title.lower() not in {"abstract", "keywords", "references"} else "paragraphs")
        sec.setdefault("target_chars", _target_chars_for_standard_section(title, standard))
        sec.setdefault("layout_hint", "content")
        points = list(sec.get("key_points") or [])
        if not points:
            points = _default_key_points(title, standard)
        sec["key_points"] = points
        next_sections.append(sec)

    if not strict:
        seen = {_norm_title(s["title"]) for s in next_sections}
        for item in sections:
            title = str(item.get("title", "")).strip()
            if title and _norm_title(title) not in seen:
                clone = dict(item)
                clone["id"] = f"s{len(next_sections) + 1}"
                next_sections.append(clone)
    return next_sections


def skill_for_standard(report_type: str = "", brief: str = "") -> str | None:
    standard = get_document_standard(report_type, brief)
    if not standard:
        return None
    mapping = {
        "academic_paper": "academic-paper-authoring",
        "official_document": "official-document-authoring",
        "lab_report": "technical-document-authoring",
        "teaching_material": "training-manual-authoring",
        "performance_review": "performance-review-authoring",
        "project_retrospective": "project-retrospective-authoring",
        "business_plan": "business-document-authoring",
        "meeting_summary": "meeting-minutes-authoring",
        "policy": "policy-document-authoring",
        "product_doc": "prd-authoring",
        "test_report": "technical-document-authoring",
        "ops_report": "technical-document-authoring",
    }
    return mapping.get(standard.get("key"))


def _norm_title(title: str) -> str:
    return (
        title.lower()
        .replace(" ", "")
        .replace("：", "")
        .replace(":", "")
        .replace("一、", "")
        .replace("二、", "")
        .replace("三、", "")
    )


def _target_chars_for_standard_section(title: str, standard: dict) -> int:
    key = standard.get("key")
    lower = title.lower()
    if key == "academic_paper":
        if lower in {"abstract", "keywords", "references"} or title in {"摘要", "关键词", "参考文献"}:
            return 250
        return 900
    if key == "official_document":
        return 180 if title in {"版头", "发文字号", "签发人", "附件", "发文机关署名", "成文日期", "印发机关和印发日期"} else 900
    return 600


def _default_key_points(title: str, standard: dict) -> list[str]:
    key = standard.get("key")
    if key == "academic_paper":
        return [f"围绕用户主题撰写「{title}」，符合中文学术论文规范", "使用中文、客观、可验证、结构化的学术表达"]
    if key == "official_document":
        return [f"按法定公文规范撰写「{title}」", "保持正式、准确、可执行的公文语体"]
    return [f"围绕用户需求完成「{title}」", "符合所选模板的结构、语体和交付规范"]


def _explicit_english_requested(text: str) -> bool:
    lowered = (text or "").lower()
    patterns = [
        "英文", "英语", "english", "write in english", "in english",
        "英文论文", "英文摘要", "英文关键词", "sci", "ssci",
    ]
    negative = ["不要英文", "不用英文", "中文", "用中文", "中文论文"]
    if any(item in lowered for item in negative):
        return False
    return any(item in lowered for item in patterns)
