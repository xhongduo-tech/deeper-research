"""
Argument Mining Skill — structured argument extraction and evaluation.

Argument Mining identifies the logical scaffolding of a document:
  - Claims (主张): what the author asserts
  - Premises / Evidence (前提/证据): what supports the claim
  - Warrants (推理规则): the implicit logic connecting evidence to claim
  - Rebuttals (反驳): counter-arguments acknowledged or dismissed
  - Conclusions (结论): final supported judgments

Why it matters for enterprise research:
  - Evaluate the logical strength of reports and proposals
  - Detect unsupported assertions ("claim without evidence")
  - Map competing viewpoints on the same topic
  - Identify logical fallacies that undermine reliability

Reference: Toulmin Argument Model (1958) adapted for NLP.
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router


class ArgumentMiningSkill(Skill):
    name = "argument_mining"
    category = "analysis"
    description = (
        "论证挖掘：从文本中提取结构化论证链（主张→证据→推理→结论），"
        "识别无支撑断言、逻辑谬误和竞争性观点，评估整体论证强度"
    )
    parameters = {
        "text":    {"type": "string", "description": "待分析文本"},
        "topic":   {"type": "string", "description": "分析聚焦点（可选）", "default": ""},
        "mode":    {
            "type": "string",
            "description": "分析模式: full|claims_only|strength_eval|fallacy_check",
            "default": "full",
        },
    }

    _FALLACY_TYPES = [
        "诉诸权威（无证据）", "滑坡谬误", "稻草人谬误", "错误归因",
        "过度概括", "黑白思维", "循环论证", "诉诸情感", "幸存者偏差",
    ]

    async def execute(self, text: str = "", topic: str = "",
                      mode: str = "full", **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text  = params.get("text", text)
            topic = params.get("topic", topic)
            mode  = params.get("mode", mode)

        topic_line = f"分析焦点：{topic}" if topic else "自动识别文本中的核心论证"
        fallacy_list = "、".join(self._FALLACY_TYPES)

        system_msg = """你是逻辑学和论证分析专家，熟悉图尔明论证模型（Toulmin Model）和批判性思维方法。
你的任务是严格按照要求分析文本的论证结构，输出结构化 JSON。"""

        sections_for_mode = {
            "claims_only": ["claims"],
            "strength_eval": ["claims", "strength_assessment"],
            "fallacy_check": ["claims", "fallacies", "unsupported"],
            "full": ["claims", "argument_map", "fallacies", "unsupported", "competing_views", "strength_assessment"],
        }
        active_sections = sections_for_mode.get(mode, sections_for_mode["full"])

        json_schema_parts = {}

        if "claims" in active_sections:
            json_schema_parts["main_claims"] = [
                {
                    "claim_id": "C1",
                    "claim": "<主张陈述>",
                    "claim_type": "factual|evaluative|policy|causal|predictive",
                    "evidence": [
                        {"type": "data|expert|example|analogy|logic", "content": "<证据内容≤50字>", "strength": "strong|moderate|weak"}
                    ],
                    "warrant": "<隐含的推理规则，即为何该证据支持该主张>",
                    "rebuttal": "<文中承认的反驳（如有）>",
                    "conclusion_supported": True,
                }
            ]

        if "argument_map" in active_sections:
            json_schema_parts["argument_map"] = {
                "central_claim": "<核心主张一句话>",
                "support_chains": ["<支撑链条1: 前提A + 前提B → 主张C>"],
                "attack_chains": ["<攻击链条: 反驳X → 削弱主张Y>"],
            }

        if "fallacies" in active_sections:
            json_schema_parts["fallacies"] = [
                {
                    "fallacy_type": f"<{fallacy_list[:60]}/其他>",
                    "location": "<涉及的文本片段≤40字>",
                    "explanation": "<为何构成谬误>",
                    "severity": "critical|moderate|minor",
                }
            ]

        if "unsupported" in active_sections:
            json_schema_parts["unsupported_claims"] = [
                {"claim": "<无支撑断言>", "why_unsupported": "<缺少什么类型的证据>"}
            ]

        if "competing_views" in active_sections:
            json_schema_parts["competing_views"] = [
                {"viewpoint": "<竞争性观点>", "how_addressed": "acknowledged|dismissed|ignored|refuted", "adequacy": "adequate|inadequate"}
            ]

        if "strength_assessment" in active_sections:
            json_schema_parts["strength_assessment"] = {
                "overall_score": "<1-10，整体论证强度>",
                "logical_consistency": "high|medium|low",
                "evidence_quality": "high|medium|low",
                "completeness": "high|medium|low",
                "key_weaknesses": ["<主要弱点1>", "<主要弱点2>"],
                "verdict": "<2-3句综合判断：该文本的论证质量如何，可信度如何>",
            }

        user_content = f"""{topic_line}

待分析文本（前3000字）：
{text[:3000]}

请进行论证挖掘分析，输出以下 JSON（仅输出 JSON，不含其他文字）：
{json.dumps(json_schema_parts, ensure_ascii=False, indent=2)}"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)

        raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                         temperature=0.15, max_tokens=2000)

        # Parse JSON
        analysis: dict = {}
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

        # Build narrative summary
        lines = []
        claims = analysis.get("main_claims", [])
        if claims:
            lines.append(f"**识别到 {len(claims)} 条核心主张**")
            for c in claims[:3]:
                ev_count = len(c.get("evidence", []))
                lines.append(f"  - {c.get('claim', '')} （支撑证据：{ev_count}条）")

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

        narrative = "\n".join(lines) if lines else raw

        return {
            "result":   narrative,
            "analysis": analysis,
            "topic":    topic,
            "mode":     mode,
        }
