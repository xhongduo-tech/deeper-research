"""
Sentiment API — public opinion analysis and sentiment tracking.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.sentiment_service import (
    analyze_text_sentiment,
    save_sentiment_to_db,
    build_opinion_profile,
    get_sentiment_dashboard,
)
from app.agents.sentiment_agent import SentimentAgent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


class AnalyzeRequest(BaseModel):
    text: str
    topic: str = ""
    entities: list[str] = []
    domain: str = "general"
    kb_id: Optional[int] = None
    report_id: Optional[int] = None
    save: bool = True


class MultiSourceRequest(BaseModel):
    texts: list[dict]   # [{text, source, date}]
    topic: str
    entities: list[str] = []
    domain: str = "general"
    kb_id: Optional[int] = None
    report_id: Optional[int] = None


class OpinionProfileRequest(BaseModel):
    subject: str
    subject_type: str = "topic"
    kb_id: Optional[int] = None
    report_id: Optional[int] = None


class RiskScanRequest(BaseModel):
    text: str
    topic: str = ""
    domain: str = "general"


@router.post("/analyze")
async def analyze_sentiment(req: AnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """Analyze sentiment of a text with entity and aspect breakdown."""
    if len(req.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="文本太短")

    result = await analyze_text_sentiment(
        req.text, entities=req.entities, doc_ref=req.topic, domain=req.domain
    )

    saved_count = 0
    if req.save:
        saved_count = await save_sentiment_to_db(
            db, result,
            kb_id=req.kb_id,
            report_id=req.report_id,
            doc_ref=req.topic,
            text_snippet=req.text[:500],
        )

    return {
        "analysis": result,
        "saved_records": saved_count,
    }


@router.post("/analyze-multi")
async def analyze_multi_source(req: MultiSourceRequest, db: AsyncSession = Depends(get_db)):
    """Analyze and synthesize sentiment across multiple source texts."""
    if not req.texts:
        raise HTTPException(status_code=400, detail="至少需要提供一份文本")

    agent = SentimentAgent()
    result = await agent.analyze_multi_source(
        req.texts, topic=req.topic, entities=req.entities, domain=req.domain
    )

    for i, (text_item, analysis) in enumerate(
        zip(req.texts, result.get("individual_analyses", []))
    ):
        await save_sentiment_to_db(
            db, analysis,
            kb_id=req.kb_id,
            report_id=req.report_id,
            doc_ref=text_item.get("source", f"source-{i}"),
            text_snippet=text_item.get("text", "")[:300],
        )

    return result


@router.post("/risk-scan")
async def risk_scan(req: RiskScanRequest):
    """Focused risk signal detection — no DB persistence."""
    agent = SentimentAgent()
    return await agent.detect_risk_signals(req.text, topic=req.topic, domain=req.domain)


@router.post("/profile")
async def get_or_build_profile(req: OpinionProfileRequest, db: AsyncSession = Depends(get_db)):
    """Build or retrieve an opinion profile for a subject."""
    if not req.subject.strip():
        raise HTTPException(status_code=400, detail="主题不能为空")

    profile = await build_opinion_profile(
        db, req.subject,
        subject_type=req.subject_type,
        kb_id=req.kb_id,
        report_id=req.report_id,
    )
    return {
        "id": profile.id,
        "subject": profile.subject,
        "subject_type": profile.subject_type,
        "overall_sentiment": profile.overall_sentiment,
        "avg_polarity": round(profile.avg_polarity, 3),
        "avg_subjectivity": round(profile.avg_subjectivity, 3),
        "record_count": profile.record_count,
        "positive_count": profile.positive_count,
        "negative_count": profile.negative_count,
        "neutral_count": profile.neutral_count,
        "top_positive_aspects": profile.get_top_positive_aspects(),
        "top_negative_aspects": profile.get_top_negative_aspects(),
        "summary": profile.summary,
        "last_updated": profile.last_updated.isoformat() if profile.last_updated else None,
    }


@router.get("/dashboard")
async def sentiment_dashboard(
    kb_id: Optional[int] = None,
    report_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated sentiment dashboard data."""
    return await get_sentiment_dashboard(db, kb_id=kb_id, report_id=report_id)
