"""
ApiKey model — user self-service API keys with automatic approval.

Per DESIGN.md §5:
  - Users generate their own keys from the Developer page (auto-approved)
  - Admin can view all keys, suspend, and adjust quotas

Storage: we store SHA-256 of the raw key ("prefix_rest").
The prefix (first 8 chars) is kept in plaintext so the UI can show
"dr_ab12••••" without leaking the secret.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # First ~8 chars of the raw key (plaintext, safe to display)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # SHA-256 of the full raw key
    hashed_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    # Full raw key, retained so the user can view it again from the Developer
    # page. The platform is an internal/offline deployment, so we trade a bit
    # of theoretical exposure for far better UX. Owner-only reveal endpoint.
    raw_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # "active" | "suspended" | "revoked"
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)

    # Soft quotas (None = no limit)
    daily_request_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    monthly_token_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Usage stats
    total_requests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} user={self.user_id} prefix={self.prefix} status={self.status}>"
