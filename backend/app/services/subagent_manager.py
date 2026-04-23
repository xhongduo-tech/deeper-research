"""
SubagentManager — 异步子智能体任务注册与 Fire-and-Steer 控制中心

解决传统 Supervisor 的两个致命弱点：
  1. 同步阻塞（Deadlock）：Subagent 启动后立即返回 task_id，后台独立运行
  2. 协调损耗（Coordination Tax）：Supervisor 可并行调度多个子节点，中途下发
     新的 steering 指令修正执行路线，无需等待前一个子节点完成

架构模式：Fire-and-Steer（发射并控制）
  - launch(coro)  →  task_id (立即返回)
  - steer(task_id, instruction)  →  注入 mid-flight 指令到 steering_queue
  - cancel(task_id)  →  取消 asyncio.Task
  - collect(task_ids)  →  等待所有任务完成并汇总结果
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Coroutine, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SubagentTask — 单个异步任务的完整生命周期记录
# ---------------------------------------------------------------------------

@dataclass
class SubagentTask:
    task_id: str
    employee_id: str
    description: str
    report_id: int
    phase: str                   # "data" | "synthesis" | "qa" | "planning"
    section_id: Optional[str] = None

    status: str = "pending"      # pending | running | done | cancelled | failed | steered
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    result: Any = None
    error: Optional[str] = None

    # mid-flight steering: supervisor 可以向正在运行的任务推送指令
    steering_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=16))
    _asyncio_task: Optional[asyncio.Task] = field(default=None, repr=False)

    def elapsed_ms(self) -> Optional[float]:
        if self.started_at and self.finished_at:
            return round((self.finished_at - self.started_at) * 1000, 1)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "employee_id": self.employee_id,
            "description": self.description,
            "report_id": self.report_id,
            "phase": self.phase,
            "section_id": self.section_id,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "elapsed_ms": self.elapsed_ms(),
            "error": self.error,
            "has_result": self.result is not None,
        }


# ---------------------------------------------------------------------------
# SubagentManager — 进程级单例注册表
# ---------------------------------------------------------------------------

class SubagentManager:
    """
    进程级单例。管理所有 subagent 的生命周期。

    使用方式（在 SupervisorService 中）：

        manager = SubagentManager.get()

        # 并行发射多个 subagent（Phase 3 拓扑并行）
        task_ids = []
        for section in parallel_batch:
            tid = manager.launch(
                coro=EmployeeRunner.run_synthesis(...),
                employee_id=employee_id,
                description=section_title,
                report_id=report_id,
                phase="synthesis",
                section_id=section_id,
            )
            task_ids.append(tid)

        # 主管可以在此期间做其他工作，或向某个任务注入新指令
        manager.steer(task_ids[0], "请强调风险敞口部分")

        # 等待这一批完成，收集结果
        results = await manager.collect(task_ids)

    """

    _instance: Optional["SubagentManager"] = None

    @classmethod
    def get(cls) -> "SubagentManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        # task_id → SubagentTask
        self._registry: Dict[str, SubagentTask] = {}
        # 全局锁仅保护 registry 的增删，不阻塞任务执行
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # launch — 发射一个 subagent，立即返回 task_id
    # ------------------------------------------------------------------

    def launch(
        self,
        *,
        coro: Coroutine[Any, Any, Any],
        employee_id: str,
        description: str,
        report_id: int,
        phase: str,
        section_id: Optional[str] = None,
    ) -> str:
        """将协程包装成 asyncio.Task，注册到 registry，立即返回 task_id。

        调用方无需 await，可继续发射下一个 subagent（Fire-and-Forget 变成
        Fire-and-Steer：发射后 supervisor 仍持有 task_id 控制权）。
        """
        task_id = uuid.uuid4().hex[:16]
        subagent = SubagentTask(
            task_id=task_id,
            employee_id=employee_id,
            description=description,
            report_id=report_id,
            phase=phase,
            section_id=section_id,
        )
        self._registry[task_id] = subagent

        # 用 _wrap 包装真实协程，注入生命周期跟踪
        asyncio_task = asyncio.create_task(
            self._wrap(task_id, coro),
            name=f"subagent-{task_id}",
        )
        subagent._asyncio_task = asyncio_task
        logger.debug("SubagentManager.launch: %s (%s / %s)", task_id, employee_id, description[:50])
        return task_id

    async def _wrap(self, task_id: str, coro: Coroutine) -> Any:
        """生命周期包装器：running → done/failed，记录时间戳。"""
        sub = self._registry.get(task_id)
        if sub:
            sub.status = "running"
            sub.started_at = time.time()
        try:
            result = await coro
            if sub:
                sub.status = "done"
                sub.result = result
                sub.finished_at = time.time()
            return result
        except asyncio.CancelledError:
            if sub:
                sub.status = "cancelled"
                sub.finished_at = time.time()
            raise
        except Exception as exc:
            if sub:
                sub.status = "failed"
                sub.error = str(exc)[:500]
                sub.finished_at = time.time()
            logger.warning("SubagentTask %s failed: %s", task_id, exc)
            return None

    # ------------------------------------------------------------------
    # steer — mid-flight 注入指令
    # ------------------------------------------------------------------

    def steer(self, task_id: str, instruction: str) -> bool:
        """向正在运行的 subagent 注入修正指令（非阻塞）。

        Employee 的协程在开始写作前会检查 steering_queue；如果有指令，
        它会将指令附加到自己的 context 中，修正输出方向。

        Returns True if the task exists and is running, False otherwise.
        """
        sub = self._registry.get(task_id)
        if not sub or sub.status not in ("pending", "running"):
            return False
        try:
            sub.steering_queue.put_nowait(instruction)
            sub.status = "steered"
            logger.info("SubagentManager.steer: %s ← '%s'", task_id, instruction[:80])
            return True
        except asyncio.QueueFull:
            logger.warning("Steering queue full for task %s", task_id)
            return False

    # ------------------------------------------------------------------
    # cancel — 取消一个正在运行的任务
    # ------------------------------------------------------------------

    def cancel(self, task_id: str) -> bool:
        sub = self._registry.get(task_id)
        if not sub or not sub._asyncio_task:
            return False
        if sub._asyncio_task.done():
            return False
        sub._asyncio_task.cancel()
        sub.status = "cancelled"
        logger.info("SubagentManager.cancel: %s", task_id)
        return True

    # ------------------------------------------------------------------
    # collect — 等待一批 task 完成，返回 {task_id: result}
    # ------------------------------------------------------------------

    async def collect(
        self,
        task_ids: List[str],
        *,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """等待指定 task_ids 全部完成（或超时），返回结果字典。

        不抛出异常：单个任务失败时 result 为 None，error 已记录在 SubagentTask 上。
        """
        asyncio_tasks = []
        for tid in task_ids:
            sub = self._registry.get(tid)
            if sub and sub._asyncio_task and not sub._asyncio_task.done():
                asyncio_tasks.append(sub._asyncio_task)

        if asyncio_tasks:
            try:
                if timeout:
                    await asyncio.wait_for(
                        asyncio.gather(*asyncio_tasks, return_exceptions=True),
                        timeout=timeout,
                    )
                else:
                    await asyncio.gather(*asyncio_tasks, return_exceptions=True)
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("collect timeout/error: %s", exc)

        return {
            tid: (self._registry[tid].result if tid in self._registry else None)
            for tid in task_ids
        }

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        return self._registry.get(task_id)

    def list_for_report(self, report_id: int) -> List[SubagentTask]:
        return [t for t in self._registry.values() if t.report_id == report_id]

    def running_count(self, report_id: Optional[int] = None) -> int:
        tasks = self._registry.values() if report_id is None else self.list_for_report(report_id)
        return sum(1 for t in tasks if t.status in ("pending", "running", "steered"))

    def summary_for_report(self, report_id: int) -> Dict[str, Any]:
        tasks = self.list_for_report(report_id)
        return {
            "total": len(tasks),
            "running": sum(1 for t in tasks if t.status in ("running", "steered")),
            "done": sum(1 for t in tasks if t.status == "done"),
            "failed": sum(1 for t in tasks if t.status == "failed"),
            "cancelled": sum(1 for t in tasks if t.status == "cancelled"),
            "tasks": [t.to_dict() for t in tasks],
        }

    def purge_report(self, report_id: int) -> int:
        """清理已完成 report 的任务记录，释放内存。返回删除数量。"""
        to_delete = [
            tid for tid, t in self._registry.items()
            if t.report_id == report_id and t.status in ("done", "failed", "cancelled")
        ]
        for tid in to_delete:
            del self._registry[tid]
        return len(to_delete)
