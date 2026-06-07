"""
Sentiment Service — multi-document opinion mining and sentiment analysis.

Analyzes text for entity-level and aspect-level sentiment, tracks temporal
trends, and generates opinion profiles for topics or entities.
"""
import json
import logging
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sentiment import SentimentRecord, OpinionProfile
from app.services.llm_service import chat
from app.services.model_router import get_model_router

logger = logging.getLogger(__name__)


SYSTEM_SENTIMENT = """你是专业的舆情分析专家。对给定文本进行细粒度情感分析，以JSON格式输出结果。
保持客观准确，情感判断基于文本证据而非主观推断。"""

EMOTION_TAGS = ["乐观", "担忧", "信任", "质疑", "期待", "恐慌", "愤怒", "满意", "不满", "中立"]

ASPECT_KEYWORDS = {
    "财务": ["营收", "利润", "亏损", "盈利", "债务", "现金流", "估值"],
    "风险": ["风险", "危机", "违规", "处罚", "诉讼", "违约"],
    "产品": ["产品", "服务", "质量", "创新", "技术", "研发"],
    "市场": ["市场", "份额", "竞争", "客户", "用户", "增长"],
    "管理": ["管理层", "治理", "战略", "决策", "执行", "人才"],
    "政策": ["政策", "监管", "法规", "合规", "审批", "许可"],
    "宏观": ["经济", "通胀", "利率", "汇率", "GDP", "就业"],
}


async def analyze_text_sentiment(
    text: str,
    entities: Optional[list[str]] = None,
    doc_ref: str = "",
    domain: str = "general",
) -> dict:
    """
    Full sentiment analysis on a text snippet.
    Returns structured result with entity/aspect level breakdown.
    """
    entity_guide = f"重点关注实体：{', '.join(entities[:10])}" if entities else "提取文本中的主要实体"

    messages = [
        {"role": "system", "content": SYSTEM_SENTIMENT},
        {
            "role": "user",
            "content": f"""对以下文本进行情感分析。领域：{domain}。
{entity_guide}

文本：
{text[:2500]}

返回JSON（仅JSON）：
{{
  "document_sentiment": {{
    "sentiment": "positive|negative|neutral|mixed",
    "polarity": 0.0,
    "subjectivity": 0.5,
    "confidence": 0.9,
    "summary": "一句话总结文本整体情感倾向"
  }},
  "entity_sentiments": [
    {{
      "entity": "实体名称",
      "entity_type": "company|person|product|policy|market|concept",
      "sentiment": "positive|negative|neutral|mixed",
      "polarity": 0.0,
      "aspects": [
        {{
          "aspect": "方面名称",
          "sentiment": "positive|negative|neutral",
          "evidence": "支撑文本片段"
        }}
      ]
    }}
  ],
  "emotion_tags": ["乐观", "担忧"],
  "key_opinion_words": {{
    "positive": ["积极词1", "积极词2"],
    "negative": ["消极词1", "消极词2"]
  }},
  "risk_signals": ["风险信号1", "风险信号2"],
  "opportunity_signals": ["机会信号1", "机会信号2"]
}}

polarity范围：-1.0（极负面）到+1.0（极正面），0为中性。
subjectivity范围：0（纯客观）到1（纯主观）。""",
        },
    ]
    router = get_model_router()
    model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
    raw = await chat(messages, model=model, base_url=base_url, api_key=api_key,
                     temperature=0.1, max_tokens=2000)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
            cleaned = cleaned.rsplit("```", 1)[0]
        return json.loads(cleaned)
    except Exception as e:
        logger.warning(f"[sentiment] Parse error: {e}")
        return {
            "document_sentiment": {"sentiment": "neutral", "polarity": 0.0,
                                   "subjectivity": 0.5, "confidence": 0.5, "summary": ""},
            "entity_sentiments": [],
            "emotion_tags": [],
            "key_opinion_words": {"positive": [], "negative": []},
            "risk_signals": [],
            "opportunity_signals": [],
        }


