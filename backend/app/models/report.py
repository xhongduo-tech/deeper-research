"""
Report and related models — the core domain entities of the v2 system.

Naming note: the previous `Task` table was retired entirely (A2 strategy).
Nothing in the v2 codebase references `tasks`.

Tables defined here:
  - reports                 (the unit of production)
  - messages                (the Supervisor Collaboration Room feed)
  - clarifications          (Chief's questions to the user)
  - timeline_events         (phase transitions, team changes, etc.)
  - evidence                (extracted chunks tied back to uploaded files)
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReportStatus(str, enum.Enum):
    """Lifecycle of a report, driven by the Supervisor state machine."""
    draft = "draft"                 # Created, waiting for Chief's first pass
    intake = "intake"               # Chief is scoping + asking clarifications
    scoping = "scoping"             # Chief has the team plan, awaiting go-ahead
    producing = "producing"         # Employees are generating sections
    reviewing = "reviewing"         # QA + Compliance checks
    delivered = "delivered"         # Final Word is ready
    failed = "failed"
    cancelled = "cancelled"


class ReportType(str, enum.Enum):
    """The 5 built-in report structures. Kept as strings for forward compat."""
    ops_review = "ops_review"
    internal_research = "internal_research"
    risk_assessment = "risk_assessment"
    regulatory_filing = "regulatory_filing"
    training_material = "training_material"


class MessageRole(str, enum.Enum):
    supervisor_say = "supervisor_say"
    supervisor_ask = "supervisor_ask"
    team_change = "team_change"
    employee_note = "employee_note"
    user_reply = "user_reply"
    user_interject = "user_interject"
    phase_transition = "phase_transition"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    api_key_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("api_keys.id"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    # Stored as a free-form string so custom report types (e.g.
    # ``custom:42``) can coexist with the 5 built-in values listed in
    # ``ReportType``. The API layer validates that the value resolves to a
    # real type.
    report_type: Mapped[str] = mapped_column(
        String(60),
        default=ReportType.internal_research.value,
        nullable=False,
        index=True,
    )
    depth: Mapped[str] = mapped_column(String(20), default="standard", nullable=False)

    status: Mapped[str] = mapped_column(
        SAEnum(ReportStatus, values_callable=lambda x: [e.value for e in x]),
        default=ReportStatus.draft.value,
        nullable=False,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    phase: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)

    # JSON blobs: scoping_plan, team_roster, section_outline, output_index
    scoping_plan: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    team_roster: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    section_outline: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    output_index: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Optional template file chosen by the user at creation time.
    # References uploaded_files.id where is_template=True (or a builtin id).
    template_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # Delivered artifact
    final_file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    final_file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Phase 4 audit: full execution trace (plan steps, sandbox code, QA flags…)
    trace_log: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Phase 2: accumulated data_context (key metrics verified by sandbox)
    data_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Report id={self.id} type={self.report_type} status={self.status}>"


# ---------------------------------------------------------------------------
# Message — a single entry in the Supervisor Collaboration Room
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[str] = mapped_column(
        SAEnum(MessageRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )
    # For employee_note / team_change, who the message is "from".
    author_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} report={self.report_id} role={self.role}>"


# ---------------------------------------------------------------------------
# Clarification — structured Q&A items Chief asks the user
# ---------------------------------------------------------------------------

class Clarification(Base):
    __tablename__ = "clarifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    question: Mapped[str] = mapped_column(Text, nullable=False)
    default_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "pending" | "answered" | "defaulted" | "skipped"
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    # "high" | "medium" | "low" — set by LLM scoping plan
    priority: Mapped[Optional[str]] = mapped_column(String(10), default="medium", nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# TimelineEvent — coarser-grained lifecycle pins than messages
# ---------------------------------------------------------------------------

class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "phase_enter" | "team_assign" | "section_done" | "qa_verdict" | "delivered"
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# Evidence — citable chunks extracted from uploaded files
# ---------------------------------------------------------------------------

class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("uploaded_files.id"), nullable=True, index=True
    )

    source_name: Mapped[str] = mapped_column(String(500), nullable=False)
    locator: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # e.g. "p.12" or "sheet:Q3!A1:D20"
    snippet: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), default="text", nullable=False)  # text|table|image
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
