from datetime import datetime
from pydantic import BaseModel


class AgentResponse(BaseModel):
    id: int
    employee_id: str
    name: str = ""
    role: str = ""
    tag: str = ""
    llm_model: str | None = None
    enabled: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]
    total: int
