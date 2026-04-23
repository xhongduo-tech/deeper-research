"""
Escalation API — Expert Escalation 控制平面

提供三类操作：
  1. 手动触发专家升级（POST /escalation/reports/{id}/sections/{section_id}）
  2. 查询升级状态（GET /escalation/reports/{id}）
  3. 全局复杂度评分预览（POST /escalation/preview）

设计原则：
  - 升级动作最终由 runner.py 中的 EscalationService.decide() 决定
  - API 只负责传递 manual_override=True 标志，或返回评分供 UI 展示
  - 升级记录持久化在 SubagentTask.escalated 字段里
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.services.escalation_service import (
    EscalationService,
    EscalationReason,
    score_complexity,
)
from app.services.subagent_manager import SubagentManager
from app.services.supervisor_service import _get_active_state

router = APIRouter(prefix="/escalation", tags=["escalation"])


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class ManualEscalateRequest(BaseModel):
    section_id: str
    reason_note: Optional[str] = "用户手动触发专家介入"


class ComplexityPreviewRequest(BaseModel):
    task_instruction: str
    task_kind: str = "narrative"
    brief: str = ""
    evidence_count: int = 0
    doc_count: int = 0
    qa_retry_count: int = 0
    prior_error: Optional[str] = None


class EscalationRecord(BaseModel):
    task_id: str
    section_id: Optional[str]
    original_employee_id: str
    expert_employee_id: str
    reason: str
    phase: str
    elapsed_ms: Optional[float]


class ReportEscalationSummary(BaseModel):
    report_id: int
    total_tasks: int
    escalated_count: int
    escalations: List[EscalationRecord]


class ComplexityPreviewResponse(BaseModel):
    complexity_score: float
    would_escalate: bool
    threshold: float
    reason: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/reports/{report_id}/sections/{section_id}",
    summary="手动触发专家升级",
    description=(
        "对指定 section 发出手动升级信号。\n\n"
        "如果该 section 对应的 SubagentTask 仍在运行，则向其注入 steer 指令 "
        "提示 Supervisor 在下次重试时使用专家模式。\n"
        "如果 section 尚未运行（或已完成），则在 ExecutionState 中标记该 section "
        "需要专家处理，下次调度时生效。"
    ),
)
async def manual_escalate_section(
    report_id: int,
    section_id: str,
    body: ManualEscalateRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    # Verify report exists and is accessible
    from app.services.report_service import ReportService
    report = await ReportService.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    manager = SubagentManager.get()
    tasks = manager.list_for_report(report_id)

    # Find running task for this section
    running_task = next(
        (t for t in tasks
         if t.section_id == section_id and t.status in ("pending", "running", "steered")),
        None,
    )

    if running_task:
        # Inject escalation signal via steering — runner checks this on next loop
        escalation_signal = (
            f"[EXPERT_ESCALATE] {body.reason_note or '手动触发专家升级'}\n"
            f"请在本章节使用专家模式（expert tier）进行深度分析。"
        )
        ok = manager.steer(running_task.task_id, escalation_signal)
        return {
            "status": "escalation_signal_sent",
            "task_id": running_task.task_id,
            "section_id": section_id,
            "message": f"已向运行中的任务 {running_task.task_id} 发送专家升级信号",
        }

    # No running task — mark in ExecutionState for next dispatch
    state = _get_active_state(report_id)
    if state:
        # Store as a high-priority steering instruction that will trigger expert mode
        state.inject_steering(
            section_id,
            f"[EXPERT_ESCALATE] {body.reason_note or '手动触发专家升级'}",
        )
        return {
            "status": "escalation_queued",
            "section_id": section_id,
            "message": "报告生产流水线仍在运行，专家升级信号已排队，下次调度该 section 时生效",
        }

    return {
        "status": "no_active_run",
        "section_id": section_id,
        "message": "该报告当前没有活跃的生产流水线，无法注入升级信号",
    }


@router.get(
    "/reports/{report_id}",
    response_model=ReportEscalationSummary,
    summary="查询报告的专家升级记录",
)
async def get_report_escalations(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ReportEscalationSummary:
    from app.services.report_service import ReportService
    report = await ReportService.get_report(db, report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    manager = SubagentManager.get()
    all_tasks = manager.list_for_report(report_id)
    escalated_tasks = [t for t in all_tasks if t.escalated]

    records = [
        EscalationRecord(
            task_id=t.task_id,
            section_id=t.section_id,
            original_employee_id=t.original_employee_id or t.employee_id,
            expert_employee_id=t.employee_id,
            reason=t.escalation_reason,
            phase=t.phase,
            elapsed_ms=t.elapsed_ms(),
        )
        for t in escalated_tasks
    ]

    return ReportEscalationSummary(
        report_id=report_id,
        total_tasks=len(all_tasks),
        escalated_count=len(escalated_tasks),
        escalations=records,
    )


@router.post(
    "/preview",
    response_model=ComplexityPreviewResponse,
    summary="复杂度评分预览",
    description=(
        "输入任务参数，返回复杂度评分和是否会触发自动升级。\n"
        "可用于 UI 提示用户'此任务可能需要专家处理'。"
    ),
)
async def preview_complexity(
    body: ComplexityPreviewRequest,
    current_user=Depends(get_current_user),
) -> ComplexityPreviewResponse:
    from app.services.escalation_service import COMPLEXITY_THRESHOLD

    score = score_complexity(
        task_instruction=body.task_instruction,
        task_kind=body.task_kind,
        brief=body.brief,
        evidence_count=body.evidence_count,
        doc_count=body.doc_count,
        qa_retry_count=body.qa_retry_count,
        prior_error=body.prior_error,
    )

    would_escalate = score >= COMPLEXITY_THRESHOLD

    # Build reason text
    if not would_escalate:
        reason = f"复杂度评分 {score:.2f} 低于阈值 {COMPLEXITY_THRESHOLD}，无需升级"
    elif body.qa_retry_count >= 2:
        reason = f"QA 失败次数 ({body.qa_retry_count}) 超过阈值，强制升级"
    else:
        reason = f"复杂度评分 {score:.2f} 超过阈值 {COMPLEXITY_THRESHOLD}，自动升级"

    return ComplexityPreviewResponse(
        complexity_score=round(score, 3),
        would_escalate=would_escalate,
        threshold=COMPLEXITY_THRESHOLD,
        reason=reason,
    )