async def save_sentiment_to_db(
    db: AsyncSession,
    analysis: dict,
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
    doc_ref: str = "",
    text_snippet: str = "",
) -> int:
    """Persist sentiment records. Returns number of records saved."""
    count = 0

    # Document-level record
    doc_s = analysis.get("document_sentiment", {})
    if doc_s:
        rec = SentimentRecord(
            kb_id=kb_id,
            report_id=report_id,
            doc_ref=doc_ref,
            entity="",
            aspect="document",
            text_snippet=text_snippet[:500],
            sentiment=doc_s.get("sentiment", "neutral"),
            polarity=doc_s.get("polarity", 0.0),
            subjectivity=doc_s.get("subjectivity", 0.5),
            confidence=doc_s.get("confidence", 0.8),
            emotion_tags=json.dumps(analysis.get("emotion_tags", []), ensure_ascii=False),
            keywords=json.dumps(
                analysis.get("key_opinion_words", {}).get("positive", []) +
                analysis.get("key_opinion_words", {}).get("negative", []),
                ensure_ascii=False,
            ),
        )
        db.add(rec)
        count += 1

    # Entity-level records
    for ent in analysis.get("entity_sentiments", []):
        entity_name = ent.get("entity", "")
        if not entity_name:
            continue
        for asp in ent.get("aspects", [{}]):
            rec = SentimentRecord(
                kb_id=kb_id,
                report_id=report_id,
                doc_ref=doc_ref,
                entity=entity_name,
                aspect=asp.get("aspect", "general"),
                text_snippet=asp.get("evidence", text_snippet[:300]),
                sentiment=asp.get("sentiment", ent.get("sentiment", "neutral")),
                polarity=ent.get("polarity", 0.0),
                subjectivity=0.5,
                confidence=0.8,
                emotion_tags=json.dumps(analysis.get("emotion_tags", []), ensure_ascii=False),
                keywords=json.dumps([], ensure_ascii=False),
            )
            db.add(rec)
            count += 1
        if not ent.get("aspects"):
            rec = SentimentRecord(
                kb_id=kb_id,
                report_id=report_id,
                doc_ref=doc_ref,
                entity=entity_name,
                aspect="general",
                text_snippet=text_snippet[:300],
                sentiment=ent.get("sentiment", "neutral"),
                polarity=ent.get("polarity", 0.0),
                subjectivity=0.5,
                confidence=0.8,
            )
            db.add(rec)
            count += 1

    await db.commit()
    return count


