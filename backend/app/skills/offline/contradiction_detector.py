"""Contradiction Detector — SOTA-enhanced cross-claim consistency analysis.

Enhancements:
  - Chain-of-Thought: reason about consistency before detection
  - Self-critique: checks for false positives, ensures genuine contradictions
  - Adversarial review: challenges contradiction severity, offers alternative interpretations
  - Quality score (0-100) per analysis
  - Structured JSON output with auto-repair
  - Confidence scoring per contradiction

Detects and classifies contradictions between claims, either within a single
document or across multiple documents. Critical for:
  - Research report quality control (internal consistency)
  - Due diligence (comparing company statements vs. analyst reports)
  - Policy analysis (what was said vs. what was done)
  - Multi-source intelligence synthesis (conflicting intelligence)

Contradiction types handled:
  - Factual contradictions (different numbers for the same metric)
  - Temporal contradictions (event order inconsistency)
  - Causal contradictions (A causes B vs. B causes A)
  - Normative contradictions (policy X endorsed vs. condemned)
  - Statistical contradictions (% share adds up to > 100%)
  - Attribution contradictions (who said/did what)
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class ContradictionDetectorSkill(Skill):
    name = "contradiction_detection"
    category = "analysis"
    description = (
        "SOTA跨文档矛盾检测：识别单篇或多篇文本中的事实矛盾、数据冲突、逻辑不一致和观点对立，"
        "输出矛盾清单、严重程度分级、可信度加权建议。含CoT推理、自评、红队挑战和质量评分"
    )
    parameters = {
        "text":         {"type": "string",  "description": "主要文本（单篇分析内部矛盾）"},
        "reference_text": {
            "type": "string",
            "description": "参考文本（与主文本进行跨文档对比，可选）",
            "default": "",
        },
        "topic":        {"type": "string",  "description": "分析主题（可选）", "default": ""},
        "focus":        {
            "type": "string",
            "description": "重点检查类型: all|factual|temporal|causal|statistical",
            "default": "all",
        },
        "resolve_contradictions": {
            "type": "boolean",
            "description": "是否尝试解释/调和矛盾（提供解释假设）",
            "default": True,
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

    _CONTRADICTION_TYPES = {
        "factual":    "事实矛盾（对同一事实有不同陈述）",
        "temporal":   "时序矛盾（事件顺序不一致）",
        "causal":     "因果矛盾（因果方向相反）",
        "normative":  "价值矛盾（同一事物既被肯定又被否定）",
        "statistical":"数据矛盾（统计数字相互矛盾）",
        "attribution":"归因矛盾（行为/言论的归属不一致）",
    }

    CONTRADICTION_SCHEMA = {
        "contradictions": [
            {
                "contradiction_id": "CON1",
                "type": "",
                "severity": "critical|major|minor",
                "claim_a": {
                    "text": "",
                    "source": "doc_a|doc_b|internal",
                    "location_hint": "",
                },
                "claim_b": {
                    "text": "",
                    "source": "doc_a|doc_b|internal",
                    "location_hint": "",
                },
                "contradiction_nature": "",
                "confidence": 0.85,
                "resolution_hypothesis": "",
                "recommended_action": "verify|prioritize_source_a|prioritize_source_b|flag_for_review",
            }
        ],
        "consistency_score": 80,
        "critical_issues": [""],
        "internal_consistency": {
            "is_consistent": True,
            "issues_count": {"critical": 0, "major": 0, "minor": 0},
        },
        "credibility_assessment": {
            "overall": "high|medium|low",
            "reasoning": "",
            "most_reliable_claims": [""],
            "least_reliable_claims": [""],
        },
        "summary": "",
        "analysis_quality": 8.0,
    }

    async def execute(self, text: str = "", reference_text: str = "",
                      topic: str = "", focus: str = "all",
                      resolve_contradictions: bool = True,
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text                   = params.get("text", text)
            reference_text         = params.get("reference_text", reference_text)
            topic                  = params.get("topic", topic)
            focus                  = params.get("focus", focus)
            resolve_contradictions = params.get("resolve_contradictions", resolve_contradictions)
            enable_critique        = params.get("enable_critique", enable_critique)
            enable_adversarial     = params.get("enable_adversarial", enable_adversarial)

        is_cross_doc = bool(reference_text and reference_text.strip())
        mode_desc = "跨文档矛盾分析" if is_cross_doc else "文档内部一致性分析"

        focus_types = (
            list(self._CONTRADICTION_TYPES.keys())
            if focus == "all"
            else [focus] if focus in self._CONTRADICTION_TYPES else list(self._CONTRADICTION_TYPES.keys())
        )
        focus_desc = "；".join(self._CONTRADICTION_TYPES[k] for k in focus_types)

        # ── Phase 1: CoT Reasoning ────────────────────────────────────────────
        system_msg = f"""你是批判性分析专家，专门识别文本中的逻辑矛盾和事实冲突。
