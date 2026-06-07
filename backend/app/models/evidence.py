from datetime import datetime
from sqlalchemy import String, Integer, JSON, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("uploaded_files.id"), index=True, nullable=True)
    source_name: Mapped[str] = mapped_column(String(500))
    locator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snippet: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(40))
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
