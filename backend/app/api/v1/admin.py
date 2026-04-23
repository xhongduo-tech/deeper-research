import json
from datetime import datetime
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User, UserRole
from app.models.agent_config import AgentConfig
from app.models.system_config import SystemConfig
from app.models.report import Report, ReportStatus
from app.api.v1.auth import require_admin, get_password_hash
from app.config import settings

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Schemas ---
class AgentConfigCreate(BaseModel):
    employee_id: str
    model_profile_id: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    enabled: bool = True
    custom_params: Optional[dict] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class AgentConfigResponse(BaseModel):
    id: int
    employee_id: str
    model_profile_id: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    enabled: bool = True
    custom_params: Optional[dict] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None

    class Config:
        from_attributes = True


class LlmProfile(BaseModel):
    id: str
    name: str
    base_url: str
    model: str
    api_key: str = ""
    description: str = ""


class SystemConfigFlat(BaseModel):
    enable_external_search: Optional[bool] = None
    enable_browser: Optional[bool] = None
    default_llm_base_url: Optional[str] = None
    default_llm_model: Optional[str] = None
    default_llm_api_key: Optional[str] = None
    default_llm_profile_id: Optional[str] = None
    llm_profiles: list[LlmProfile] = Field(default_factory=list)
    embedding_base_url: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_api_key: Optional[str] = None
    vector_store_enabled: Optional[bool] = None
    kb_chunk_size: Optional[int] = None
    kb_top_k: Optional[int] = None
    sandbox_timeout: Optional[int] = None
    max_workers: Optional[int] = None


class ApplyDefaultConfig(BaseModel):
    model_profile_id: Optional[str] = None


class AdminUserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"


class AdminUserResponse(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


def _normalize_agent_payload(config: AgentConfigCreate) -> dict:
    payload = config.model_dump()
    custom_params = dict(payload.get("custom_params") or {})
    model_profile_id = payload.pop("model_profile_id", None)
    if model_profile_id:
        custom_params["model_profile_id"] = model_profile_id
        # Once employees are profile-driven, keep direct connection fields empty
        # so runtime always resolves from the system-managed model pool.
        payload["llm_base_url"] = None
        payload["llm_model"] = None
        payload["llm_api_key"] = None
    if custom_params:
        payload["custom_params"] = custom_params
    return payload


def _serialize_agent_config(config: AgentConfig) -> dict:
    payload = AgentConfigResponse.model_validate(config).model_dump()
    payload["model_profile_id"] = (config.custom_params or {}).get("model_profile_id")
    return payload


# =========================================================
# Agent Config Endpoints
# =========================================================

@router.get("/agent-configs", response_model=List[AgentConfigResponse])
async def list_agent_configs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List all per-employee LLM configurations."""
    result = await db.execute(select(AgentConfig).order_by(AgentConfig.employee_id))
    return [_serialize_agent_config(cfg) for cfg in result.scalars().all()]


@router.post("/agent-configs", response_model=AgentConfigResponse)
async def create_agent_config(
    config: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = await db.execute(
        select(AgentConfig).where(AgentConfig.employee_id == config.employee_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Config for this employee already exists. Use PUT to update.",
        )
    new_config = AgentConfig(**_normalize_agent_payload(config))
    db.add(new_config)
    await db.flush()
    await db.refresh(new_config)
    return _serialize_agent_config(new_config)


@router.put("/agent-configs/{config_id}", response_model=AgentConfigResponse)
async def update_agent_config(
    config_id: int,
    config: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == config_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Agent config not found")

    for key, value in _normalize_agent_payload(config).items():
        setattr(existing, key, value)
    existing.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(existing)
    return _serialize_agent_config(existing)


@router.delete("/agent-configs/{config_id}")
async def delete_agent_config(
    config_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AgentConfig).where(AgentConfig.id == config_id))
    existing = result.scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404, detail="Agent config not found")
    await db.delete(existing)
    return {"message": "Deleted"}


@router.post("/agent-configs/apply-default")
async def apply_default_config(
    default: ApplyDefaultConfig,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Apply the system default model profile to employees without custom config."""
    from app.agents.employees.registry import EMPLOYEES
    from app.services.config_service import ConfigService

    system_config = await ConfigService(db).get_flat_config()
    model_profile_id = default.model_profile_id or system_config.get("default_llm_profile_id")
    if not model_profile_id:
        raise HTTPException(status_code=400, detail="No default model profile configured")

    applied = 0
    for emp in EMPLOYEES:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.employee_id == emp["id"])
        )
        if not result.scalar_one_or_none():
            new_config = AgentConfig(
                employee_id=emp["id"],
                custom_params={"model_profile_id": model_profile_id},
                enabled=True,
            )
            db.add(new_config)
            applied += 1
    return {"applied": applied}


# =========================================================
# System Config Endpoints
# =========================================================

