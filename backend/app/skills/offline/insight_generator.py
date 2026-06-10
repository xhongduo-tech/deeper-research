"""
Insight Generator — SOTA-enhanced non-obvious insight extraction.

Enhancements over v1:
1. Chain-of-Thought reasoning: pattern detection → mechanism inference → strategic implication
2. Adversarial critique per insight (red-team challenges)
3. Confidence calibration with evidence strength
4. Structured JSON output with schema validation
5. Quality score per insight + overall
6. Anti-hallucination guard: evidence anchoring check

Reference: Anthropic's "Building effective agents", Stanford DSPy
"""
import json
from app.skills.base import Skill
from app.services.llm_service import chat, chat_json
from app.skills.offline.sota_utils import (
    self_critique,
    adversarial_review,
    structured_generate,
)


class InsightGeneratorSkill(Skill):
    name = "generate_insights"
    description = (
        "SOTA洞察生成：从研究发现中提炼非显而易见的高价值洞察。"
        "包含CoT推理→生成→对抗评审→置信度校准→结构化JSON输出的完整流程"
    )
    category = "offline"
    parameters = {
        "findings": {"type": "string", "description": "研究发现内容（越详细越好）"},
        "topic": {"type": "string", "description": "研究主题"},
        "insight_type": {
            "type": "string",
            "description": "洞察类型: strategic|operational|risk|opportunity|all",
            "default": "all",
        },
        "depth": {
            "type": "string",
            "description": "深度级别: surface|deep|contrarian",
            "default": "deep",
        },
        "count": {
            "type": "integer",
            "description": "生成洞察数量（最多10条）",
            "default": 5,
        },
        "enable_critique": {
            "type": "boolean",
            "description": "启用质量自评",
            "default": True,
        },
        "enable_adversarial": {
            "type": "boolean",
            "description": "启用红队对抗评审",
            "default": True,
        },
        "enable_confidence_calibration": {
            "type": "boolean",
            "description": "启用置信度校准",
            "default": True,
        },
        "min_confidence": {
            "type": "number",
            "description": "最低置信度门槛(0-1)，低于此值的洞察会被过滤",
            "default": 0.6,
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

    # JSON Schema for structured insight output
    INSIGHT_SCHEMA = {
        "insights": [
            {
                "id": "I1",
                "title": "洞察标题（一句话）",
                "type": "strategic|operational|risk|opportunity",
                "finding": "具体观察到了什么（包含数据引用）",
                "mechanism": "为什么会这样（机制解释，含因果链条）",
                "implication": "这意味着什么，应该怎么做（战略含义）",
                "evidence_anchors": ["证据1（引用原文具体数据）", "证据2"],
                "confidence_raw": 0.85,
                "confidence_calibrated": 0.75,
                "confidence_reason": "校准原因：...",
                "novelty_score": 8,
                "actionability_score": 7,
                "contrarian_degree": "moderate",
                "time_horizon": "short|medium|long",
            }
        ],
        "synthesis": {
            "theme": "所有洞察的共同主题（一句话）",
            "pattern_type": "因果链|反馈环|临界点|结构矛盾|先行指标",
            "overall_quality": 7.5,
            "key_recommendation": "最重要的单一行动建议",
        },
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        findings = params.get("findings", "")
        topic = params.get("topic", "")
        insight_type = params.get("insight_type", "all")
        depth = params.get("depth", "deep")
        count = min(params.get("count", 5), 10)
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)
        enable_confidence_calibration = params.get("enable_confidence_calibration", True)
        min_confidence = params.get("min_confidence", 0.6)

        if not findings and not topic:
            return {"result": "", "insights": [], "error": "findings or topic required"}

        depth_hint = self.DEPTH_PROMPTS.get(depth, self.DEPTH_PROMPTS["deep"])
        focus_areas = self.TYPE_FILTERS.get(insight_type, self.TYPE_FILTERS["all"])
        focus_str = "、".join(focus_areas)

        # ── Phase 1: CoT Pattern Detection ───────────────────────────────────────
        cot_system = f"""你是顶级研究分析师，专门从复杂数据中提炼非显而易见的深层洞察。

你的洞察标准：
1. **不是重述事实**：洞察 = 事实 + 机制解释 + 战略含义
2. **不是表面趋势**：挖掘{depth_hint}
3. **有行动指向**：每条洞察能指导具体决策
4. **反常识优先**：如果结论是"显而易见的"，继续挖掘更深层的

关注维度：{focus_str}

思考步骤（必须在输出中包含）：
Step 1 - 模式识别：从数据中提取所有不寻常的模式和异常点
Step 2 - 机制推断：为每个模式构建因果解释（为什么发生）
Step 3 - 含义推导：从机制推导出战略含义（应该怎么做）
Step 4 - 置信度评估：基于证据充分程度评估每条洞察的可信度"""

        cot_user = f"""请从以下研究发现中提炼{count}条高价值洞察。

## 研究主题
{topic}

## 研究发现
{findings[:3000]}

## 要求
- 先进行CoT思考（模式识别→机制推断→含义推导）
- 然后输出{count}条结构化洞察
- 每条洞察必须引用原文中的具体数据作为证据锚点
- 避免"市场在增长""竞争激烈""需要关注"等空洞表述
- 优先挖掘以下类型的洞察：
  * 反直觉：表面看是A，实际上是B
  * 因果倒置：看似原因其实是结果
  * 临界点效应：在某个阈值之前/之后完全不同
  * 被忽视的先行指标：通常领先结果6-18个月
  * 结构性矛盾：两个看似合理的趋势相互冲突

请直接输出思考过程和洞察。"""

        cot_result = await chat(
            [{"role": "system", "content": cot_system}, {"role": "user", "content": cot_user}],
            temperature=0.4,
            max_tokens=4000,
        )

        # ── Phase 2: Structured JSON Generation ──────────────────────────────────
        schema_desc = """输出必须是符合以下Schema的JSON对象：

insights数组：每条洞察包含 id, title, type, finding, mechanism, implication,
evidence_anchors(数组), confidence_raw(0-1), confidence_calibrated(0-1),
confidence_reason, novelty_score(1-10), actionability_score(1-10),
contrarian_degree(none|low|moderate|high), time_horizon(short|medium|long)

synthesis对象：包含 theme, pattern_type, overall_quality(0-10), key_recommendation"""

        json_system = f"""你是顶级研究分析师。将以下洞察内容转化为严格结构化的JSON。

{schema_desc}

规则：
1. confidence_raw是初始置信度（基于证据直接评估）
2. confidence_calibrated是校准后的置信度（考虑认知偏差后的修正）
3. evidence_anchors必须引用原文中的具体数据/数字
4. novelty_score：1=常识，10=高度反直觉
5. actionability_score：1=纯理论，10=立即可执行"""

        json_user = f"""请将以下分析内容转化为结构化JSON。

## 分析内容
{cot_result[:3500]}

## 研究主题
{topic}

请只输出JSON对象，不要任何其他文本。"""

        structured = await structured_generate(
            system=json_system,
            user=json_user,
            schema_description=schema_desc,
            output_schema=self.INSIGHT_SCHEMA,
            temperature=0.3,
            max_tokens=3000,
        )

        if structured["error"]:
            # Fallback: return CoT text
            return {
                "result": cot_result,
                "insights": self._parse_insights_legacy(cot_result),
                "structured_error": structured["error"],
                "quality_score": None,
            }

        data = structured["data"] or {}
        insights = data.get("insights", [])
        synthesis = data.get("synthesis", {})

        # ── Phase 3: Confidence Calibration ──────────────────────────────────────
        if enable_confidence_calibration and insights:
            insights = await self._calibrate_confidence(insights, findings)

        # Filter by min_confidence
        filtered = [i for i in insights if i.get("confidence_calibrated", 0) >= min_confidence]

        # ── Phase 4: Self-critique (overall) ─────────────────────────────────────
        critique = None
        if enable_critique and filtered:
            try:
                critique = await self_critique(
                    draft=json.dumps(filtered[:3], ensure_ascii=False),
                    topic=f"洞察生成 - {topic}",
                    dimensions=["data_grounding", "insight_depth", "specificity"],
                )
            except Exception:
                pass

        # ── Phase 5: Adversarial Review (per insight) ────────────────────────────
        adversarial_results = []
        if enable_adversarial and filtered:
            for insight in filtered[:5]:  # Review top 5
                adv = await adversarial_review(
                    output=json.dumps(insight, ensure_ascii=False),
                    topic=f"{topic} - {insight.get('title', '')}",
                )
                insight["adversarial_review"] = adv
                adversarial_results.append(adv)

        # ── Phase 5: Overall Quality Score ───────────────────────────────────────
        overall_quality = synthesis.get("overall_quality", 5.0)
        if filtered:
            avg_confidence = sum(i.get("confidence_calibrated", 0) for i in filtered) / len(filtered)
            avg_novelty = sum(i.get("novelty_score", 5) for i in filtered) / len(filtered)
            overall_quality = round((overall_quality + avg_confidence * 10 + avg_novelty) / 3, 1)

        # ── Phase 6: Build final result text ─────────────────────────────────────
        result_text = self._build_result_text(filtered, synthesis)

        out = {
            "result": result_text,
            "insights": filtered,
            "synthesis": synthesis,
            "quality_score": round(overall_quality * 10),
            "structured_output": data,
            "adversarial_reviews": adversarial_results,
            "filtered_count": len(filtered),
            "original_count": len(insights),
            "depth": depth,
            "insight_type": insight_type,
        }
        if critique:
            out["critique"] = critique
        return out

    async def _calibrate_confidence(self, insights: list, findings: str) -> list:
        """Calibrate confidence scores using base rate awareness and evidence strength."""
        system = """你是校准专家。你的任务是修正每条洞察的置信度，考虑以下认知偏差：

1. **过度自信偏差**：分析师倾向于高估自己的判断
2. **确认偏差**：只关注支持自己观点的证据
3. **样本量幻觉**：从小样本得出大结论
4. **时效性忽略**：没有考虑数据是否过时

校准规则：
- 如果evidence_anchors少于2条，confidence_calibrated = confidence_raw × 0.7
- 如果evidence_anchors中没有具体数字，confidence_calibrated = confidence_raw × 0.8
- 如果洞察涉及预测未来，confidence_calibrated = confidence_raw × 0.85
- 如果洞察是反直觉的，confidence_calibrated = confidence_raw × 0.9（额外折扣）
- 如果有多条独立证据支撑，confidence_calibrated = min(confidence_raw + 0.1, 1.0)

输出JSON格式：
[{"id": "I1", "confidence_calibrated": 0.72, "calibration_reason": "..."}]"""

        user = f"""请校准以下洞察的置信度。

## 研究发现原文
{findings[:2000]}

## 洞察列表
{json.dumps(insights, ensure_ascii=False, indent=2)[:2500]}

请输出校准后的JSON数组。"""

        parsed = await chat_json(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.2,
            max_tokens=2000,
        )

        if "error" in parsed:
            return insights

        # Apply calibrations
        calibration_map = {}
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "id" in item:
                    calibration_map[item["id"]] = item
        elif isinstance(parsed, dict):
            # Maybe wrapped
            for key, val in parsed.items():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, dict) and "id" in item:
                            calibration_map[item["id"]] = item

        for insight in insights:
            insight_id = insight.get("id", "")
            if insight_id in calibration_map:
                cal = calibration_map[insight_id]
                insight["confidence_calibrated"] = cal.get("confidence_calibrated", insight.get("confidence_raw", 0.7))
                insight["calibration_reason"] = cal.get("calibration_reason", "")
            else:
                # Auto-calibrate if missing
                raw = insight.get("confidence_raw", 0.7)
                anchors = insight.get("evidence_anchors", [])
                calibrated = raw
                reason = ""
                if len(anchors) < 2:
                    calibrated = raw * 0.7
                    reason = "证据锚点不足2条"
                elif not any(any(c.isdigit() for c in a) for a in anchors):
                    calibrated = raw * 0.8
                    reason = "证据中缺少具体数字"
                else:
                    calibrated = min(raw + 0.05, 1.0)
                    reason = "基于证据充分程度微调"
                insight["confidence_calibrated"] = round(calibrated, 2)
                insight["calibration_reason"] = reason

        return insights

    def _build_result_text(self, insights: list, synthesis: dict) -> str:
        lines = []
        theme = synthesis.get("theme", "")
        if theme:
            lines.append(f"**洞察主题：{theme}**")
            lines.append("")

        for i, ins in enumerate(insights, 1):
            lines.append(f"**洞察{i}：{ins.get('title', '未命名')}**")
            lines.append(f"- 类型：{ins.get('type', '未分类')}")
            lines.append(f"- 发现：{ins.get('finding', '')}")
            lines.append(f"- 机制：{ins.get('mechanism', '')}")
            lines.append(f"- 含义：{ins.get('implication', '')}")
            anchors = ins.get('evidence_anchors', [])
            if anchors:
                lines.append(f"- 证据锚点：{'；'.join(anchors)}")
            lines.append(f"- 置信度：{ins.get('confidence_calibrated', ins.get('confidence_raw', 'N/A'))}（{ins.get('calibration_reason', '')}）")
            lines.append(f"- 新颖度：{ins.get('novelty_score', 'N/A')}/10")
            lines.append(f"- 可执行度：{ins.get('actionability_score', 'N/A')}/10")
            lines.append("")

        key_rec = synthesis.get("key_recommendation", "")
        if key_rec:
            lines.append(f"**核心建议：{key_rec}**")

        return "\n".join(lines)

    def _parse_insights_legacy(self, text: str) -> list:
        """Fallback parser for non-JSON output."""
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
                current = {
                    "title": title,
                    "finding": "",
                    "mechanism": "",
                    "implication": "",
                    "confidence": "中",
                }
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
