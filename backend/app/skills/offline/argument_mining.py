"""Argument Mining Skill — SOTA-enhanced structured argument extraction and evaluation.

Enhancements:
  - Chain-of-Thought: map argument structure before extraction
  - Self-critique: checks logical completeness, evidence quality, fallacy coverage
  - Adversarial review: challenges argument strength, spots unsupported leaps
  - Quality score (0-100) per analysis
  - Structured JSON output with auto-repair
  - Confidence scoring per claim and evidence link

Reference: Toulmin Argument Model (1958) adapted for NLP.
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class ArgumentMiningSkill(Skill):
    name = "argument_mining"
    category = "analysis"
    description = (
        "SOTA论证挖掘：从文本中提取结构化论证链（主张→证据→推理→结论），"
        "识别无支撑断言、逻辑谬误和竞争性观点，评估整体论证强度。"
        "含CoT推理、自评、红队挑战和质量评分"
    )
    parameters = {
        "text":    {"type": "string", "description": "待分析文本"},
        "topic":   {"type": "string", "description": "分析聚焦点（可选）", "default": ""},
        "mode":    {
            "type": "string",
            "description": "分析模式: full|claims_only|strength_eval|fallacy_check",
            "default": "full",
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

    _FALLACY_TYPES = [
        "诉诸权威（无证据）", "滑坡谬误", "稻草人谬误", "错误归因",
        "过度概括", "黑白思维", "循环论证", "诉诸情感", "幸存者偏差",
    ]

    ARGUMENT_SCHEMA = {
        "main_claims": [
            {
                "claim_id": "C1",
                "claim": "",
                "claim_type": "factual|evaluative|policy|causal|predictive",
                "evidence": [
                    {"type": "data|expert|example|analogy|logic", "content": "", "strength": "strong|moderate|weak", "confidence": 0.9}
                ],
                "warrant": "",
                "rebuttal": "",
                "conclusion_supported": True,
                "confidence": 0.85,
            }
        ],
        "argument_map": {
            "central_claim": "",
            "support_chains": [""],
            "attack_chains": [""],
        },
        "fallacies": [
            {
                "fallacy_type": "",
                "location": "",
                "explanation": "",
                "severity": "critical|moderate|minor",
                "confidence": 0.8,
            }
        ],
        "unsupported_claims": [
            {"claim": "", "why_unsupported": "", "severity": "critical|moderate|minor"}
        ],
        "competing_views": [
            {"viewpoint": "", "how_addressed": "acknowledged|dismissed|ignored|refuted", "adequacy": "adequate|inadequate", "confidence": 0.8}
        ],
        "strength_assessment": {
            "overall_score": 7.0,
            "logical_consistency": "high|medium|low",
            "evidence_quality": "high|medium|low",
            "completeness": "high|medium|low",
            "key_weaknesses": [""],
            "verdict": "",
        },
        "analysis_quality": 8.0,
    }

    async def execute(self, text: str = "", topic: str = "",
                      mode: str = "full",
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text  = params.get("text", text)
            topic = params.get("topic", topic)
            mode  = params.get("mode", mode)
            enable_critique = params.get("enable_critique", enable_critique)
            enable_adversarial = params.get("enable_adversarial", enable_adversarial)

        topic_line = f"分析焦点：{topic}" if topic else "自动识别文本中的核心论证"
        fallacy_list = "、".join(self._FALLACY_TYPES)

        # ── Phase 1: CoT — map argument structure ─────────────────────────────
        system_msg = "你是逻辑学和论证分析专家，熟悉图尔明论证模型（Toulmin Model）和批判性思维方法。"
        cot_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"""{topic_line}

在进行正式论证挖掘前，请先逐步思考：
1. 文本的核心主张是什么？
2. 有哪些证据支撑这些主张？证据的质量如何？
3. 推理过程（warrant）是否充分？
4. 有哪些潜在的逻辑谬误？
5. 文本是否回应了竞争性观点？

文本（前2000字）：
{text[:2000]}

请输出你的思考过程。"""},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=1000)

        # ── Phase 2: Structured extraction ────────────────────────────────────
        sections_for_mode = {
            "claims_only": ["main_claims"],
            "strength_eval": ["main_claims", "strength_assessment"],
            "fallacy_check": ["main_claims", "fallacies", "unsupported_claims"],
            "full": ["main_claims", "argument_map", "fallacies", "unsupported_claims", "competing_views", "strength_assessment"],
        }
        active_keys = sections_for_mode.get(mode, sections_for_mode["full"])

        schema_desc = f"""输出严格JSON，包含：
- main_claims: 核心主张（每条含evidence列表，每条evidence含confidence）
- argument_map: 论证图谱（central_claim, support_chains, attack_chains）
- fallacies: 逻辑谬误（含confidence）
- unsupported_claims: 无支撑断言
- competing_views: 竞争性观点（含confidence）
- strength_assessment: 论证强度评估（overall_score 1-10）
- analysis_quality: 1-10分自评

当前模式：{mode}，只输出以下字段：{', '.join(active_keys)}"""

        user_content = f"""{reasoning[:400]}

{topic_line}

待分析文本（前3000字）：
{text[:3000]}

请进行论证挖掘分析，输出以下 JSON：
{schema_desc}

注意：
- 每个主张和证据都标注置信度(0-1)
- 谬误类型从以下选择：{fallacy_list}
- overall_score 为 1-10 的整数或一位小数"""

        structured = await structured_generate(
            system=system_msg + " 输出结构化 JSON，不要任何额外文字。",
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.ARGUMENT_SCHEMA,
            temperature=0.15,
            max_tokens=2500,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}

        # ── Phase 3: Build narrative ──────────────────────────────────────────
        lines = []
        claims = analysis.get("main_claims", [])
        if claims:
            lines.append(f"**识别到 {len(claims)} 条核心主张**")
            for c in claims[:3]:
                ev_count = len(c.get("evidence", []))
                conf = c.get("confidence", "N/A")
                lines.append(f"  - {c.get('claim', '')} （支撑证据：{ev_count}条，置信度：{conf}）")

        fallacies = analysis.get("fallacies", [])
        if fallacies:
            critical = [f for f in fallacies if f.get("severity") == "critical"]
            lines.append(f"\n**⚠️ 发现 {len(fallacies)} 处逻辑问题**（其中严重：{len(critical)} 处）")

        unsupported = analysis.get("unsupported_claims", [])
        if unsupported:
            lines.append(f"**无支撑断言：{len(unsupported)} 条**（建议补充证据）")

        strength = analysis.get("strength_assessment", {})
        if strength:
            score = strength.get("overall_score", "N/A")
            lines.append(f"\n**论证强度综合评分：{score}/10**")
            if strength.get("verdict"):
                lines.append(f"**评估结论**：{strength['verdict']}")

        narrative = "\n".join(lines) if lines else reasoning

        # ── Phase 4: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and analysis:
            critique = await self_critique(
                draft=narrative[:3000],
                topic=f"{topic or '论证挖掘'}",
                dimensions=["logical_rigor", "specificity", "insight_depth"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 5: Adversarial review ───────────────────────────────────────
        if enable_adversarial and analysis:
            adversarial = await adversarial_review(
                output=narrative[:3000],
                topic=f"{topic or '论证挖掘'}",
            )

        result = {
            "result": narrative,
            "analysis": analysis,
            "topic": topic,
            "mode": mode,
            "reasoning": reasoning,
        }
        if quality_score is not None:
            result["quality_score"] = quality_score
        if critique:
            result["critique"] = critique
        if adversarial:
            result["adversarial"] = adversarial

        return result
