from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str


class ChatRequest(BaseModel):
    prompt: str
    model_id: str | None = None
    effort: str = "low"
    conversation_id: int | None = None
    uploaded_files: list[int] = []
    kb_ids: list[int] = []
    include_system_kb: bool = False
    project_id: int | None = None


class MessageResponse(BaseModel):
    id: int
    report_id: int
    role: str
    author_id: str | None = None
    author_name: str | None = None
    content: str
    meta: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RagSource(BaseModel):
    source: str
    snippet: str


class ChatResponse(BaseModel):
    report_id: int
    answer: str
    messages: list[MessageResponse]
    sources: list[RagSource] = []
    intent_domain: str | None = None  # ontology domain detected for this query
