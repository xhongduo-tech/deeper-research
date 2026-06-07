"""Sentiment analysis and opinion mining ORM models."""
import json
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SentimentRecord(Base):
    """Sentiment score for a piece of text (doc, chunk, or entity mention)."""
    __tablename__ = "sentiment_records"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True)
    report_id = Column(Integer, nullable=True)
    doc_ref = Column(String(300), default="")      # source document reference
    entity = Column(String(200), default="")       # target entity (empty = document-level)
    aspect = Column(String(100), default="")       # opinion aspect: price | quality | service | risk | ...
    text_snippet = Column(Text, default="")        # the text being evaluated
    sentiment = Column(String(20), nullable=False) # positive | negative | neutral | mixed
    polarity = Column(Float, default=0.0)          # -1.0 to +1.0
    subjectivity = Column(Float, default=0.5)      # 0 = objective, 1 = subjective
    confidence = Column(Float, default=0.8)
    emotion_tags = Column(Text, default="")        # JSON list: fear | hope | anger | trust | ...
    keywords = Column(Text, default="")            # JSON list of key opinion words
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def get_emotion_tags(self) -> list[str]:
        try:
            return json.loads(self.emotion_tags) if self.emotion_tags else []
        except Exception:
            return []

    def get_keywords(self) -> list[str]:
        try:
            return json.loads(self.keywords) if self.keywords else []
        except Exception:
            return []


class OpinionProfile(Base):
    """Aggregated opinion profile for a topic or entity across all analyzed documents."""
    __tablename__ = "opinion_profiles"

    id = Column(Integer, primary_key=True, index=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=True)
    report_id = Column(Integer, nullable=True)
    subject = Column(String(300), nullable=False)       # entity or topic being profiled
    subject_type = Column(String(60), default="topic")  # topic | company | person | product | policy
    overall_sentiment = Column(String(20), default="neutral")
    avg_polarity = Column(Float, default=0.0)
    avg_subjectivity = Column(Float, default=0.5)
    record_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    top_positive_aspects = Column(Text, default="")  # JSON list
    top_negative_aspects = Column(Text, default="")  # JSON list
    key_risks = Column(Text, default="")             # JSON list of identified risk signals
    key_opportunities = Column(Text, default="")     # JSON list
    temporal_trend = Column(Text, default="")        # JSON list {date, polarity}
    summary = Column(Text, default="")               # LLM-generated narrative summary
    last_updated = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def get_temporal_trend(self) -> list[dict]:
        try:
            return json.loads(self.temporal_trend) if self.temporal_trend else []
        except Exception:
            return []

    def get_top_positive_aspects(self) -> list[str]:
        try:
            return json.loads(self.top_positive_aspects) if self.top_positive_aspects else []
        except Exception:
            return []

    def get_top_negative_aspects(self) -> list[str]:
        try:
            return json.loads(self.top_negative_aspects) if self.top_negative_aspects else []
        except Exception:
            return []


__all__ = ["SentimentRecord", "OpinionProfile"]
