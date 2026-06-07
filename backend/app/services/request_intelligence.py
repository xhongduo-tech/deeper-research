import re


CHART_INTENT_RE = re.compile(
    r"(图表|图形|可视化|仪表盘|dashboard|chart|charts|echarts|"
    r"柱状图|条形图|折线图|面积图|饼图|环图|散点图|热力图|雷达图|"
    r"组合图|双轴|瀑布图|漏斗图|桑基图|树图|箱线图|直方图|组图|小多图)",
    re.I,
)

NO_CHART_RE = re.compile(r"(不要|无需|不需要|禁止|不必).{0,8}(图表|图形|可视化|chart)", re.I)

DATA_HEAVY_RE = re.compile(r"(数据分析|经营分析|指标分析|趋势分析|销售分析|财务分析|仪表盘|dashboard)", re.I)

RESEARCH_REPORT_RE = re.compile(
    r"(研究报告|专项研究|行业报告|市场研究|调研报告|白皮书|风险评估|可行性研究|"
    r"research report|white paper|market study|industry analysis)",
    re.I,
)

ACADEMIC_VISUAL_RE = re.compile(
    r"(实证研究|实验研究|实验|消融|基准测试|性能对比|迁移评估|"
    r"empirical|experiment|experiments|benchmark|ablation|"
    r"performance comparison|cross-subject|cross-dataset)",
    re.I,
)

ACADEMIC_DOCUMENT_RE = re.compile(r"(论文|paper|journal|conference|study|research)", re.I)

NARRATIVE_REPORT_RE = re.compile(r"(述职|总结|心得|发言稿|演讲稿|事迹材料|汇报材料)", re.I)

RETROSPECTIVE_RE = re.compile(r"(述职|年终|年度|工作总结|工作汇报|汇报材料|事迹材料)", re.I)

TITLE_COMMAND_RE = re.compile(
    r"^(请|麻烦|帮我|帮忙|需要|我要|我们要|给我|为我|请帮我)?"
    r"(生成|撰写|写|制作|整理|输出|创建|起草|形成|做一份|做一个|做)?",
    re.I,
)

TARGET_TITLE_RE = re.compile(
    r"(?:生成|撰写|写|制作|整理|输出|创建|起草|形成)"
    r"\s*(20\d{2}\s*年?[^，,。；;\n]{0,40}(?:报告|材料|方案|文档|PPT|表格|工作簿|总结|述职))",
    re.I,
)

TARGET_YEAR_RE = re.compile(
    r"(?:生成|撰写|写|制作|整理|输出|创建|起草|形成)\s*.{0,16}?(20\d{2})\s*年?",
    re.I,
)


def normalize_requested_title(title: str = "", brief: str = "", report_type: str = "") -> str:
    """Convert imperative prompts like "生成2026年述职报告" into document titles."""
    raw = (title or "").strip() or (brief or "").strip()
    text = re.sub(r"\s+", " ", raw).strip(" ：:，,。；;")
    target_matches = TARGET_TITLE_RE.findall(text)
    if target_matches:
        return target_matches[-1].strip(" ：:，,。；;")
    text = TITLE_COMMAND_RE.sub("", text).strip(" ：:，,。；;")

    # Keep the title short and title-like; drop common instruction tails.
    text = re.split(r"(，|,|。|；|;|\n|要求|并|同时|包含|包括|围绕|基于|根据)", text, maxsplit=1)[0].strip()
    text = re.sub(r"^(一份|一个|1份|这份)", "", text).strip()

    if text:
        return text
    if report_type:
        year = extract_primary_year(brief)
        return f"{year}年{report_type}" if year and f"{year}" not in report_type else report_type
    return "未命名报告"


def extract_primary_year(text: str) -> str:
    """Return the first explicit 20xx year in the user's goal."""
    target_matches = TARGET_YEAR_RE.findall(text or "")
    if target_matches:
        return target_matches[-1]
    match = re.search(r"(20\d{2})\s*年?", text or "")
    return match.group(1) if match else ""