任务：{mode_desc}。重点检测：{focus_desc}。"""

        cot_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"""分析主题：{topic or '自动识别'}

在进行矛盾检测前，请先逐步思考：
1. 文本的核心主张有哪些？
2. 这些主张之间是否存在逻辑冲突？
3. 数据/事实陈述是否一致？
4. 是否存在由于定义不同或时间差异导致的"伪矛盾"？

主文本（前2000字）：
{text[:2000]}
{chr(10) + f"参考文本（前1500字）：{chr(10)}{reference_text[:1500]}" if is_cross_doc else ""}

请输出你的思考过程。"""},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=1000)

        # ── Phase 2: Structured extraction ────────────────────────────────────
        resolve_fields = (
            '  "resolution_hypothesis": "<如何解释此矛盾的可能假设>",\n  "recommended_action": "verify|prioritize_source_a|prioritize_source_b|flag_for_review",\n'
            if resolve_contradictions else ""
        )

        schema_desc = f"""输出严格JSON，包含：
- contradictions: 矛盾列表（每条含contradiction_id, type, severity, claim_a, claim_b, contradiction_nature, confidence, {resolve_fields.strip() if resolve_fields else ''}）
- consistency_score: 0-100整体一致性得分
- critical_issues: 需要立即核实的关键矛盾
- internal_consistency: 含is_consistent和issues_count
- credibility_assessment: 可信度评估（含overall, reasoning, most_reliable_claims, least_reliable_claims）
- summary: 2-3句综合评价
- analysis_quality: 1-10分自评

注意：
1. 只标记真正的矛盾，不将不同角度的补充性陈述视为矛盾
2. critical = 影响核心结论；major = 影响分支论点；minor = 细节差异
3. confidence 表示判断该处为矛盾的把握程度"""

        text_block = f"**主文本（前2500字）：**\n{text[:2500]}"
        if is_cross_doc:
            text_block += f"\n\n**参考文本（前2000字）：**\n{reference_text[:2000]}"

        user_content = f"""{reasoning[:400]}

分析主题：{topic or '自动识别'}

{text_block}

请进行矛盾检测，输出完整 JSON：
{schema_desc}"""

        structured = await structured_generate(
            system=system_msg + " 严格输出 JSON，不含额外文字。",
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.CONTRADICTION_SCHEMA,
            temperature=0.15,
            max_tokens=2500,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}

        # ── Phase 3: Build narrative ──────────────────────────────────────────
        lines = []
        contradictions = analysis.get("contradictions", [])
        score = analysis.get("consistency_score", "N/A")

        by_severity: dict = {"critical": [], "major": [], "minor": []}
        for c in contradictions:
            by_severity.get(c.get("severity", "minor"), by_severity["minor"]).append(c)

        lines.append(f"**一致性评分：{score}/100**（发现 {len(contradictions)} 处矛盾）")
        if by_severity["critical"]:
            lines.append(f"🔴 **严重矛盾（{len(by_severity['critical'])}处）**：")
            for c in by_severity["critical"][:2]:
                lines.append(f"  - {c.get('contradiction_nature', '')} [置信度: {c.get('confidence', 'N/A')}]")
        if by_severity["major"]:
            lines.append(f"🟠 **重要矛盾（{len(by_severity['major'])}处）**")
        if by_severity["minor"]:
            lines.append(f"🟡 **次要矛盾（{len(by_severity['minor'])}处）**")

        cred = analysis.get("credibility_assessment", {})
        if cred:
            lines.append(f"\n**可信度评级：{cred.get('overall', '').upper()}**")
            if cred.get("reasoning"):
                lines.append(f"{cred['reasoning']}")

        if analysis.get("summary"):
            lines.append(f"\n**综合评价**：{analysis['summary']}")

        narrative = "\n".join(lines) if lines else reasoning

        # ── Phase 4: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and analysis:
            critique = await self_critique(
                draft=narrative[:3000],
                topic=f"{topic or '矛盾检测'}",
                dimensions=["logical_rigor", "specificity", "data_grounding"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 5: Adversarial review ───────────────────────────────────────
        if enable_adversarial and analysis:
            adversarial = await adversarial_review(
                output=narrative[:3000],
                topic=f"{topic or '矛盾检测'}",
            )

        result = {
            "result": narrative,
            "analysis": analysis,
            "contradiction_count": len(contradictions),
            "consistency_score": score,
            "is_cross_doc": is_cross_doc,
            "reasoning": reasoning,
        }
        if quality_score is not None:
            result["quality_score"] = quality_score
        if critique:
            result["critique"] = critique
        if adversarial:
            result["adversarial"] = adversarial

        return result
