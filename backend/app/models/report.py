from datetime import datetime
from sqlalchemy import String, Integer, Float, JSON, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    api_key_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("api_keys.id"), index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    brief: Mapped[str] = mapped_column(Text)
    report_type: Mapped[str] = mapped_column(String(17), index=True)
    depth: Mapped[str] = mapped_column(String(20), default="standard")
    status: Mapped[str] = mapped_column(String(9), default="pending", index=True)  # pending, running, completed, failed
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    phase: Mapped[str] = mapped_column(String(40), default="初始化")
    scoping_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    team_roster: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    section_outline: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_index: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    final_file_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str] = mapped_column(String(20), default="word")
    template_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
