"""
/api/v1/subagents — SubagentManager 的控制平面 API

提供三类能力：
  1. 查询（GET）：列出某 report 的所有子智能体任务及其状态
  2. Steer（POST）：向运行中的 subagent 注入 mid-flight 修正指令
  3. Cancel（DELETE）：取消一个正在运行的子智能体任务

这些端点将"发射后不管（Fire-and-Forget）"升级为
"发射并控制（Fire-and-Steer）"，是 Supervisor 干预能力的 API 投影。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import AuthContext, get_auth_context
from app.services.subagent_manager import SubagentManager

router = APIRouter(prefix="/subagents", tags=["subagents"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SteerRequest(BaseModel):
    instruction: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="注入到运行中 subagent 的修正指令（中文优先）",
    )


class SubagentStatusResponse(BaseModel):
    task_id: str
    employee_id: str
    description: str
    report_id: int
    phase: str
    section_id: Optional[str]
    status: str
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    elapsed_ms: Optional[float]
    error: Optional[str]
    has_result: bool


class ReportSubagentsSummary(BaseModel):
    report_id: int
    total: int
    running: int
    done: int
    failed: int
    cancelled: int
    tasks: List[SubagentStatusResponse]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/reports/{report_id}", response_model=ReportSubagentsSummary)
async def list_subagents_for_report(
    report_id: int,
    auth: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """列出某 report 下所有子智能体任务的实时状态。

    这是 Supervisor 控制台的后端数据源：展示哪些 employee 正在运行、
    哪些已完成、哪些失败，以及每个任务的耗时。
    """
    manager = SubagentManager.get()
    summary = manager.summary_for_report(report_id)
    return {"report_id": report_id, **summary}


@router.get("/{task_id}", response_model=SubagentStatusResponse)
async def get_subagent_status(
    task_id: str,
    auth: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """查询单个 subagent 任务的详细状态。"""
    manager = SubagentManager.get()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task.to_dict()


@router.post("/{task_id}/steer")
async def steer_subagent(
    task_id: str,
    body: SteerRequest,
    auth: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """向正在运行的 subagent 注入 mid-flight 修正指令。

    实现 Fire-and-Steer 架构的关键 API：
    - Supervisor 或用户发出 steer 请求
    - SubagentManager 将指令推入目标 subagent 的 steering_queue
    - Employee 在开始写作前检查队列，将指令附加到 prompt 中

    典型场景：
    - 用户发现 synthesis 阶段某章节方向偏了，立刻 steer 纠正
    - Supervisor 在 Phase 2 数据阶段发现缺少某维度，steer 增加分析维度
    """
    manager = SubagentManager.get()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task.status in ("done", "cancelled", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot steer task in status '{task.status}'. Task has already finished.",
        )

    ok = manager.steer(task_id, body.instruction)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail="Steer failed: task may not be running or steering queue is full.",
        )

    return {
        "task_id": task_id,
        "status": "steered",
        "instruction_preview": body.instruction[:100],
        "task_status": task.status,
    }


@router.delete("/{task_id}")
async def cancel_subagent(
    task_id: str,
    auth: AuthContext = Depends(get_auth_context),
) -> Dict[str, Any]:
    """取消一个正在运行的 subagent 任务。

    适用场景：用户发现某个 employee 的方向完全错误，
    不想等它完成再重做，直接取消后由 Supervisor 重新派遣。
    """
    manager = SubagentManager.get()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    ok = manager.cancel(task_id)
    return {
        "task_id": task_id,
        "cancelled": ok,
        "task_status": task.status,
    }
