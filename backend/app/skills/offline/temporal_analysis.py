"""
Temporal Analysis Skill — timeline extraction and trend reasoning.

Extracts the temporal dimension hidden in text:
  - Event timeline reconstruction (even from relative time references)
  - Trend direction and inflection point detection
  - Cycle and pattern recognition (seasonal, quarterly, multi-year)
  - Future projection based on identified trends
  - Lag relationships (event A precedes event B by N periods)

Why it matters:
  - Financial reports often embed historical context that needs sequencing
  - Policy impact analysis requires understanding temporal rollout
  - Competitive intelligence needs event ordering to assess causality
  - Trend forecasting requires pattern recognition from past sequences
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router


class TemporalAnalysisSkill(Skill):
    name = "temporal_analysis"
    category = "analysis"
    description = (
        "时序分析：从文本中重建事件时间线、检测趋势拐点、识别周期性规律、"
        "进行基于趋势的未来推演；输出结构化时间线和趋势报告"
    )
    parameters = {
        "text":        {"type": "string", "description": "待分析文本"},
        "topic":       {"type": "string", "description": "分析主题（可选）", "default": ""},
        "time_range":  {"type": "string", "description": "关注的时间范围（如 2020-2025）", "default": ""},
        "project_future": {"type": "boolean", "description": "是否生成未来推演", "default": True},
    }

    async def execute(self, text: str = "", topic: str = "",
                      time_range: str = "", project_future: bool = True, **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text           = params.get("text", text)
            topic          = params.get("topic", topic)
            time_range     = params.get("time_range", time_range)
            project_future = params.get("project_future", project_future)

        context_parts = []
        if topic:
            context_parts.append(f"分析主题：{topic}")
        if time_range:
            context_parts.append(f"关注时间范围：{time_range}")
        context_line = "；".join(context_parts) if context_parts else "自动识别文中所有时间信息"

        future_section = """
  "future_projections": [
    {
      "projection": "<基于趋势的推演>",
      "timeframe": "<预计时间段>",
      "probability": "high|medium|low",
      "key_assumptions": ["<假设1>", "<假设2>"],
      "risk_factors": ["<可能偏离的因素>"]
    }
  ],""" if project_future else '  "future_projections": [],'

        system_msg = """你是时序分析专家，擅长从文本中重建时间脉络、检测趋势变化和进行基于证据的未来推演。
严格输出 JSON，不含任何额外文字。处理相对时间引用（"去年"、"三个月前"等）时，
若文本有绝对日期参考则计算实际日期，否则保留相对描述。"""

        user_content = f"""{context_line}

文本（前3500字）：
{text[:3500]}

请进行时序分析，输出完整 JSON：
{{
  "timeline": [
    {{
      "event_id": "E1",
      "timestamp": "<绝对日期 YYYY-MM 或相对时间 如'三年前'>",
      "timestamp_precision": "exact|approximate|relative",
      "event": "<事件描述≤60字>",
      "significance": "high|medium|low",
      "category": "milestone|trend_change|policy|market|financial|operational",
      "entities_involved": ["<相关实体>"],
      "source_quote": "<原文依据≤40字>"
    }}
  ],
  "trends": [
    {{
      "trend_name": "<趋势名称>",
      "direction": "ascending|descending|volatile|cyclical|stable",
      "start_period": "<趋势开始时间>",
      "inflection_points": [
        {{"time": "<时间点>", "description": "<拐点描述>", "trigger": "<触发因素>"}}
      ],
      "magnitude": "strong|moderate|weak",
      "supporting_events": ["E1", "E3"],
      "confidence": "high|medium|low"
    }}
  ],
  "cycles": [
    {{
      "cycle_name": "<周期名称>",
      "period": "<周期长度，如'季度'/'年度'/'3-5年'>",
      "current_phase": "<当前所处阶段>",
      "evidence": "<依据>"
    }}
  ],
  "temporal_gaps": [
    {{"period": "<缺少信息的时间段>", "significance": "<为何重要>"}}
  ],
  {future_section.strip()}
  "timeline_summary": "<3-4句话概括时间线的整体叙事和主要趋势>"
}}

注意：
1. timeline 按时间顺序排列（最早在前）
2. 只提取文本中有明确依据的事件，不臆造
3. 重要的时间节点（里程碑、转折点）的 significance 设为 high
4. trends 聚焦有意义的方向性变化，不重复列出单次事件"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)

        raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                         temperature=0.2, max_tokens=2000)

        # Parse
        analysis: dict = {"timeline": [], "trends": [], "cycles": [], "future_projections": []}
        try:
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.rsplit("```", 1)[0].strip()
            analysis = json.loads(clean)
        except Exception:
            analysis = {"raw": raw, "parse_error": True}

        # Narrative summary
        lines = []
        timeline = analysis.get("timeline", [])
        trends = analysis.get("trends", [])
        projections = analysis.get("future_projections", [])

        if timeline:
            high_sig = [e for e in timeline if e.get("significance") == "high"]
            lines.append(f"**时间线**：提取到 {len(timeline)} 个时间事件（其中重要节点 {len(high_sig)} 个）")
            for e in timeline[:3]:
                lines.append(f"  - {e.get('timestamp', '?')} | {e.get('event', '')}")

        if trends:
            lines.append(f"\n**趋势检测**：识别 {len(trends)} 条趋势走向")
            for t in trends[:3]:
                dir_icon = {"ascending": "📈", "descending": "📉", "volatile": "📊",
                            "cyclical": "🔄", "stable": "➡️"}.get(t.get("direction", ""), "")
                lines.append(f"  {dir_icon} {t.get('trend_name', '')}（{t.get('direction', '')}，强度：{t.get('magnitude', '')}）")

        if projections:
            lines.append(f"\n**未来推演**：{len(projections)} 个情景")
            for p in projections[:2]:
                lines.append(f"  - [{p.get('probability', '?').upper()}] {p.get('projection', '')}（{p.get('timeframe', '')}）")

        if analysis.get("timeline_summary"):
            lines.append(f"\n**时序摘要**：{analysis['timeline_summary']}")

        narrative = "\n".join(lines) if lines else raw

        return {
            "result":   narrative,
            "analysis": analysis,
            "topic":    topic,
            "event_count": len(timeline),
            "trend_count": len(trends),
        }
