from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.sqlite import JSON
from app.database import Base


class AgentConfig(Base):
    __tablename__ = "agent_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    employee_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    llm_base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    llm_api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    custom_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return f"<AgentConfig id={self.id} employee_id={self.employee_id} enabled={self.enabled}>"
