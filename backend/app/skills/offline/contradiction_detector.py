"""
Contradiction Detector — cross-claim consistency analysis.

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


class ContradictionDetectorSkill(Skill):
    name = "contradiction_detection"
    category = "analysis"
    description = (
        "跨文档矛盾检测：识别单篇或多篇文本中的事实矛盾、数据冲突、逻辑不一致和观点对立，"
        "输出矛盾清单、严重程度分级和可信度加权建议"
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
    }

    _CONTRADICTION_TYPES = {
        "factual":    "事实矛盾（对同一事实有不同陈述）",
        "temporal":   "时序矛盾（事件顺序不一致）",
        "causal":     "因果矛盾（因果方向相反）",
        "normative":  "价值矛盾（同一事物既被肯定又被否定）",
        "statistical":"数据矛盾（统计数字相互矛盾）",
        "attribution":"归因矛盾（行为/言论的归属不一致）",
    }

    async def execute(self, text: str = "", reference_text: str = "",
                      topic: str = "", focus: str = "all",
                      resolve_contradictions: bool = True, **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text                   = params.get("text", text)
            reference_text         = params.get("reference_text", reference_text)
            topic                  = params.get("topic", topic)
            focus                  = params.get("focus", focus)
            resolve_contradictions = params.get("resolve_contradictions", resolve_contradictions)

        is_cross_doc = bool(reference_text and reference_text.strip())
        mode_desc = "跨文档矛盾分析" if is_cross_doc else "文档内部一致性分析"

        focus_types = (
            list(self._CONTRADICTION_TYPES.keys())
            if focus == "all"
            else [focus] if focus in self._CONTRADICTION_TYPES else list(self._CONTRADICTION_TYPES.keys())
        )
        focus_desc = "；".join(self._CONTRADICTION_TYPES[k] for k in focus_types)

        system_msg = f"""你是批判性分析专家，专门识别文本中的逻辑矛盾和事实冲突。
任务：{mode_desc}。重点检测：{focus_desc}。
严格输出 JSON，不含额外文字。"""

        text_block = f"**主文本（前2500字）：**\n{text[:2500]}"
        if is_cross_doc:
            text_block += f"\n\n**参考文本（前2000字）：**\n{reference_text[:2000]}"

        resolve_schema = """, "resolution_hypothesis": "<如何解释此矛盾的可能假设，如时间差/不同定义/片面引用>", "recommended_action": "verify|prioritize_source_a|prioritize_source_b|flag_for_review" """ if resolve_contradictions else ""

        user_content = f"""分析主题：{topic or '自动识别'}

{text_block}

请进行矛盾检测，输出完整 JSON：
{{
  "contradictions": [
    {{
      "contradiction_id": "CON1",
      "type": "<{'/'.join(focus_types)}>",
      "severity": "critical|major|minor",
      "claim_a": {{
        "text": "<声明A原文≤60字>",
        "source": "doc_a|doc_b|internal",
        "location_hint": "<所在段落关键词>"
      }},
      "claim_b": {{
        "text": "<声明B原文≤60字（与A矛盾）>",
        "source": "doc_a|doc_b|internal",
        "location_hint": "<所在段落关键词>"
      }},
      "contradiction_nature": "<矛盾的具体性质描述≤50字>",
      "confidence": "high|medium|low"{resolve_schema}
    }}
  ],
  "consistency_score": <0-100，整体一致性得分>,
  "critical_issues": ["<需要立即核实的关键矛盾简述>"],
  "internal_consistency": {{
    "is_consistent": <true/false>,
    "issues_count": {{"critical": 0, "major": 0, "minor": 0}}
  }},
  "credibility_assessment": {{
    "overall": "high|medium|low",
    "reasoning": "<为何给出此可信度评级，≤100字>",
    "most_reliable_claims": ["<最可信的核心断言>"],
    "least_reliable_claims": ["<最存疑的断言>"]
  }},
  "summary": "<2-3句综合评价：文本整体一致性如何，主要矛盾集中在哪里>"
}}

注意：
1. 只标记真正的矛盾，不将不同角度的补充性陈述视为矛盾
2. critical = 影响核心结论的矛盾；major = 影响分支论点；minor = 细节差异
3. confidence 表示判断该处为矛盾的把握程度"""

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_content},
        ]

        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)

        raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                         temperature=0.15, max_tokens=2000)

        # Parse
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

        # Narrative
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
                lines.append(f"  - {c.get('contradiction_nature', '')} [置信度: {c.get('confidence', '')}]")
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

        narrative = "\n".join(lines) if lines else raw

        return {
            "result":              narrative,
            "analysis":            analysis,
            "contradiction_count": len(contradictions),
            "consistency_score":   score,
            "is_cross_doc":        is_cross_doc,
        }
