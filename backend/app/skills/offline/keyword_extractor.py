"""Keyword Extractor — extract entities, themes, and structured metadata from text."""
from app.skills.base import Skill
from app.services.llm_service import chat_json


class KeywordExtractorSkill(Skill):
    name = "extract_keywords"
    description = "从文本中提取关键词、命名实体（人名/公司/地点/时间/金额）、主题标签，用于索引和摘要"
    category = "offline"
    parameters = {
        "text": {"type": "string", "description": "待提取关键词的文本"},
        "extract_entities": {"type": "boolean", "description": "是否提取命名实体", "default": True},
        "max_keywords": {"type": "integer", "description": "最多关键词数量", "default": 15},
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        text = params.get("text", "")
        extract_entities = params.get("extract_entities", True)
        max_keywords = int(params.get("max_keywords", 15))
        if not text.strip():
            return {"result": {}, "error": "no text"}

        resp = await chat_json(
            [
                {"role": "system", "content": "你是信息提取专家，输出严格 JSON。"},
                {"role": "user", "content": f"""从以下文本提取结构化信息。

文本（前3000字符）:
{text[:3000]}

输出 JSON（最多 {max_keywords} 个关键词）:
{{
  "keywords": ["词1", "词2"],
  "entities": {{"persons": [], "organizations": [], "locations": [], "dates": [], "amounts": []}},
  "themes": ["主题1", "主题2"],
  "sentiment": "positive|neutral|negative",
  "summary_one_line": "一句话概括"
}}"""},
            ],
            temperature=0.1,
        )
        return {"result": resp}
