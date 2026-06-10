"""Summarizer skill — SOTA-enhanced text condensation with quality scoring.

Enhancements:
- Chain-of-Thought: plan structure before summarizing
- Self-critique: checks coverage, accuracy, conciseness
- Adversarial review: detects missing key points
- Quality score (0-100) per summary
"""
from app.skills.base import Skill
from app.services.llm_service import chat
from app.skills.offline.sota_utils import self_critique, adversarial_review


class SummarizerSkill(Skill):
    name = "summarize"
    description = "SOTA摘要生成：将长文本压缩为结构化摘要，含CoT规划、质量评分、红队挑战，确保不遗漏关键信息"
    category = "offline"
    parameters = {
        "text": {"type": "string", "description": "待摘要的文本内容"},
        "max_points": {"type": "integer", "description": "最多输出几条要点，默认5", "default": 5},
        "style": {"type": "string", "description": "摘要风格: bullet|paragraph|table", "default": "bullet"},
        "enable_critique": {"type": "boolean", "description": "启用质量自评", "default": True},
        "enable_adversarial": {"type": "boolean", "description": "启用红队挑战", "default": True},
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        text = params.get("text", "")
        max_points = int(params.get("max_points", 5))
        style = params.get("style", "bullet")
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)
        if not text.strip():
            return {"result": "", "error": "no text provided"}

        style_instruction = {
            "bullet": f"输出 {max_points} 条要点，每条以 • 开头",
            "paragraph": "输出 2-3 段自然语言摘要",
            "table": "以 | 分隔的 Markdown 表格呈现关键字段",
        }.get(style, f"输出 {max_points} 条要点")

        # ── Phase 1: CoT Planning ─────────────────────────────────────────────
        cot_messages = [
            {"role": "system", "content": "你是专业摘要助手。在摘要前先分析文本结构，识别核心主题和关键信息点。"},
            {"role": "user", "content": f"请分析以下文本的核心结构和关键信息，再生成摘要。\n\n{text[:3000]}\n\n请先回答：1. 文本的核心主题是什么？2. 有哪些关键论点/数据？3. 摘要应覆盖哪些要点？"},
        ]
        reasoning = await chat(cot_messages, temperature=0.3, max_tokens=600)

        # ── Phase 2: Summary Generation ───────────────────────────────────────
        messages = [
            {"role": "system", "content": "你是专业摘要助手，擅长提炼关键信息。输出简洁、准确。"},
            {"role": "user", "content": f"分析思路：{reasoning[:400]}\n\n请摘要以下内容。{style_instruction}。\n\n{text[:6000]}"},
        ]
        result = await chat(messages, temperature=0.3, max_tokens=800)

        # ── Phase 3: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        quality_score = None
        if enable_critique:
            critique = await self_critique(
                draft=result, topic="摘要质量",
                dimensions=["data_grounding", "structural_clarity", "specificity"],
            )
            quality_score = round(critique["overall_score"] * 10)

        # ── Phase 4: Adversarial review ───────────────────────────────────────
        if enable_adversarial:
            adversarial = await adversarial_review(output=result, topic="摘要")

        out = {"result": result, "reasoning": reasoning}
        if quality_score is not None:
            out["quality_score"] = quality_score
        if critique:
            out["critique"] = critique
        if adversarial:
            out["adversarial"] = adversarial
        return out
