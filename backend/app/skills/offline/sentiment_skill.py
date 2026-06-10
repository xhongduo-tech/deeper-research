"""Sentiment Analysis Skill — SOTA-enhanced multi-dimensional opinion mining.

Enhancements:
  - Chain-of-Thought reasoning before analysis
  - Structured JSON output with auto-repair
  - Self-critique: checks coverage, polarity calibration, entity accuracy
  - Adversarial review: detects sentiment bias, selective evidence, framing effects
  - Quality score (0-100) per analysis
  - Confidence calibration per entity and aspect
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class SentimentAnalysisSkill(Skill):
    name = "sentiment_analysis"
    category = "analysis"
    description = (
        "SOTA多维情感分析：文档级极性评分、实体级细粒度情感、方面级分析（财务/风险/产品/市场）、"
        "风险与机会信号提取（含严重程度分级）、情绪强度检测。"
        "含CoT推理、自评、红队挑战和质量评分，输出结构化 JSON 供仪表板消费"
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

    _ASPECTS = ["财务表现", "风险状况", "产品/服务", "市场地位", "管理层", "政策合规", "舆论形象"]
    _EMOTIONS = ["恐惧", "愤怒", "信任", "期待", "惊讶", "悲观", "乐观", "中性"]

    SENTIMENT_SCHEMA = {
        "document_sentiment": {
            "label": "positive|negative|neutral|mixed",
            "polarity": 0.0,
            "confidence": "high|medium|low",
            "summary": "",
            "reasoning": "",
        },
        "emotion_profile": {
            "primary_emotion": "",
            "emotions": [{"label": "", "intensity": 0.0}],
            "tone": "formal|informal|alarming|reassuring|neutral",
        },
        "entity_sentiments": [
            {
                "entity": "",
                "type": "organization|person|product|policy|market",
                "sentiment": "positive|negative|neutral|mixed",
                "polarity": 0.0,
                "confidence": 0.0,
                "aspects": [{"aspect": "", "sentiment": "", "evidence": ""}],
                "mentions": 0,
            }
        ],
        "risk_signals": [
            {
                "signal": "",
                "severity": "critical|high|medium|low",
                "category": "financial|operational|legal|reputational|market",
                "evidence": "",
                "confidence": 0.0,
            }
        ],
        "opportunity_signals": [
            {
                "signal": "",
                "potential": "high|medium|low",
                "category": "growth|efficiency|market|partnership|policy",
                "evidence": "",
                "confidence": 0.0,
            }
        ],
        "key_quotes": [
            {"text": "", "sentiment": "", "significance": ""}
        ],
        "overall_assessment": "",
        "analysis_quality": 8.0,
    }

    async def execute(self, text: str = "", entities: list = None,
                      domain: str = "general", output_format: str = "both",
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text            = params.get("text", text)
            entities        = params.get("entities", entities)
            domain          = params.get("domain", domain)
            output_format   = params.get("output_format", output_format)
            enable_critique = params.get("enable_critique", enable_critique)
            enable_adversarial = params.get("enable_adversarial", enable_adversarial)

        entities = entities or []
        entity_focus = (f"重点关注以下实体：{', '.join(entities[:8])}" if entities
                        else "自动识别文中所有重要实体")

        # ── Phase 1: CoT Reasoning ────────────────────────────────────────────
        cot_messages = [
            {
                "role": "system",
                "content": f"你是专业的舆情情感分析专家，具备金融文本分析和NLP专业背景。\n领域：{domain}。{entity_focus}\n\n分析前请先进行逐步思考。",
            },
            {
                "role": "user",
                "content": f"对以下文本进行情感分析前的思考。请回答：\n1. 文本的整体基调是什么？\n2. 涉及哪些关键实体？\n3. 有哪些潜在的偏见或情感诱导？\n4. 风险和机会的线索分别在哪里？\n\n文本（前2000字）：\n{text[:2000]}",
            },
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=800)

        # ── Phase 2: Structured JSON extraction ───────────────────────────────
        schema_desc = """输出严格JSON，包含：
