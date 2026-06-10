from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════
# Requests
# ═══════════════════════════════════════════════════════════

class ReportCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    brief: str = Field(..., min_length=3, max_length=10000)
    report_type: str = "经营分析"
    output_format: str = "word"
    skip_clarify: bool = False
    strict_facts: bool = True
    uploaded_files: List[int] = Field(default_factory=list)
    kb_ids: List[int] = Field(default_factory=list)
    include_system_kb: bool = False
    skills: List[str] = Field(default_factory=list)
    model_id: Optional[str] = None
    effort: str = "low"
    project_id: Optional[int] = None


class ClarificationAnswer(BaseModel):
    answers: List[dict]  # [{"id": 1, "answer": "..."}]


class ReportOptions(BaseModel):
    template_style: Optional[str] = None
    page_count: Optional[str] = None
    layout: Optional[str] = None
    tone: Optional[str] = None


# ═══════════════════════════════════════════════════════════
# Sub-models
# ═══════════════════════════════════════════════════════════

class SourceResponse(BaseModel):
    url: str = ""
    title: str = ""
    credibility_score: float = Field(0.5, ge=0.0, le=1.0)

    model_config = {"from_attributes": True}


class FindingResponse(BaseModel):
    claim: str
    evidence: str
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    sources: List[SourceResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SubTaskResponse(BaseModel):
    id: str
    query: str
    agent_type: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    progress_pct: int = 0

    model_config = {"from_attributes": True}


class ClarificationResponse(BaseModel):
    id: int
    question: str
    default_answer: Optional[str] = None
    status: str
    priority: Optional[str] = None

    model_config = {"from_attributes": True}


class TimelineEventResponse(BaseModel):
    id: int
    event_type: str
    label: str
    payload: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class VerificationCheckResponse(BaseModel):
    criterion: str
    passed: bool
    detail: str
    sources_count: int = 0

    model_config = {"from_attributes": True}


class VerificationResultResponse(BaseModel):
    sub_task_id: str = ""
    passed: bool
    overall_confidence: float = 0.5
    checks: List[VerificationCheckResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════
# Main Responses
# ═══════════════════════════════════════════════════════════

class ReportProgress(BaseModel):
    report_id: int
    stage: Literal[
        "planning", "clarifying", "researching", "writing",
        "reviewing", "completed", "error",
    ]
    progress_pct: int = Field(0, ge=0, le=100)
    current_task: str = ""
    sub_tasks: List[SubTaskResponse] = Field(default_factory=list)
    messages: List[dict] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: int
    title: str
    brief: str
    report_type: str
    output_format: str
    status: str
    progress: float
    phase: str
    section_outline: Optional[dict] = None
    output_index: Optional[dict] = None
    final_file_name: Optional[str] = None
    final_file_path: Optional[str] = None
    error_message: Optional[str] = None
    clarifications: List[ClarificationResponse] = Field(default_factory=list)
    timeline: List[TimelineEventResponse] = Field(default_factory=list)
    findings: List[FindingResponse] = Field(default_factory=list)
    verifications: List[VerificationResultResponse] = Field(default_factory=list)
    project_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReportListResponse(BaseModel):
    id: int
    title: str
    report_type: str
    status: str
    progress: float
    phase: str
    project_id: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
