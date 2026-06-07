"""Pipeline state machine — explicit DB commits and broadcasts on every transition."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.api.ws import broadcast_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.report import Report
    from app.pipeline.types import PipelineError

logger = logging.getLogger(__name__)

# Ordered phase list
PHASES = ["UNDERSTAND", "PLAN", "RESEARCH", "SPEC_GEN", "DOC_RENDER", "QA", "EXPORT"]

# Weighted progress — reflects that RESEARCH and SPEC_GEN dominate wall-clock time
_PHASE_WEIGHTS = {
    "UNDERSTAND": 0.08,
    "PLAN":       0.10,
    "RESEARCH":   0.35,
    "SPEC_GEN":   0.25,
    "DOC_RENDER": 0.10,
    "QA":         0.07,
    "EXPORT":     0.05,
}

def _build_phase_progress() -> dict[str, float]:
    cumulative = 0.0
    result: dict[str, float] = {}
    for phase in PHASES:
        cumulative += _PHASE_WEIGHTS.get(phase, 1 / len(PHASES))
        result[phase] = round(min(cumulative, 1.0), 2)
    return result

_PHASE_PROGRESS = _build_phase_progress()


class PipelineState:
    """Coordinates report status and phase transitions.

    Every transition is committed to the DB and broadcast over WebSocket so the
    frontend always has an accurate picture — no silent state drift.
    """

    async def enter_phase(
        self,
        phase: str,
        db: "AsyncSession",
        report: "Report",
        detail: str = "",
    ) -> None:
        from app.pipeline.db_helpers import add_timeline_event

        report.status = "running"
        report.phase = phase
        report.progress = _PHASE_PROGRESS.get(phase, report.progress)
        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await broadcast_event(report.id, "pipeline.phase", {
            "phase": phase,
            "progress": report.progress,
            "detail": detail,
        })
        await add_timeline_event(db, report.id, "phase_start", phase, {"detail": detail})
        logger.info("[report=%s] → %s (%.0f%%)", report.id, phase, report.progress * 100)

    async def complete(
        self,
        db: "AsyncSession",
        report: "Report",
        file_path: str,
        file_name: str,
    ) -> None:
        from app.pipeline.db_helpers import add_timeline_event

        report.status = "completed"
        report.phase = "完成"
        report.progress = 1.0
        report.final_file_path = file_path
        report.final_file_name = file_name
        report.completed_at = datetime.now(timezone.utc)
        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await broadcast_event(report.id, "pipeline.complete", {
            "file_name": file_name,
        })
        await add_timeline_event(db, report.id, "completed", "报告生成完成", {"file_name": file_name})
        logger.info("[report=%s] completed → %s", report.id, file_name)

    async def fail(
        self,
        db: "AsyncSession",
        report: "Report",
        error: "PipelineError",
    ) -> None:
        from app.pipeline.db_helpers import add_timeline_event, add_message

        error_msg = str(error)
        report.status = "failed"
        report.phase = f"FAILED:{error.phase}"
        report.error_message = error_msg
        report.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await broadcast_event(report.id, "pipeline.error", {
            "phase": error.phase,
            "message": error.message,
            "section_id": error.section_id,
        })
        await add_timeline_event(db, report.id, "error", f"阶段 {error.phase} 失败", {
            "message": error.message,
            "section_id": error.section_id,
        })
        await add_message(db, report.id, "assistant",
                          f"报告生成失败（{error.phase}）：{error.message}",
                          author_id="system", author_name="系统")
        logger.error("[report=%s] FAILED at %s: %s", report.id, error.phase, error.message)

    async def wait_if_paused(self, db: "AsyncSession", report: "Report") -> None:
        import asyncio
        while True:
            await db.refresh(report)
            if report.status != "paused":
                return
            await asyncio.sleep(1.0)
