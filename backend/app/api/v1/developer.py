"""
/api/v1/developer/api-keys — user self-service API key management.

Per DESIGN.md §5, approval is automatic. Any logged-in user can:
  - Create keys (returns raw key once)
  - List their own keys (masked)
  - Suspend / resume
  - Delete
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AuthContext, get_auth_context
from app.database import get_db
from app.services.api_key_service import ApiKeyService, serialize_api_key


router = APIRouter(prefix="/developer/api-keys", tags=["developer"])


class CreateKeyBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    daily_request_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None


class SetStatusBody(BaseModel):
    status: str  # active | suspended | revoked


class SetQuotaBody(BaseModel):
    daily_request_limit: Optional[int] = None
    monthly_token_limit: Optional[int] = None


@router.get("")
async def list_keys(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    # API keys endpoint is deliberately session-only — returning the list
    # via an API key would be confusing.
    if ctx.auth_method != "session":
        raise HTTPException(403, "API key management requires session login")
    keys = await ApiKeyService.list_for_user(db, ctx.user.id)
    return {"items": [serialize_api_key(k) for k in keys]}


@router.post("", status_code=201)
async def create_key(
    body: CreateKeyBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.auth_method != "session":
        raise HTTPException(403, "Must be logged in via UI to create keys")

    created = await ApiKeyService.create_for_user(
        db,
        user_id=ctx.user.id,
        name=body.name,
        daily_request_limit=body.daily_request_limit,
        monthly_token_limit=body.monthly_token_limit,
    )
    await db.commit()
    payload = serialize_api_key(created.api_key)
    payload["raw_key"] = created.raw_key
    return payload


@router.get("/{key_id}/reveal")
async def reveal_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """Return the full raw key for the owner. Session-only."""
    if ctx.auth_method != "session":
        raise HTTPException(403, "Must be logged in via UI")
    k = await ApiKeyService.get(db, key_id)
    if not k or k.user_id != ctx.user.id:
        raise HTTPException(404, "API key not found")
    if not k.raw_key:
        raise HTTPException(
            410,
            "该密钥是在旧版本系统中创建的，无法再次查看原文，请删除后重新创建。",
        )
    return {"id": k.id, "raw_key": k.raw_key}


@router.put("/{key_id}/status")
async def set_status(
    key_id: int,
    body: SetStatusBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.auth_method != "session":
        raise HTTPException(403, "Must be logged in via UI")
    k = await ApiKeyService.get(db, key_id)
    if not k or k.user_id != ctx.user.id:
        raise HTTPException(404, "API key not found")
    try:
        await ApiKeyService.set_status(db, k, body.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return serialize_api_key(k)


@router.put("/{key_id}/quota")
async def set_quota(
    key_id: int,
    body: SetQuotaBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.auth_method != "session":
        raise HTTPException(403, "Must be logged in via UI")
    k = await ApiKeyService.get(db, key_id)
    if not k or k.user_id != ctx.user.id:
        raise HTTPException(404, "API key not found")
    await ApiKeyService.update_quotas(
        db, k,
        daily_request_limit=body.daily_request_limit,
        monthly_token_limit=body.monthly_token_limit,
    )
    await db.commit()
    return serialize_api_key(k)


@router.delete("/{key_id}")
async def delete_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, str]:
    if ctx.auth_method != "session":
        raise HTTPException(403, "Must be logged in via UI")
    k = await ApiKeyService.get(db, key_id)
    if not k or k.user_id != ctx.user.id:
        raise HTTPException(404, "API key not found")
    await ApiKeyService.delete(db, k)
    await db.commit()
    return {"message": "deleted"}


# ---------------------------------------------------------------------------
# Admin-side — view/manage ALL keys
# ---------------------------------------------------------------------------

admin_router = APIRouter(prefix="/admin/api-keys", tags=["admin"])


@admin_router.get("")
async def admin_list_all_keys(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.user.role != "admin":
        raise HTTPException(403, "Admin only")
    keys = await ApiKeyService.list_all(db)
    return {"items": [serialize_api_key(k) for k in keys]}


@admin_router.put("/{key_id}/status")
async def admin_set_status(
    key_id: int,
    body: SetStatusBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.user.role != "admin":
        raise HTTPException(403, "Admin only")
    k = await ApiKeyService.get(db, key_id)
    if not k:
        raise HTTPException(404, "API key not found")
    try:
        await ApiKeyService.set_status(db, k, body.status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return serialize_api_key(k)


@admin_router.put("/{key_id}/quota")
async def admin_set_quota(
    key_id: int,
    body: SetQuotaBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    if ctx.user.role != "admin":
        raise HTTPException(403, "Admin only")
    k = await ApiKeyService.get(db, key_id)
    if not k:
        raise HTTPException(404, "API key not found")
    await ApiKeyService.update_quotas(
        db, k,
        daily_request_limit=body.daily_request_limit,
        monthly_token_limit=body.monthly_token_limit,
    )
    await db.commit()
    return serialize_api_key(k)
