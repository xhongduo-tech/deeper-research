"""Causal Analysis Skill — SOTA-enhanced multi-layer cause-effect extraction.

Enhancements:
  - Chain-of-Thought reasoning: identify mechanisms before causal chains
  - Self-critique: checks correlation-vs-causation distinction, confounder awareness
  - Adversarial review: challenges causal jumps, counterfactual validity
  - Quality score (0-100) per analysis
  - Structured JSON output with auto-repair
  - Confidence calibration per causal link
"""
from app.skills.base import Skill
from app.services.llm_service import chat
from app.services.model_router import get_model_router
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class CausalAnalysisSkill(Skill):
    name = "causal_analysis"
    category = "analysis"
    description = (
        "SOTA因果分析：从文本中提取多层因果链、根本驱动因素和连锁效应，"
        "含CoT推理、置信度评分、干预点识别、反事实推演、时间滞后估计。"
        "含自评和红队挑战，输出质量评分"
    )
    parameters = {
        "text":    {"type": "string",  "description": "待分析文本"},
        "topic":   {"type": "string",  "description": "分析主题", "default": ""},
        "depth":   {"type": "integer", "description": "因果链深度（1-3）", "default": 2},
        "mode":    {
            "type": "string",
            "description": "分析模式: full | chains_only | root_cause | intervention",
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

    _CONFIDENCE_GUIDE = """
置信度判断标准：
- **高** (Corroborated)：文本中有直接证据，因果关系被明确陈述或数据支持
- **中** (Plausible)：文本中有间接证据，因果关系符合逻辑但未直接证明
- **低** (Speculative)：基于领域常识推断，文本中无直接依据"""

    CAUSAL_SCHEMA = {
        "causal_chains": [
            {
                "chain_id": "C1",
                "chain": "因素A → 因素B → 因素C",
                "link_confidences": ["high", "medium", "low"],
                "time_lag": "即时|短期1-3月|中期3-12月|长期1年+",
                "overall_confidence": "high|medium|low",
                "key_evidence": "",
            }
        ],
        "root_causes": [
            {
                "driver": "",
                "type": "结构性|周期性|触发性|政策性|技术性",
                "impact_weight": "高|中|低",
                "confidence": "high|medium|low",
                "evidence": "",
            }
        ],
        "feedback_loops": [
            {
                "loop_type": "正反馈|负反馈",
                "description": "",
                "nodes": ["A", "B", "C"],
                "confidence": "high|medium|low",
            }
        ],
        "interventions": [
            {
                "intervention_point": "",
                "current_status": "",
                "recommended_action": "",
                "expected_effect": "",
                "feasibility": "高|中|低",
                "confidence": "high|medium|low",
            }
        ],
        "counterfactuals": [
            {
                "scenario": "",
                "assumption": "",
                "projected_outcome": "",
                "confidence": "high|medium|low",
            }
        ],
        "analysis_summary": "",
        "analysis_quality": 8.0,
    }

    async def execute(self, text: str = "", topic: str = "",
                      depth: int = 2, mode: str = "full",
                      enable_critique: bool = True, enable_adversarial: bool = True,
                      **kwargs) -> dict:
        params = kwargs.get("params", {})
        if params:
            text  = params.get("text", text)
            topic = params.get("topic", topic)
            depth = int(params.get("depth", depth))
            mode  = params.get("mode", mode)
            enable_critique = params.get("enable_critique", enable_critique)
            enable_adversarial = params.get("enable_adversarial", enable_adversarial)

        depth = min(max(int(depth), 1), 3)

        # ── Phase 1: CoT Reasoning ────────────────────────────────────────────
        system_msg = f"""你是专业因果推理分析师，具备系统性思维和跨领域因果分析能力。{self._CONFIDENCE_GUIDE}

你的任务是从给定文本中进行严格的因果分析，遵循：
1. 区分相关性（correlation）和因果性（causation）
2. 识别混淆变量（confounders）
3. 区分直接原因和根本原因（proximate vs. root cause）
4. 标注每个因果关系的置信度"""

        cot_messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"""在进行正式因果分析前，请先逐步思考以下问题：

分析主题：{topic or '（文本自动识别）'}
因果链深度：{depth}层

文本（前2000字）：
{text[:2000]}

思考任务：
1. 文本中涉及的核心变量有哪些？
2. 哪些关系可能是因果性的，哪些只是相关性的？
3. 可能存在哪些混淆变量？
4. 因果传导的时间顺序是什么？

请输出你的思考过程。"""},
        ]
        router = get_model_router()
        model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=cot_messages)
        reasoning = await chat(cot_messages, model=model, base_url=base_url, api_key=api_key,
                               temperature=0.2, max_tokens=1000)

        # ── Phase 2: Structured extraction ────────────────────────────────────
        schema_desc = """输出严格JSON，包含：
- causal_chains: 核心因果链（每条含link_confidences, time_lag, overall_confidence, key_evidence）
- root_causes: 根本驱动因素（含type, impact_weight, confidence, evidence）
- feedback_loops: 反馈环识别
- interventions: 干预点与应对策略
- counterfactuals: 反事实推演
- analysis_summary: 分析摘要
- analysis_quality: 1-10分自评"""

        mode_filter = f"分析模式：{mode}（只输出该模式相关内容，其他设为空数组）"

        user_content = f"""{reasoning[:500]}

分析主题：{topic or '（文本自动识别）'}
因果链深度：{depth}层
{mode_filter}

---
待分析文本：
{text[:3000]}
---

请提供完整的因果分析报告：
{schema_desc}

重要：
- 每个因果关系必须标注置信度
- 必须引用原文证据
- 区分因果与相关"""

        structured = await structured_generate(
            system=system_msg,
            user=user_content,
            schema_description=schema_desc,
            output_schema=self.CAUSAL_SCHEMA,
            temperature=0.2,
            max_tokens=2500,
        )

        analysis = structured.get("data", {}) if not structured.get("error") else {}

        # ── Phase 3: Build narrative from structured data ─────────────────────
        narrative_lines = []
        chains = analysis.get("causal_chains", [])
        if chains:
            narrative_lines.append(f"### 🔗 核心因果链（深度 {depth} 层）")
            for c in chains[:5]:
                conf = c.get("overall_confidence", "medium")
                conf_icon = {"high": "✓", "medium": "~", "low": "?"}.get(conf, "")
                narrative_lines.append(f"  {conf_icon} {c.get('chain', '')} [置信度: {conf}]")
                if c.get("key_evidence"):
                    narrative_lines.append(f"    证据：{c['key_evidence'][:60]}")

        roots = analysis.get("root_causes", [])
        if roots:
            narrative_lines.append("\n### 🎯 根本驱动因素")
            for r in roots[:5]:
                narrative_lines.append(
                    f"  • {r.get('driver', '')}（{r.get('type', '')}，权重：{r.get('impact_weight', '')}，置信度：{r.get('confidence', '')}）"
                )

        loops = analysis.get("feedback_loops", [])
        if loops:
            narrative_lines.append("\n### 🔄 反馈环")
            for l in loops[:3]:
                narrative_lines.append(f"  • {l.get('loop_type', '')}：{l.get('description', '')}")

        interventions = analysis.get("interventions", [])
        if interventions:
            narrative_lines.append("\n### ⚡ 干预点")
            for i in interventions[:4]:
                narrative_lines.append(f"  • {i.get('intervention_point', '')} → {i.get('recommended_action', '')}")

        counterfactuals = analysis.get("counterfactuals", [])
        if counterfactuals:
            narrative_lines.append("\n### 📊 反事实推演")
            for c in counterfactuals[:2]:
                narrative_lines.append(f"  • 假设：{c.get('assumption', '')}")
                narrative_lines.append(f"    推演：{c.get('projected_outcome', '')}")

        if analysis.get("analysis_summary"):
            narrative_lines.append(f"\n**分析摘要**：{analysis['analysis_summary']}")

        narrative = "\n".join(narrative_lines) if narrative_lines else reasoning

        # ── Phase 4: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique and analysis:
            critique = await self_critique(
                draft=narrative[:3000],
                topic=f"{topic or '因果分析'} - 深度{depth}层",
                dimensions=["data_grounding", "logical_rigor", "specificity"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 5: Adversarial review ───────────────────────────────────────
        if enable_adversarial and analysis:
            adversarial = await adversarial_review(
                output=narrative[:3000],
                topic=f"{topic or '因果分析'} - 深度{depth}层",
            )

        result = {
            "result": narrative,
            "topic": topic,
            "depth": depth,
            "mode": mode,
            "analysis": analysis,
            "reasoning": reasoning,
        }
        if quality_score is not None:
            result["quality_score"] = quality_score
        if critique:
            result["critique"] = critique
        if adversarial:
            result["adversarial"] = adversarial

        return result
