"""
Insight Generator — non-obvious, high-value insight extraction from research findings.

Goes beyond surface-level summaries to surface counter-intuitive patterns,
second-order effects, and strategic implications that typical analysis misses.
"""
from app.skills.base import Skill
from app.services.llm_service import chat


class InsightGeneratorSkill(Skill):
    name = "generate_insights"
    description = "从研究发现中提炼非显而易见的高价值洞察：反直觉规律、二阶效应、战略含义、行动触发点，避免空洞的结论重述"
    category = "offline"
    parameters = {
        "findings": {"type": "string", "description": "研究发现内容（越详细越好）"},
        "topic": {"type": "string", "description": "研究主题"},
        "insight_type": {
            "type": "string",
            "description": "洞察类型: strategic（战略洞察）| operational（运营洞察）| risk（风险洞察）| opportunity（机会洞察）| all",
            "default": "all",
        },
        "depth": {
            "type": "string",
            "description": "深度级别: surface（表层）| deep（深层）| contrarian（反直觉）",
            "default": "deep",
        },
        "count": {
            "type": "integer",
            "description": "生成洞察数量",
            "default": 5,
        },
    }

    DEPTH_PROMPTS = {
        "surface": "识别数据中的直接模式和明显趋势",
        "deep": "挖掘数据背后的深层原因、系统性规律和结构性矛盾",
        "contrarian": "寻找反直觉的模式、被忽视的关联、颠覆常规认知的发现",
    }

    TYPE_FILTERS = {
        "strategic": ["市场定位", "竞争优势", "长期趋势", "颠覆性变化", "战略转折点"],
        "operational": ["流程瓶颈", "效率杠杆", "成本驱动因素", "执行关键点", "资源优化"],
        "risk": ["尾部风险", "系统性风险", "被低估的威胁", "风险叠加效应", "黑天鹅前兆"],
        "opportunity": ["被忽视的市场空白", "第一曲线之外的机会", "政策红利窗口", "时机性机会"],
        "all": ["战略", "运营", "风险", "机会", "跨领域关联"],
    }

    INSIGHT_FORMAT = """每条洞察按以下格式输出：

**洞察[N]：[一句话标题]**
- 发现：[具体观察到了什么（包含数据）]
- 深层原因：[为什么会这样（机制解释）]
- 战略含义：[这意味着什么，应该怎么做]
- 置信度：高/中/低（基于证据充分程度）"""

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        findings = params.get("findings", "")
        topic = params.get("topic", "")
        insight_type = params.get("insight_type", "all")
        depth = params.get("depth", "deep")
        count = min(params.get("count", 5), 10)

        if not findings and not topic:
            return {"result": "", "insights": [], "error": "findings or topic required"}

        depth_hint = self.DEPTH_PROMPTS.get(depth, self.DEPTH_PROMPTS["deep"])
        focus_areas = self.TYPE_FILTERS.get(insight_type, self.TYPE_FILTERS["all"])
        focus_str = "、".join(focus_areas)

        messages = [
            {
                "role": "system",
                "content": f"""你是顶级研究分析师，专门从复杂数据中提炼非显而易见的深层洞察。

你的洞察标准：
1. **不是重述事实**：洞察 = 事实 + 机制解释 + 战略含义
2. **不是表面趋势**：挖掘{depth_hint}
3. **有行动指向**：每条洞察能指导具体决策
4. **反常识优先**：如果结论是"显而易见的"，继续挖掘更深层的

关注维度：{focus_str}""",
            },
            {
                "role": "user",
                "content": f"""请从以下研究发现中提炼{count}条高价值洞察。

## 研究主题
{topic}

## 研究发现
{findings[:3000]}

## 洞察提炼要求
{self.INSIGHT_FORMAT}

额外要求：
- 避免"市场在增长""竞争激烈""需要关注"等空洞表述
- 优先挖掘以下类型的洞察：
  * 反直觉：表面看是A，实际上是B
  * 因果倒置：看似原因其实是结果
  * 临界点效应：在某个阈值之前/之后完全不同
  * 被忽视的先行指标：通常领先结果6-18个月
  * 结构性矛盾：两个看似合理的趋势相互冲突

请直接输出{count}条洞察：""",
            },
        ]

        result = await chat(messages, temperature=0.4, max_tokens=3000)

        insights = self._parse_insights(result)

        return {
            "result": result,
            "insights": insights,
            "insight_type": insight_type,
            "depth": depth,
            "count": len(insights),
        }

    def _parse_insights(self, text: str) -> list:
        insights = []
        lines = text.split("\n")
        current = None
        for line in lines:
            line = line.strip()
            if line.startswith("**洞察") or (line.startswith("**") and "洞察" in line[:10]):
                if current:
                    insights.append(current)
                title = line.strip("*").strip()
                if "：" in title:
                    title = title.split("：", 1)[1]
                current = {"title": title, "finding": "", "mechanism": "", "implication": "", "confidence": "中"}
            elif current and line.startswith("- 发现："):
                current["finding"] = line[5:].strip()
            elif current and line.startswith("- 深层原因："):
                current["mechanism"] = line[7:].strip()
            elif current and line.startswith("- 战略含义："):
                current["implication"] = line[7:].strip()
            elif current and line.startswith("- 置信度："):
                current["confidence"] = line[6:].strip()
        if current:
            insights.append(current)
        return insights