- document_sentiment: 文档级情感（含reasoning字段）
- emotion_profile: 情绪画像
- entity_sentiments: 实体级情感（每条含confidence）
- risk_signals: 风险信号（每条含confidence）
- opportunity_signals: 机会信号（每条含confidence）
- key_quotes: 关键引用
- overall_assessment: 综合评估
- analysis_quality: 1-10分自评"""

        system_msg = f"""你是专业的舆情情感分析专家，具备金融文本分析和NLP专业背景。
领域：{domain}。{entity_focus}

思考过程（供参考，不输出）：
{reasoning[:500]}

输出要求：严格按照 JSON 格式输出，不要有任何额外文字。"""

        user_content = f"""对以下文本进行全维度情感分析，输出完整的 JSON 对象：

文本（前3000字）：
{text[:3000]}

{schema_desc}"""

        structured = await structured_generate(
            system=system_msg,
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.SENTIMENT_SCHEMA,
            temperature=0.15,
            max_tokens=2000,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}
        if not analysis:
            # Fallback to raw chat
            raw = await chat(
                [{"role": "system", "content": system_msg},
                 {"role": "user", "content": user_content}],
                model=model, base_url=base_url, api_key=api_key,
                temperature=0.15, max_tokens=1800,
            )
            analysis = {"raw": raw, "parse_error": True}

        # ── Phase 3: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and not analysis.get("parse_error"):
            critique = await self_critique(
                draft=json.dumps(analysis, ensure_ascii=False, indent=2)[:3000],
                topic=f"情感分析 - {domain}",
                dimensions=["data_grounding", "specificity", "logical_rigor"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 4: Adversarial review ───────────────────────────────────────
        if enable_adversarial and not analysis.get("parse_error"):
            adversarial = await adversarial_review(
                output=json.dumps(analysis, ensure_ascii=False, indent=2)[:3000],
                topic=f"情感分析 - {domain}",
            )

        # ── Phase 5: Build narrative output ───────────────────────────────────
        doc_s = analysis.get("document_sentiment", {})
        narrative_lines = [
            f"**整体情感**：{doc_s.get('label', 'neutral')}（极性 {doc_s.get('polarity', 0):+.2f}，"
            f"置信度：{doc_s.get('confidence', 'medium')}）",
            f"**摘要评价**：{doc_s.get('summary', '')}",
        ]
        if doc_s.get("reasoning"):
            narrative_lines.append(f"**推理过程**：{doc_s['reasoning']}")

        emo = analysis.get("emotion_profile", {})
        if emo.get("primary_emotion"):
            narrative_lines.append(f"**主要情绪**：{emo['primary_emotion']}（语气：{emo.get('tone', '')}）")

        entities_out = analysis.get("entity_sentiments", [])
        if entities_out:
            narrative_lines.append("**实体情感**：")
            for e in entities_out[:5]:
                narrative_lines.append(
                    f"  - {e['entity']}：{e.get('sentiment', 'neutral')}"
                    f"（极性 {e.get('polarity', 0):+.2f}，置信度 {e.get('confidence', 'N/A')}）"
                )

        risks = analysis.get("risk_signals", [])
        if risks:
            narrative_lines.append("**风险信号**：")
            for r in risks[:4]:
                sev = r.get("severity", "medium")
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(sev, "⚪")
                narrative_lines.append(f"  {sev_icon} [{sev.upper()}] {r['signal']} [置信度: {r.get('confidence', 'N/A')}]")

        opps = analysis.get("opportunity_signals", [])
        if opps:
            narrative_lines.append("**机会信号**：")
            for o in opps[:3]:
                narrative_lines.append(f"  ✅ {o['signal']} [置信度: {o.get('confidence', 'N/A')}]")

        if analysis.get("overall_assessment"):
            narrative_lines.append(f"\n**综合评估**：{analysis['overall_assessment']}")

        narrative = "\n".join(narrative_lines)

        result = {
            "result": narrative,
            "analysis": analysis,
            "reasoning": reasoning,
        }
        if quality_score is not None:
            result["quality_score"] = quality_score
        if critique:
            result["critique"] = critique
        if adversarial:
            result["adversarial"] = adversarial

        if output_format == "structured":
            return result
        if output_format == "narrative":
            return {"result": narrative, "analysis": {}}
        return result