def wants_charts(text: str = "", report_type: str = "", output_format: str = "") -> bool:
    """Whether the user/document type explicitly calls for visual charts."""
    combined = f"{text or ''} {report_type or ''} {output_format or ''}"
    if NO_CHART_RE.search(combined):
        return False
    if CHART_INTENT_RE.search(combined):
        return True
    if (output_format or "").lower() in {"word", "doc", "docx", "wps"}:
        if ACADEMIC_DOCUMENT_RE.search(combined) or ACADEMIC_VISUAL_RE.search(combined):
            return True
        if re.search(r"(实验报告|科研报告|研究论文|学术论文|毕业论文|课程论文|实验数据|数据文件|csv|xlsx|excel)", combined, re.I):
            return True
    if ACADEMIC_VISUAL_RE.search(combined) and ACADEMIC_DOCUMENT_RE.search(combined):
        return True
    if (output_format or "").lower() in {"excel", "sheet", "xlsx", "xls", "ppt", "pptx", "powerpoint"}:
        return DATA_HEAVY_RE.search(combined) is not None
    if NARRATIVE_REPORT_RE.search(combined):
        return False
    if RESEARCH_REPORT_RE.search(combined):
        return True
    return DATA_HEAVY_RE.search(combined) is not None


def chart_policy_for_request(text: str = "", report_type: str = "", output_format: str = "") -> dict:
    explicit = CHART_INTENT_RE.search(f"{text or ''} {report_type or ''}") is not None
    allowed = wants_charts(text, report_type, output_format)
    return {
        "allowed": allowed,
        "explicit": explicit,
        "mode": "rich_charting" if allowed else "tables_only",
        "instruction": (
            "用户或报告类型需要图表：先生成可审计 ChartSpec，再输出高质量图表；复杂场景优先组图、小多图、组合图或专业统计图。"
            if allowed
            else "用户未要求图表：Word 正文优先使用文字和必要表格，不得把普通表格自动转成装饰性图表。"
        ),
    }


def temporal_policy_for_request(text: str = "", report_type: str = "") -> dict:
    combined = f"{text or ''} {report_type or ''}"
    primary_year = extract_primary_year(combined)
    is_retrospective = RETROSPECTIVE_RE.search(combined) is not None
    if not primary_year:
        if is_retrospective:
            return {
                "primary_year": "",
                "instruction": (
                    "这是一份回顾性述职/总结文档：全程使用过去时（已完成、实现了、达成了）描述本年度工作成果，"
                    "禁止出现【将xxx】【计划xxx】【展望】等将来时表述（展望下一年的结尾段除外）。"
                ),
            }
        return {"primary_year": "", "instruction": "未指定年份：按用户材料和事实来源保持原时间口径。"}
    prev_year = str(int(primary_year) - 1)
    if is_retrospective:
        return {
            "primary_year": primary_year,
            "previous_year": prev_year,
            "instruction": (
                f"这是{primary_year}年度回顾性述职/总结文档："
                f"全程描述{primary_year}年已完成的工作成果，使用过去时（已完成、实现了、达成了）。"
                f"禁止出现【将xxx】【计划】【{primary_year}年将】等将来时（末尾展望下一年的段落除外）。"
                f"{prev_year}年数据仅作背景基线，不要大篇幅复盘{prev_year}年内容。"
                f"参考文档中的{prev_year}年内容是结构模板，需要替换为{primary_year}年的对应成果。"
            ),
        }
    return {
        "primary_year": primary_year,
        "previous_year": prev_year,
        "instruction": (
            f"目标年份是{primary_year}年：标题、章节和主叙事必须围绕{primary_year}年。"
            f"不要把{prev_year}年进展大篇幅写成{primary_year}年内容；"
            f"只有当用户或资料明确要求复盘/对比时，才可把{prev_year}年作为背景、基线或对照。"
        ),
    }
