"""
Sentiment Analysis Skill — multi-dimensional opinion mining.

Features:
  - Document-level polarity scoring (-1 to +1)
  - Entity-level fine-grained sentiment (per mentioned organization/person/product)
  - Aspect-based sentiment (financial / risk / product / market / management / policy)
  - Risk & opportunity signal extraction with severity levels
  - Emotion intensity detection (fear, anger, trust, anticipation, surprise)
  - Multi-document trend support (call with multiple texts for trend analysis)
  - Structured JSON output for dashboard consumption
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router


class SentimentAnalysisSkill(Skill):
    name = "sentiment_analysis"
    category = "analysis"
    description = (
        "多维情感分析：文档级极性评分、实体级细粒度情感、方面级分析（财务/风险/产品/市场）、"
        "风险与机会信号提取（含严重程度分级）、情绪强度检测，输出结构化 JSON 供仪表板消费"
    )
    parameters = {
        "text":     {"type": "string", "description": "待分析文本（单篇或多篇合并）"},
        "entities": {"type": "array",  "description": "重点关注的实体列表", "default": []},
        "domain":   {"type": "string", "description": "业务领域", "default": "general"},
        "output_format": {
            "type": "string",
            "description": "输出格式: narrative（叙述报告）| structured（结构化JSON）| both",
            "default": "both",
        },
    }

    _ASPECTS = ["财务表现", "风险状况", "产品/服务", "市场地位", "管理层", "政策合规", "舆论形象"]
    _EMOTIONS = ["恐惧", "愤怒", "信任", "期待", "惊讶", "悲观", "乐观", "中性"]

    async def execute(self, text: str = "", entities: list = None,
                      domain: str = "general", output_format: str = "both", **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text          = params.get("text", text)
            entities      = params.get("entities", entities)
            domain        = params.get("domain", domain)
            output_format = params.get("output_format", output_format)

        entities = entities or []
        entity_focus = (f"重点关注以下实体：{', '.join(entities[:8])}" if entities
                        else "自动识别文中所有重要实体")

        system_msg = f"""你是专业的舆情情感分析专家，具备金融文本分析和NLP专业背景。
领域：{domain}。{entity_focus}

输出要求：严格按照 JSON 格式输出，不要有任何额外文字。"""

        user_content = f"""对以下文本进行全维度情感分析，输出完整的 JSON 对象：

文本（前3000字）：
{text[:3000]}

请输出以下 JSON 结构：
{{
  "document_sentiment": {{
    "label": "positive|negative|neutral|mixed",
    "polarity": <-1.0到1.0的浮点数>,
    "confidence": "high|medium|low",
    "summary": "<一句话整体评价>"
  }},
  "emotion_profile": {{
    "primary_emotion": "<{'/'.join(self._EMOTIONS)}>",
    "emotions": [{{"label": "<情绪名>", "intensity": <0-1浮点数>}}],
    "tone": "formal|informal|alarming|reassuring|neutral"
  }},
  "entity_sentiments": [
    {{
      "entity": "<实体名称>",
      "type": "organization|person|product|policy|market",
      "sentiment": "positive|negative|neutral|mixed",
      "polarity": <-1.0到1.0>,
      "aspects": [{{"aspect": "<{'/'.join(self._ASPECTS[:3])}/...>", "sentiment": "positive|negative|neutral", "evidence": "<引用原文片段，≤30字>"}}],
      "mentions": <整数，提及次数>
    }}
  ],
  "risk_signals": [
    {{
      "signal": "<风险描述>",
      "severity": "critical|high|medium|low",
      "category": "financial|operational|legal|reputational|market",
      "evidence": "<原文依据，≤50字>"
    }}
  ],
  "opportunity_signals": [
    {{
      "signal": "<机会描述>",
      "potential": "high|medium|low",
      "category": "growth|efficiency|market|partnership|policy",
      "evidence": "<原文依据，≤50字>"
    }}
  ],
  "key_quotes": [
    {{"text": "<原文引用≤60字>", "sentiment": "positive|negative|neutral", "significance": "<为何重要，≤20字>"}}
  ],
  "overall_assessment": "<2-3句综合评估，含主要结论>"
}}"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)

        raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                         temperature=0.15, max_tokens=1800)

        # Parse JSON result
        analysis: dict = {}
        try:
            # Strip markdown code fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```", 2)[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.rsplit("```", 1)[0].strip()
            analysis = json.loads(clean)
        except Exception:
            # Fallback: return raw text
            analysis = {"raw": raw, "parse_error": True}

        # Build narrative output
        doc_s = analysis.get("document_sentiment", {})
        narrative_lines = [
            f"**整体情感**：{doc_s.get('label', 'neutral')}（极性 {doc_s.get('polarity', 0):+.2f}，"
            f"置信度：{doc_s.get('confidence', 'medium')}）",
            f"**摘要评价**：{doc_s.get('summary', '')}",
        ]

        emo = analysis.get("emotion_profile", {})
        if emo.get("primary_emotion"):
            narrative_lines.append(f"**主要情绪**：{emo['primary_emotion']}（语气：{emo.get('tone', '')}）")

        entities_out = analysis.get("entity_sentiments", [])
        if entities_out:
            narrative_lines.append("**实体情感**：")
            for e in entities_out[:5]:
                narrative_lines.append(
                    f"  - {e['entity']}：{e.get('sentiment', 'neutral')}（极性 {e.get('polarity', 0):+.2f}）"
                )

        risks = analysis.get("risk_signals", [])
        if risks:
            narrative_lines.append("**风险信号**：")
            for r in risks[:4]:
                sev = r.get("severity", "medium")
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                narrative_lines.append(f"  {sev_icon} [{sev.upper()}] {r['signal']}")

        opps = analysis.get("opportunity_signals", [])
        if opps:
            narrative_lines.append("**机会信号**：")
            for o in opps[:3]:
                narrative_lines.append(f"  ✅ {o['signal']}")

        if analysis.get("overall_assessment"):
            narrative_lines.append(f"\n**综合评估**：{analysis['overall_assessment']}")

        narrative = "\n".join(narrative_lines)

        if output_format == "structured":
            return {"result": narrative, "analysis": analysis}
        if output_format == "narrative":
            return {"result": narrative, "analysis": {}}
        return {"result": narrative, "analysis": analysis}