async def build_opinion_profile(
    db: AsyncSession,
    subject: str,
    subject_type: str = "topic",
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
) -> OpinionProfile:
    """Aggregate sentiment records into an OpinionProfile for a subject."""
    q = select(SentimentRecord).where(
        (SentimentRecord.entity == subject) | (SentimentRecord.entity == "")
    )
    if kb_id:
        q = q.where(SentimentRecord.kb_id == kb_id)
    if report_id:
        q = q.where(SentimentRecord.report_id == report_id)

    records = (await db.execute(q)).scalars().all()
    if not records:
        records = []

    pos = sum(1 for r in records if r.sentiment == "positive")
    neg = sum(1 for r in records if r.sentiment == "negative")
    neu = sum(1 for r in records if r.sentiment in ("neutral", "mixed"))
    total = len(records) or 1

    avg_pol = sum(r.polarity for r in records) / total
    avg_sub = sum(r.subjectivity for r in records) / total

    if avg_pol > 0.2:
        overall = "positive"
    elif avg_pol < -0.2:
        overall = "negative"
    else:
        overall = "neutral"

    # Aggregate aspect opinions
    pos_aspects: dict[str, int] = {}
    neg_aspects: dict[str, int] = {}
    for r in records:
        if r.aspect and r.aspect != "document":
            if r.sentiment == "positive":
                pos_aspects[r.aspect] = pos_aspects.get(r.aspect, 0) + 1
            elif r.sentiment == "negative":
                neg_aspects[r.aspect] = neg_aspects.get(r.aspect, 0) + 1

    top_pos = sorted(pos_aspects, key=pos_aspects.get, reverse=True)[:5]
    top_neg = sorted(neg_aspects, key=neg_aspects.get, reverse=True)[:5]

    # Generate LLM summary
    summary = await _generate_opinion_summary(
        subject, records, top_pos, top_neg, overall, avg_pol
    )

    # Upsert profile
    existing = (
        await db.execute(
            select(OpinionProfile).where(
                OpinionProfile.subject == subject,
                OpinionProfile.kb_id == kb_id,
                OpinionProfile.report_id == report_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.overall_sentiment = overall
        existing.avg_polarity = avg_pol
        existing.avg_subjectivity = avg_sub
        existing.record_count = len(records)
        existing.positive_count = pos
        existing.negative_count = neg
        existing.neutral_count = neu
        existing.top_positive_aspects = json.dumps(top_pos, ensure_ascii=False)
        existing.top_negative_aspects = json.dumps(top_neg, ensure_ascii=False)
        existing.summary = summary
        await db.commit()
        return existing

    profile = OpinionProfile(
        kb_id=kb_id,
        report_id=report_id,
        subject=subject,
        subject_type=subject_type,
        overall_sentiment=overall,
        avg_polarity=avg_pol,
        avg_subjectivity=avg_sub,
        record_count=len(records),
        positive_count=pos,
        negative_count=neg,
        neutral_count=neu,
        top_positive_aspects=json.dumps(top_pos, ensure_ascii=False),
        top_negative_aspects=json.dumps(top_neg, ensure_ascii=False),
        summary=summary,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def _generate_opinion_summary(
    subject: str,
    records: list,
    top_pos: list[str],
    top_neg: list[str],
    overall: str,
    avg_pol: float,
) -> str:
    if not records:
        return "暂无足够数据生成舆情摘要。"
    snippets = "\n".join(f"- {r.text_snippet[:100]}" for r in records[:8] if r.text_snippet)
    messages = [
        {
            "role": "system",
            "content": "你是舆情分析师，根据情感记录生成客观、简洁的舆情摘要（150字以内）。",
        },
        {
            "role": "user",
            "content": f"""主题：{subject}
整体情感：{overall}（极性均值：{avg_pol:.2f}）
正面方面：{', '.join(top_pos) or '无'}
负面方面：{', '.join(top_neg) or '无'}
典型文本片段：
{snippets}

请生成一段客观的舆情摘要，涵盖主要观点、关键分歧和整体趋势。""",
        },
    ]
    router = get_model_router()
    model, base_url, api_key = router.route_for_chat(agent_type="nova", messages=messages)
    return await chat(messages, model=model, base_url=base_url, api_key=api_key,
                      temperature=0.3, max_tokens=300)


async def get_sentiment_dashboard(
    db: AsyncSession,
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
) -> dict:
    """Return aggregated sentiment stats for dashboard display."""
    q = select(SentimentRecord)
    if kb_id:
        q = q.where(SentimentRecord.kb_id == kb_id)
    if report_id:
        q = q.where(SentimentRecord.report_id == report_id)
    records = (await db.execute(q)).scalars().all()

    if not records:
        return {"total": 0, "distribution": {}, "top_entities": [], "profiles": []}

    distribution = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    entity_pol: dict[str, list[float]] = {}
    for r in records:
        distribution[r.sentiment] = distribution.get(r.sentiment, 0) + 1
        if r.entity:
            entity_pol.setdefault(r.entity, []).append(r.polarity)

    top_entities = sorted(
        [{"entity": e, "avg_polarity": sum(v) / len(v), "count": len(v)}
         for e, v in entity_pol.items()],
        key=lambda x: abs(x["avg_polarity"]),
        reverse=True,
    )[:10]

    profiles_q = select(OpinionProfile)
    if kb_id:
        profiles_q = profiles_q.where(OpinionProfile.kb_id == kb_id)
    if report_id:
        profiles_q = profiles_q.where(OpinionProfile.report_id == report_id)
    profiles = (await db.execute(profiles_q)).scalars().all()

    return {
        "total": len(records),
        "distribution": distribution,
        "top_entities": top_entities,
        "profiles": [
            {
                "id": p.id,
                "subject": p.subject,
                "subject_type": p.subject_type,
                "overall_sentiment": p.overall_sentiment,
                "avg_polarity": round(p.avg_polarity, 3),
                "record_count": p.record_count,
                "positive_count": p.positive_count,
                "negative_count": p.negative_count,
                "top_positive": p.get_top_positive_aspects(),
                "top_negative": p.get_top_negative_aspects(),
                "summary": p.summary,
            }
            for p in profiles
        ],
    }
