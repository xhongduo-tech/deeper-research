"""Table Builder — convert data/descriptions to professional Markdown tables for reports."""
from app.skills.base import Skill
from app.services.llm_service import chat


class TableBuilderSkill(Skill):
    name = "build_table"
    description = "将描述性文本、列表、JSON或CSV数据转换为专业格式化的Markdown表格，适合报告中的对比分析、数据汇总、指标看板"
    category = "offline"
    parameters = {
        "data": {"type": "string", "description": "数据内容（文本描述、JSON、CSV或列表）"},
        "columns": {"type": "array", "description": "期望的列名，留空自动推断最合适的列结构"},
        "table_title": {"type": "string", "description": "表格标题"},
        "table_type": {
            "type": "string",
            "description": "表格用途: comparison|metrics|timeline|risk_matrix|general，影响列结构设计",
            "default": "general",
        },
        "add_summary_row": {
            "type": "boolean",
            "description": "是否添加合计/汇总行",
            "default": False,
        },
        "add_insights": {
            "type": "boolean",
            "description": "是否在表格后附加2-3条数据洞察",
            "default": True,
        },
    }

    TABLE_TYPE_GUIDES = {
        "comparison": """对比分析表：
- 第1列为对比维度/指标名称
- 后续列为各对比对象（方案A/B/C 或 公司A/B/C）
- 末列可加"评价"或"推荐"
- 重要差异用具体数字体现，避免模糊描述""",

        "metrics": """指标看板表：
- 列结构建议：指标名称 | 当期值 | 目标值 | 同比% | 环比% | 状态
- 状态列用符号：↑达标 ↓未达标 → 持平
- 数值格式统一（金额统一万元/亿元，比率统一X.X%）
- 合计/均值放最后一行""",

        "timeline": """时间序列表：
- 第1列为时间（年/季度/月）
- 后续列为各指标数值
- 包含同比或环比变化列（用 +X.X% 或 -X.X% 格式）
- 建议包含累计列""",

        "risk_matrix": """风险矩阵表：
- 列结构：风险名称 | 风险类别 | 发生概率 | 影响程度 | 综合等级 | 缓释措施 | 负责人
- 概率和影响使用：高/中/低
- 综合等级使用颜色词：红色（极高）/橙色（高）/黄色（中）/绿色（低）
- 按综合等级从高到低排序""",

        "general": """通用数据表：
- 根据数据内容自动选择最合适的列结构
- 确保表头清晰，包含计量单位
- 数值格式规范统一
- 适当使用分隔行区分不同类别""",
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        data = params.get("data", "")
        columns = params.get("columns", [])
        title = params.get("table_title", "")
        table_type = params.get("table_type", "general")
        add_summary = params.get("add_summary_row", False)
        add_insights = params.get("add_insights", True)

        if not data.strip():
            return {"result": "", "error": "no data provided"}

        type_guide = self.TABLE_TYPE_GUIDES.get(table_type, self.TABLE_TYPE_GUIDES["general"])
        col_hint = f"\n指定列结构: {', '.join(columns)}" if columns else "\n（自动推断最合适的列结构）"
        summary_hint = "\n最后一行为合计/汇总，标注\"合计\"或\"平均\"。" if add_summary else ""
        title_line = f"**表格标题: {title}**\n\n" if title else ""
        insights_hint = "\n\n在表格后追加3条基于数据的关键洞察，格式：\n> 洞察1：...\n> 洞察2：...\n> 洞察3：..." if add_insights else ""

        messages = [
            {
                "role": "system",
                "content": "你是专业数据整理专家，擅长将各类数据转化为清晰规范的Markdown表格。数字精确，格式统一，表格信息密度高。",
            },
            {
                "role": "user",
                "content": f"""{title_line}请将以下内容整理为专业的Markdown表格。

## 表格类型指导
{type_guide}
{col_hint}{summary_hint}

## 数据内容
{data[:5000]}

## 输出格式要求
1. 输出标准Markdown表格（|列名|列名|格式）
2. 数值格式规范（同类数字对齐，百分比保留1位小数，金额加单位）
3. 表格应有5-15行有意义的数据行（不足时合理推断补充）
4. 表头加粗效果通过管道符实现，不需要额外标注{insights_hint}

仅输出表格（和洞察），不要额外说明文字。""",
            },
        ]
        result = await chat(messages, temperature=0.2, max_tokens=2000)
        return {"result": result, "table_type": table_type}