@router.get("/system-config", response_model=SystemConfigFlat)
async def get_system_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return system config as a flat object."""
    from app.services.config_service import ConfigService
    return await ConfigService(db).get_flat_config()


@router.put("/system-config", response_model=SystemConfigFlat)
async def update_system_config(
    update: SystemConfigFlat,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update system config using flat object format."""
    llm_profiles = [profile.model_dump() for profile in (update.llm_profiles or [])]
    default_profile_id = update.default_llm_profile_id
    if llm_profiles and not default_profile_id:
        default_profile_id = llm_profiles[0]["id"]

    selected_default = next(
        (profile for profile in llm_profiles if profile["id"] == default_profile_id),
        llm_profiles[0] if llm_profiles else None,
    )

    mapping = {
        "enable_external_search": update.enable_external_search,
        "enable_browser": update.enable_browser,
        "default_llm_base_url": selected_default["base_url"] if selected_default else update.default_llm_base_url,
        "default_llm_model": selected_default["model"] if selected_default else update.default_llm_model,
        "default_llm_api_key": selected_default["api_key"] if selected_default else update.default_llm_api_key,
        "default_llm_profile_id": default_profile_id,
        "llm_profiles": llm_profiles,
        "embedding_base_url": update.embedding_base_url,
        "embedding_model": update.embedding_model,
        "embedding_api_key": update.embedding_api_key,
        "vector_store_enabled": update.vector_store_enabled,
        "kb_chunk_size": update.kb_chunk_size,
        "kb_top_k": update.kb_top_k,
        "sandbox_timeout": update.sandbox_timeout,
        "max_workers": update.max_workers,
    }

    for key, value in mapping.items():
        if value is None:
            continue
        str_value = value if isinstance(value, str) else (
            str(value) if not isinstance(value, (list, dict)) else json.dumps(value, ensure_ascii=False)
        )
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = str_value
            existing.updated_at = datetime.utcnow()
        else:
            db.add(SystemConfig(key=key, value=str_value))

    await db.flush()

    from app.services.config_service import ConfigService
    return await ConfigService(db).get_flat_config()


# =========================================================
# Admin Report Monitor
# =========================================================

@router.get("/reports")
async def admin_list_reports(
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Paginated list of all reports across all users."""
    query = select(Report).order_by(Report.created_at.desc())
    if status_filter:
        query = query.where(Report.status == status_filter)

    count_q = select(func.count(Report.id))
    if status_filter:
        count_q = count_q.where(Report.status == status_filter)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    result = await db.execute(query.offset((page - 1) * page_size).limit(page_size))
    reports = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "title": r.title,
                "brief": r.brief,
                "report_type": r.report_type,
                "status": r.status,
                "phase": r.phase,
                "progress": r.progress,
                "user_id": r.user_id,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/reports/{report_id}")
async def admin_delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Report).where(Report.id == report_id))
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    await db.delete(report)
    return {"message": "Report deleted"}


@router.get("/stats")
async def get_system_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return system-level statistics."""
    total_reports = await db.execute(select(func.count(Report.id)))
    running_reports = await db.execute(
        select(func.count(Report.id)).where(
            Report.status.in_([
                ReportStatus.intake.value,
                ReportStatus.scoping.value,
                ReportStatus.producing.value,
                ReportStatus.reviewing.value,
            ])
        )
    )
    completed_reports = await db.execute(
        select(func.count(Report.id)).where(Report.status == ReportStatus.delivered.value)
    )
    failed_reports = await db.execute(
        select(func.count(Report.id)).where(Report.status == ReportStatus.failed.value)
    )
    total_users = await db.execute(select(func.count(User.id)))

    return {
        "total_reports": total_reports.scalar() or 0,
        "running_reports": running_reports.scalar() or 0,
        "completed_reports": completed_reports.scalar() or 0,
        "failed_reports": failed_reports.scalar() or 0,
        "total_users": total_users.scalar() or 0,
    }


# =========================================================
# LLM Connection Test
# =========================================================

class LlmTestRequest(BaseModel):
    base_url: str
    model: str
    api_key: str = ""
    endpoint_type: str = "chat"


@router.post("/test-llm")
async def test_llm_connection(
    req: LlmTestRequest,
    _: User = Depends(require_admin),
):
    """Test connectivity to an LLM endpoint by sending a minimal chat completion."""
    import time
    import httpx

    endpoint = "/embeddings" if req.endpoint_type == "embedding" else "/chat/completions"
    url = req.base_url.rstrip("/") + endpoint
    headers = {"Content-Type": "application/json"}
    if req.api_key:
        headers["Authorization"] = f"Bearer {req.api_key}"

    if req.endpoint_type == "embedding":
        payload = {"model": req.model, "input": "connection test"}
    else:
        payload = {
            "model": req.model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 5,
        }

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.post(url, json=payload, headers=headers)
        latency_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            return {"success": True, "message": "连接成功", "latency_ms": latency_ms}
        else:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            return {"success": False, "message": f"HTTP {resp.status_code}: {detail}", "latency_ms": latency_ms}
    except httpx.ConnectError:
        return {"success": False, "message": "无法连接到服务器，请检查地址"}
    except httpx.TimeoutException:
        return {"success": False, "message": "连接超时（15s），请检查网络或服务状态"}
    except Exception as e:
        return {"success": False, "message": str(e)}


# =========================================================
# Admin User Management
# =========================================================

@router.post("/users", response_model=AdminUserResponse)
async def create_user(
    user_data: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")

    if user_data.role not in [r.value for r in UserRole]:
        raise HTTPException(status_code=400, detail="Invalid role")

    new_user = User(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    return new_user


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.put("/users/{user_id}/toggle-active", response_model=AdminUserResponse)
async def toggle_user_active(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = not user.is_active
    await db.flush()
    await db.refresh(user)
    return user
