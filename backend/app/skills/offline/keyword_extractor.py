"""Keyword Extractor — SOTA-enhanced entity/theme extraction with confidence scoring.

Enhancements:
- Chain-of-Thought: analyze text structure before extraction
- Confidence scoring per entity
- Self-critique: checks extraction completeness
- Adversarial review: challenges low-confidence extractions
- Structured JSON with validation
- Quality score for extraction completeness
"""
from app.skills.base import Skill
from app.services.llm_service import chat_json
from app.skills.offline.sota_utils import self_critique, adversarial_review, structured_generate


class KeywordExtractorSkill(Skill):
    name = "extract_keywords"
    description = "SOTA关键词提取：从文本中提取带置信度评分的命名实体、主题标签和结构化元数据，含CoT分析、自评和红队挑战"
    category = "offline"
    parameters = {
        "text": {"type": "string", "description": "待提取关键词的文本"},
        "extract_entities": {"type": "boolean", "description": "是否提取命名实体", "default": True},
        "max_keywords": {"type": "integer", "description": "最多关键词数量", "default": 15},
        "enable_critique": {"type": "boolean", "description": "启用质量自评", "default": True},
        "enable_adversarial": {"type": "boolean", "description": "启用红队挑战", "default": True},
    }

    EXTRACTION_SCHEMA = {
        "keywords": [{"word": "", "confidence": 0.95, "category": "technical|business|general"}],
        "entities": {
            "persons": [{"name": "", "confidence": 0.9}],
            "organizations": [{"name": "", "confidence": 0.9}],
            "locations": [{"name": "", "confidence": 0.9}],
            "dates": [{"value": "", "confidence": 0.9}],
            "amounts": [{"value": "", "confidence": 0.9}],
        },
        "themes": [{"theme": "", "confidence": 0.85}],
        "sentiment": "positive|neutral|negative",
        "sentiment_confidence": 0.8,
        "summary_one_line": "",
        "extraction_quality": 8.5,
    }

    async def execute(self, params: dict, context: dict | None = None) -> dict:
        text = params.get("text", "")
        extract_entities = params.get("extract_entities", True)
        max_keywords = int(params.get("max_keywords", 15))
        enable_critique = params.get("enable_critique", True)
        enable_adversarial = params.get("enable_adversarial", True)
        if not text.strip():
            return {"result": {}, "error": "no text"}

        # ── Phase 1: CoT Analysis ─────────────────────────────────────────────
        cot_messages = [
            {"role": "system", "content": "你是信息提取专家。在提取前先分析文本类型、主题和关键信息分布。"},
            {"role": "user", "content": f"请分析以下文本，识别其类型、主题和关键信息分布。\n\n{text[:1500]}\n\n回答：1. 这是什么类型的文本？2. 核心主题是什么？3. 有哪些明显的关键词和实体？"},
        ]
        reasoning = await chat_json(cot_messages, temperature=0.2, max_tokens=500)
        reasoning_text = reasoning.get("result", str(reasoning)) if isinstance(reasoning, dict) else str(reasoning)

        schema_desc = """输出严格JSON，包含：
- keywords: 带confidence的关键词数组
- entities: 各类命名实体（含confidence）
- themes: 主题标签（含confidence）
- sentiment + sentiment_confidence
- summary_one_line
- extraction_quality: 1-10分自评"""

        structured = await structured_generate(
            system=f"你是信息提取专家，擅长从文本中精准提取结构化信息。为每个提取项标注置信度。分析思路：{reasoning_text[:300]}",
            user=f"""从以下文本提取结构化信息。

文本（前3000字符）:
{text[:3000]}

要求：
- 最多 {max_keywords} 个关键词
- 每条含置信度(0-1)
- {'提取命名实体' if extract_entities else '不提取命名实体'}

{schema_desc}""",
            schema_description=schema_desc,
            output_schema=self.EXTRACTION_SCHEMA,
            temperature=0.1,
            max_tokens=1500,
        )

        data = structured.get("data", {}) if not structured.get("error") else {}
        quality_score = round(data.get("extraction_quality", 5) * 10) if data else None

        # ── Phase 2: Self-critique ────────────────────────────────────────────
        critique = None
        adversarial = None
        if enable_critique and data:
            critique = await self_critique(
                draft=str(data)[:2000],
                topic="关键词提取",
                dimensions=["data_grounding", "specificity", "completeness"],
            )
            if quality_score is None:
                quality_score = round(critique["overall_score"] * 10)

        # ── Phase 3: Adversarial review ───────────────────────────────────────
        if enable_adversarial and data:
            adversarial = await adversarial_review(
                output=str(data)[:2000],
                topic="关键词提取",
            )

        out = {
            "result": data,
            "quality_score": quality_score,
            "repair_count": structured.get("repair_count", 0),
            "error": structured.get("error"),
            "reasoning": reasoning_text,
        }
        if critique:
            out["critique"] = critique
        if adversarial:
            out["adversarial"] = adversarial
        return out
