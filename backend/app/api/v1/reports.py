"""
/api/v1/reports — report lifecycle API.

All routes accept both:
  - session JWT cookie/bearer (UI users)
  - X-API-Key / Bearer dr_... (developer API callers)

Layered on top of:
  - ReportService  (data)
  - SupervisorService  (orchestration)
  - event_bus  (SSE fan-out)
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import AuthContext, get_auth_context
from app.database import get_db
from app.models.report import Clarification, Report, ReportStatus
from app.services.event_bus import event_bus
from app.services.report_service import (
    ClarificationService,
    MessageService,
    ReportService,
    TimelineService,
    serialize_clarification,
    serialize_evidence,
    serialize_message,
    serialize_report,
    serialize_timeline,
)
from app.services.custom_report_type_service import (
    CustomReportTypeService,
    serialize as serialize_custom_rt,
)
from app.services.report_types import (
    get_report_type,
    list_report_types,
    resolve_report_type,
)
from app.services.supervisor_service import SupervisorService


router = APIRouter(prefix="/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ReportCreate(BaseModel):
    title: Optional[str] = None
    brief: str = Field(..., min_length=1)
    report_type: str = "internal_research"
    depth: str = "standard"
    file_ids: List[int] = Field(default_factory=list)
    # Optional template file id (is_template=True in uploaded_files)
    template_file_id: Optional[int] = None
    # Skip the Chief's back-and-forth clarifications. When True, Chief still
    # plans the team + outline but will answer its own questions using the
    # suggested defaults. Useful for API / automation scenarios.
    skip_clarifications: bool = False
    # Immediately transition the report into the producing phase after
    # creation, equivalent to calling POST /reports/{id}/start.
    auto_start: bool = False


class ReportReply(BaseModel):
    content: str = Field(..., min_length=1)


class ClarificationAnswer(BaseModel):
    answer: Optional[str] = None
    use_default: bool = False


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("")
async def list_reports(
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    status_list = [s for s in (status_filter.split(",") if status_filter else []) if s]
    reports = await ReportService.list_for_user(
        db, ctx.user.id,
        status_filter=status_list or None,
        limit=limit, offset=offset,
    )
    return {"items": [serialize_report(r) for r in reports]}


@router.post("", status_code=201)
async def create_report(
    body: ReportCreate,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    resolved = await resolve_report_type(db, body.report_type)
    if not resolved:
        raise HTTPException(400, f"Unknown report_type: {body.report_type}")

    # For custom types enforce visibility: only owner or public types allowed.
    # 'auto' is a frontend sentinel — resolve to 'internal_research' for DB storage
    # but pass the original value to SupervisorService so Chief knows to auto-detect.
    effective_type = body.report_type if body.report_type != "auto" else "internal_research"

    raw_id = CustomReportTypeService.parse_report_type_id(effective_type)
    if raw_id is not None:
        custom = await CustomReportTypeService.get(db, raw_id)
        if not custom or custom.status != "active":
            raise HTTPException(400, "自定义报告类型不可用或未激活")
        if custom.visibility != "public" and custom.user_id != ctx.user.id:
            raise HTTPException(403, "无权使用该自定义报告类型")

    title = (body.title or body.brief[:40]).strip()
    report = await ReportService.create(
        db,
        user_id=ctx.user.id,
        title=title,
        brief=body.brief,
        report_type=effective_type,
        depth=body.depth,
        api_key_id=ctx.api_key.id if ctx.api_key else None,
        template_file_id=body.template_file_id,
    )
    if body.file_ids:
        await ReportService.attach_files(
            db, report, file_ids=body.file_ids, user_id=ctx.user.id
        )
    # Chief's opening moves (may reach out to the LLM for tailored scoping).
    await SupervisorService.on_report_created(
        db, report, skip_clarifications=body.skip_clarifications,
    )
    await db.commit()

    # Optionally skip the "await user confirmation" step entirely.
    if body.auto_start:
        await ReportService.update_status(
            db, report,
            status=ReportStatus.scoping.value,
            phase="scoping",
        )
        await db.commit()
        await SupervisorService.start_production(report.id)

    return serialize_report(report)


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")

    messages = await MessageService.list_for_report(db, report_id)
    clarifications = await ClarificationService.list_for_report(db, report_id)
    timeline = await TimelineService.list_for_report(db, report_id)

    return {
        **serialize_report(report),
        "messages": [serialize_message(m) for m in messages],
        "clarifications": [serialize_clarification(c) for c in clarifications],
        "timeline": [serialize_timeline(t) for t in timeline],
    }


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
):
    """Stream the final .docx rendered at delivery time."""
    import os
    from urllib.parse import quote
    from fastapi.responses import FileResponse

    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    if not report.final_file_path or not os.path.exists(report.final_file_path):
        raise HTTPException(409, "报告尚未交付或文件已丢失")
    filename = report.final_file_name or f"report-{report_id}.docx"
    # RFC 5987 for non-ASCII filenames
    ascii_fallback = "report.docx"
    headers = {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_fallback}\"; "
            f"filename*=UTF-8''{quote(filename)}"
        )
    }
    return FileResponse(
        report.final_file_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers=headers,
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, str]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    await ReportService.delete(db, report)
    return {"message": "deleted"}


# ---------------------------------------------------------------------------
# Conversation — Supervisor Collaboration Room
# ---------------------------------------------------------------------------

@router.post("/{report_id}/reply")
async def post_reply(
    report_id: int,
    body: ReportReply,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, str]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    await SupervisorService.on_user_reply(db, report, body.content)
    await db.commit()
    return {"message": "accepted"}


@router.post("/{report_id}/interject")
async def post_interject(
    report_id: int,
    body: ReportReply,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, str]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    await SupervisorService.on_user_interject(db, report, body.content)
    await db.commit()
    return {"message": "accepted"}


# ---------------------------------------------------------------------------
# Clarifications
# ---------------------------------------------------------------------------

@router.post("/{report_id}/clarifications/{clar_id}/answer")
async def answer_clarification(
    report_id: int,
    clar_id: int,
    body: ClarificationAnswer,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")

    result = await db.execute(
        select(Clarification).where(
            Clarification.id == clar_id,
            Clarification.report_id == report_id,
        )
    )
    clar = result.scalar_one_or_none()
    if not clar:
        raise HTTPException(404, "Clarification not found")

    await ClarificationService.answer(
        db, clar, answer=body.answer, use_default=body.use_default
    )
    await db.commit()
    return serialize_clarification(clar)


# ---------------------------------------------------------------------------
# Steer — mid-flight 指令注入（Fire-and-Steer 的用户入口）
# ---------------------------------------------------------------------------

class SteerSectionRequest(BaseModel):
    section_id: str = Field(..., description="目标章节 ID（来自 section_outline）")
    instruction: str = Field(
        ..., min_length=1, max_length=1000,
        description="注入到正在运行的 subagent 的修正指令",
    )


@router.post("/{report_id}/steer")
async def steer_report_section(
    report_id: int,
    body: SteerSectionRequest,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """向报告的某个正在生产的章节注入 mid-flight 修正指令。

    当 Phase 3 并行合成阶段正在运行时，用户可通过此端点
    实时修正某个 employee 的写作方向，无需等待整个 report 完成。

    实现逻辑：
    1. 先尝试找到对应 section 的 subagent task_id（via SubagentManager）
    2. 若任务仍在运行，向 steering_queue 注入指令
    3. 若任务已完成/未开始，将指令存入 ExecutionState.steering_instructions，
       供下次运行该 section（如 QA retry）时使用
    """
    from app.services.subagent_manager import SubagentManager

    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")

    manager = SubagentManager.get()
    # 找到对应 section 的运行中任务
    tasks = manager.list_for_report(report_id)
    target_task = next(
        (t for t in tasks if t.section_id == body.section_id
         and t.status in ("pending", "running", "steered")),
        None,
    )

    if target_task:
        ok = manager.steer(target_task.task_id, body.instruction)
        return {
            "steered": ok,
            "task_id": target_task.task_id,
            "task_status": target_task.status,
            "mode": "live_steer",
            "message": "指令已注入运行中的子智能体" if ok else "注入失败（队列已满）",
        }
    else:
        # 任务未启动或已完成，记录到 ExecutionState 供后续 retry 使用
        # ExecutionState 在内存中，通过 report_id 索引
        from app.services.supervisor_service import _get_active_state
        state = _get_active_state(report_id)
        if state:
            state.inject_steering(body.section_id, body.instruction)
            return {
                "steered": True,
                "task_id": None,
                "mode": "queued_steering",
                "message": "指令已排队，将在下次该章节执行时生效",
            }
        return {
            "steered": False,
            "task_id": None,
            "mode": "no_active_run",
            "message": "当前 report 没有活跃的生产任务，指令未能注入",
        }


# ---------------------------------------------------------------------------
# Lifecycle controls
# ---------------------------------------------------------------------------

@router.post("/{report_id}/start")
async def start_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status not in (
        ReportStatus.draft.value,
        ReportStatus.intake.value,
        ReportStatus.scoping.value,
    ):
        raise HTTPException(400, f"Cannot start report in status {report.status}")

    await ReportService.update_status(
        db, report, status=ReportStatus.scoping.value, phase="scoping"
    )
    await db.commit()
    await SupervisorService.start_production(report.id)
    return {"message": "started"}


@router.post("/{report_id}/cancel")
async def cancel_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")
    await ReportService.update_status(
        db, report, status=ReportStatus.cancelled.value, phase="cancelled"
    )
    await db.commit()
    return {"message": "cancelled"}


# ---------------------------------------------------------------------------
# SSE — live updates for the Supervisor Collaboration Room
# ---------------------------------------------------------------------------

@router.get("/{report_id}/events")
async def report_events(
    report_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
):
    # Auth-check + ownership
    report = await ReportService.get(db, report_id, user_id=ctx.user.id)
    if not report:
        raise HTTPException(404, "Report not found")

    async def event_source():
        # Send a snapshot of current state first so late subscribers are sane.
        yield _sse({
            "type": "status",
            "payload": {
                "status": report.status,
                "phase": report.phase,
                "progress": report.progress,
            },
        })

        queue = await event_bus.subscribe(report_id)
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield _sse(event)
                except asyncio.TimeoutError:
                    yield _sse({"type": "heartbeat"})
        finally:
            await event_bus.unsubscribe(report_id, queue)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(event: dict) -> bytes:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


# ---------------------------------------------------------------------------
# Report types sub-router (exposed at /api/v1/report-types via main include)
# ---------------------------------------------------------------------------

report_types_router = APIRouter(prefix="/report-types", tags=["report-types"])


@report_types_router.get("")
async def list_all_report_types(
    db: AsyncSession = Depends(get_db),
    ctx: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = list(list_report_types())
    # Append the user's custom types (own + public) that are active.
    customs = await CustomReportTypeService.list_for_user(db, ctx.user.id)
    for c in customs:
        if c.status != "active":
            continue
        items.append({
            "id": f"custom:{c.id}",
            "label": c.label,
            "label_en": "Custom",
            "description": c.improved_description or c.description,
            "typical_inputs": [],
            "typical_output": c.typical_output or "Word 报告",
            "default_team": list(c.default_team or []),
            "section_skeleton": list(c.section_skeleton or []),
            "is_custom": True,
            "visibility": c.visibility,
            "owner_is_me": c.user_id == ctx.user.id,
        })
    return {"items": items}
