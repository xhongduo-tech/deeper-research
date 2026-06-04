"""OfficialDataSource — SQLAlchemy model for the official knowledge-source registry."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class OfficialDataSource(Base):
    __tablename__ = "official_datasources"

    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)   # e.g. "arxiv"
    name = Column(String(200), nullable=False)               # display name
    description = Column(Text, default="")
    category = Column(String(80), nullable=False)            # 金融数据/学术研究/…
    domain_tags = Column(Text, default="[]")                 # JSON list of strings
    is_active = Column(Boolean, default=True)
    source_type = Column(String(40), default="builtin")      # api/rss/web/builtin
    icon_color = Column(String(20), default="#6366f1")
    icon_bg = Column(String(20), default="#eef2ff")
    api_config = Column(Text, default="{}")                  # JSON config
    sample_queries = Column(Text, default="[]")              # JSON list
    coverage = Column(String(100), default="2020-至今")
    doc_count = Column(Integer, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Offline / API-key capability fields ─────────────────────────────────
    requires_api_key = Column(Boolean, default=False)   # needs external API key to function
    api_key_name = Column(String(100), default="")       # e.g. "TONGHUASHUN_API_KEY"
    api_key_value = Column(Text, default="")             # stored value (admin sets this)
    offline_available = Column(Boolean, default=False)   # has pre-loaded offline data
    offline_doc_count = Column(Integer, default=0)       # how many offline chunks loaded
