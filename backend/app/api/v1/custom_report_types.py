"""
/api/v1/custom-report-types — user-defined report templates.

Flow:
  POST   ""                       create a draft (auto-calls LLM for
                                  improvement); returns the draft
  GET    ""                       list own + public types
  GET    "{id}"                   fetch a single type
  POST   "{id}/confirm"           confirm the draft → active
  POST   "{id}/re-improve"        re-run LLM on the original description
  DELETE "{id}"                   delete

Types are referenced by callers elsewhere as ``report_type = "custom:<id>"``.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AuthContext, get_auth_context
from app.database import get_db
from app.services.custom_report_type_service import (
    CustomReportTypeService,
    serialize,
)

router = APIRouter(prefix="/custom-report-types", tags=["custom-report-types"])


class CreateBody(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=4000)
    visibility: str = "private"  # private | public


class SectionItem(BaseModel):
    id: str
    title: str
    kind: str = "narrative"


class ConfirmBody(BaseModel):
    label: Optional[str] = None
    improved_description: Optional[str] = None
    typical_output: Optional[str] = None
    section_skeleton: Optional[List[SectionItem]] = None
    default_team: Optional[List[str]] = None
    visibility: Optional[str] = None


@router.post("", status_code=201)
async def create_type(
    body: CreateBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    rt = await CustomReportTypeService.create_and_improve(
        db,
        user_id=ctx.user.id,
        label=body.label,
        description=body.description,
        visibility=body.visibility,
    )
    await db.commit()
    return serialize(rt)


@router.get("")
async def list_types(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    items = await CustomReportTypeService.list_for_user(db, ctx.user.id)
    return {"items": [serialize(rt) for rt in items]}


@router.get("/{raw_id}")
async def get_type(
    raw_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    rt = await CustomReportTypeService.get(db, raw_id)
    if not rt:
        raise HTTPException(404, "Custom report type not found")
    if rt.visibility != "public" and rt.user_id != ctx.user.id:
        raise HTTPException(403, "无权查看该自定义报告类型")
    return serialize(rt)


@router.post("/{raw_id}/confirm")
async def confirm_type(
    raw_id: int,
    body: ConfirmBody,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    rt = await CustomReportTypeService.get(db, raw_id)
    if not rt:
        raise HTTPException(404, "Custom report type not found")
    if rt.user_id != ctx.user.id:
        raise HTTPException(403, "仅创建者可确认该模板")
    await CustomReportTypeService.confirm(
        db, rt,
        label=body.label,
        improved_description=body.improved_description,
        typical_output=body.typical_output,
        section_skeleton=(
            [s.model_dump() for s in body.section_skeleton]
            if body.section_skeleton is not None else None
        ),
        default_team=body.default_team,
        visibility=body.visibility,
    )
    await db.commit()
    return serialize(rt)


@router.post("/{raw_id}/re-improve")
async def re_improve(
    raw_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    rt = await CustomReportTypeService.get(db, raw_id)
    if not rt:
        raise HTTPException(404, "Custom report type not found")
    if rt.user_id != ctx.user.id:
        raise HTTPException(403, "仅创建者可触发重新规划")
    improved = await CustomReportTypeService._improve_with_llm(
        rt.label, rt.description,
    )
    if improved:
        if improved.get("improved_description"):
            rt.improved_description = improved["improved_description"]
        if improved.get("typical_output"):
            rt.typical_output = improved["typical_output"]
        if improved.get("section_skeleton"):
            rt.section_skeleton = improved["section_skeleton"]
        if improved.get("default_team"):
            rt.default_team = improved["default_team"]
        await db.flush()
        await db.commit()
    return serialize(rt)


@router.delete("/{raw_id}")
async def delete_type(
    raw_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, str]:
    rt = await CustomReportTypeService.get(db, raw_id)
    if not rt:
        raise HTTPException(404, "Custom report type not found")
    if rt.user_id != ctx.user.id:
        raise HTTPException(403, "仅创建者可删除该模板")
    await CustomReportTypeService.delete(db, rt)
    await db.commit()
    return {"message": "deleted"}
