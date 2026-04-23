"""
CustomReportType — user-defined report templates.

A user describes what kind of report they want (name + requirements),
the system uses the LLM to derive a proposed section skeleton and a
default employee roster. The user can then confirm or tweak; after
confirmation the entry goes `active` and can be used as a
`report_type` value elsewhere in the system with id `custom:<id>`.

`visibility` is either `private` (only the owner can use it) or
`public` (anyone in the tenant can use it).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomReportType(Base):
    __tablename__ = "custom_report_types"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(
        String(20), default="private", nullable=False, index=True
    )  # "private" | "public"

    # "draft" — LLM suggested, awaiting user confirmation
    # "active" — confirmed, usable as report_type
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False, index=True
    )

    # Proposed by the LLM; may be edited by the user before activation.
    section_skeleton: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    default_team: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    typical_output: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    improved_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CustomReportType id={self.id} label={self.label} status={self.status}>"
