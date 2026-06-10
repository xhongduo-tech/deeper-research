"""Temporal Analysis Skill — SOTA-enhanced timeline extraction and trend reasoning.

Enhancements:
  - Chain-of-Thought: reason about temporal patterns before extraction
  - Self-critique: checks event ordering accuracy, trend validity
  - Adversarial review: challenges trend extrapolation, identifies hindsight bias
  - Quality score (0-100) per analysis
  - Structured JSON output with auto-repair
  - Confidence scoring per event and trend

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
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class TemporalAnalysisSkill(Skill):
    name = "temporal_analysis"
    category = "analysis"
    description = (
        "SOTA时序分析：从文本中重建事件时间线、检测趋势拐点、识别周期性规律、"
        "进行基于趋势的未来推演。含CoT推理、自评、红队挑战和质量评分，输出结构化时间线"
    )
    parameters = {
        "text":        {"type": "string", "description": "待分析文本"},
        "topic":       {"type": "string", "description": "分析主题（可选）", "default": ""},
        "time_range":  {"type": "string", "description": "关注的时间范围（如 2020-2025）", "default": ""},
        "project_future": {"type": "boolean", "description": "是否生成未来推演", "default": True},
        "enable_critique": {
            "type": "boolean",
            "description": "启用质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队挑战",
            "default": True,
        },
    }

    TEMPORAL_SCHEMA = {
        "timeline": [
            {
                "event_id": "E1",
                "timestamp": "",
                "timestamp_precision": "exact|approximate|relative",
                "event": "",
                "significance": "high|medium|low",
                "category": "milestone|trend_change|policy|market|financial|operational",
                "entities_involved": [""],
                "source_quote": "",
                "confidence": 0.9,
            }
        ],
        "trends": [
            {
                "trend_name": "",
                "direction": "ascending|descending|volatile|cyclical|stable",
                "start_period": "",
                "inflection_points": [
                    {"time": "", "description": "", "trigger": ""}
                ],
                "magnitude": "strong|moderate|weak",
                "supporting_events": ["E1", "E3"],
                "confidence": "high|medium|low",
            }
        ],
        "cycles": [
            {
                "cycle_name": "",
                "period": "",
                "current_phase": "",
                "evidence": "",
                "confidence": 0.8,
            }
        ],
        "temporal_gaps": [
            {"period": "", "significance": ""}
        ],
        "future_projections": [
            {
                "projection": "",
                "timeframe": "",
                "probability": "high|medium|low",
                "key_assumptions": [""],
                "risk_factors": [""],
                "confidence": 0.7,
            }
        ],
        "timeline_summary": "",
        "analysis_quality": 8.0,
    }

    async def execute(self, text: str = "", topic: str = "",
                      time_range: str = "", project_future: bool = True,
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text           = params.get("text", text)
            topic          = params.get("topic", topic)
            time_range     = params.get("time_range", time_range)
            project_future = params.get("project_future", project_future)
            enable_critique = params.get("enable_critique", enable_critique)
            enable_adversarial = params.get("enable_adversarial", enable_adversarial)

        context_parts = []
        if topic:
            context_parts.append(f"分析主题：{topic}")
        if time_range:
            context_parts.append(f"关注时间范围：{time_range}")
        context_line = "；".join(context_parts) if context_parts else "自动识别文中所有时间信息"

        # ── Phase 1: CoT Reasoning ────────────────────────────────────────────
        system_msg = """你是时序分析专家，擅长从文本中重建时间脉络、检测趋势变化和进行基于证据的未来推演。
处理相对时间引用（"去年"、"三个月前"等）时，若文本有绝对日期参考则计算实际日期，否则保留相对描述。"""

        cot_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"""{context_line}

在进行正式时序分析前，请先逐步思考：
1. 文本中涉及哪些关键时间节点？
2. 这些事件之间的因果关系和时序关系是什么？
3. 有哪些趋势方向性变化？
4. 是否存在周期性规律？
5. 有哪些时间信息缺失（temporal gaps）？

文本（前2000字）：
{text[:2000]}

请输出你的思考过程。"""},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=1000)

        # ── Phase 2: Structured extraction ────────────────────────────────────
        future_section = (
            '  "future_projections": 含 projection/timeframe/probability/key_assumptions/risk_factors/confidence 的数组，'
            if project_future else '  "future_projections": []（空数组），'
        )

        schema_desc = f"""输出严格JSON，包含：
- timeline: 事件时间线（按时间顺序，每条含event_id, timestamp, timestamp_precision, event, significance, category, entities_involved, source_quote, confidence）
- trends: 趋势（每条含direction, start_period, inflection_points, magnitude, supporting_events, confidence）
- cycles: 周期（每条含cycle_name, period, current_phase, evidence, confidence）
- temporal_gaps: 时间缺口
- {future_section}
- timeline_summary: 时序摘要
- analysis_quality: 1-10分自评

注意：
1. timeline 按时间顺序排列（最早在前）
2. 只提取文本中有明确依据的事件，不臆造
3. 重要的时间节点 significance 设为 high
4. 每个事件和趋势都标注置信度"""

        user_content = f"""{reasoning[:400]}

{context_line}

文本（前3500字）：
{text[:3500]}

请进行时序分析，输出完整 JSON：
{schema_desc}"""

        structured = await structured_generate(
            system=system_msg,
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.TEMPORAL_SCHEMA,
            temperature=0.2,
            max_tokens=2500,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}

        # ── Phase 3: Build narrative ──────────────────────────────────────────
        lines = []
        timeline = analysis.get("timeline", [])
        trends = analysis.get("trends", [])
        projections = analysis.get("future_projections", [])

        if timeline:
            high_sig = [e for e in timeline if e.get("significance") == "high"]
            lines.append(f"**时间线**：提取到 {len(timeline)} 个时间事件（其中重要节点 {len(high_sig)} 个）")
            for e in timeline[:3]:
                lines.append(f"  - {e.get('timestamp', '?')} | {e.get('event', '')} [置信度: {e.get('confidence', 'N/A')}]")

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

        gaps = analysis.get("temporal_gaps", [])
        if gaps:
            lines.append(f"\n**时间缺口**：{len(gaps)} 处")
            for g in gaps[:2]:
                lines.append(f"  - {g.get('period', '')}：{g.get('significance', '')}")

        if analysis.get("timeline_summary"):
            lines.append(f"\n**时序摘要**：{analysis['timeline_summary']}")

        narrative = "\n".join(lines) if lines else reasoning

        # ── Phase 4: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and analysis:
            critique = await self_critique(
                draft=narrative[:3000],
                topic=f"{topic or '时序分析'}",
                dimensions=["data_grounding", "logical_rigor", "specificity"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 5: Adversarial review ───────────────────────────────────────
        if enable_adversarial and analysis:
            adversarial = await adversarial_review(
                output=narrative[:3000],
                topic=f"{topic or '时序分析'}",
            )

        result = {
            "result": narrative,
            "analysis": analysis,
            "topic": topic,
            "event_count": len(timeline),
            "trend_count": len(trends),
            "reasoning": reasoning,
        }
        if quality_score is not None:
            result["quality_score"] = quality_score
        if critique:
            result["critique"] = critique
        if adversarial:
            result["adversarial"] = adversarial

        return result
