"""Summarizer skill — condense long text into key points."""
from app.skills.base import Skill
from app.services.llm_service import chat


class SummarizerSkill(Skill):
    name = "summarize"
    description = "将长文本压缩为结构化摘要，提取核心观点、关键数据和结论"
    category = "offline"
    parameters = {
        "text": {"type": "string", "description": "待摘要的文本内容"},
        "max_points": {"type": "integer", "description": "最多输出几条要点，默认5", "default": 5},
        "style": {"type": "string", "description": "摘要风格: bullet|paragraph|table", "default": "bullet"},
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        text = params.get("text", "")
        max_points = int(params.get("max_points", 5))
        style = params.get("style", "bullet")
        if not text.strip():
            return {"result": "", "error": "no text provided"}

        style_instruction = {
            "bullet": f"输出 {max_points} 条要点，每条以 • 开头",
            "paragraph": "输出 2-3 段自然语言摘要",
            "table": "以 | 分隔的 Markdown 表格呈现关键字段",
        }.get(style, f"输出 {max_points} 条要点")

        messages = [
            {"role": "system", "content": "你是专业摘要助手，擅长提炼关键信息。输出简洁、准确。"},
            {"role": "user", "content": f"请摘要以下内容。{style_instruction}。\n\n{text[:6000]}"},
        ]
        result = await chat(messages, temperature=0.3, max_tokens=800)
        return {"result": result}
