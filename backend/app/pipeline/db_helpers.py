"""Database helper functions for pipeline phases.

Consolidated from orchestrator.py and simple_pipeline.py to avoid duplication.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.report import Report

logger = logging.getLogger(__name__)


async def add_timeline_event(
    db: "AsyncSession",
    report_id: int,
    event_type: str,
    label: str,
    payload: dict | None = None,
) -> None:
    from app.models.timeline_event import TimelineEvent
    event = TimelineEvent(
        report_id=report_id,
        event_type=event_type,
        label=label,
        payload=payload,
    )
    db.add(event)
    try:
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist timeline event: %s", exc)


async def add_message(
    db: "AsyncSession",
    report_id: int,
    role: str,
    content: str,
    author_id: str | None = None,
    author_name: str | None = None,
):
    from app.models.message import Message
    msg = Message(
        report_id=report_id,
        role=role,
        author_id=author_id,
        author_name=author_name,
        content=content,
    )
    db.add(msg)
    try:
        await db.commit()
        return msg
    except Exception as exc:
        logger.warning("Failed to persist message: %s", exc)
        return None


async def update_report_status(
    db: "AsyncSession",
    report: "Report",
    status: str,
    progress: float,
    phase: str,
) -> None:
    report.status = status
    report.progress = progress
    report.phase = phase
    report.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(report)


_PAUSE_MAX_WAIT_SECONDS = 86400  # 24 hours — after this, force-fail the report


async def wait_if_paused(db: "AsyncSession", report: "Report") -> None:
    """Cooperative pause point between pipeline steps.

    Raises PipelineError after 24 hours of continuous pause to prevent
    reports from remaining stuck in 'paused' status indefinitely.
    """
    import time
    from app.pipeline.types import PipelineError

    deadline = time.monotonic() + _PAUSE_MAX_WAIT_SECONDS
    while True:
        await db.refresh(report)
        if report.status != "paused":
            return
        if time.monotonic() > deadline:
            raise PipelineError(
                phase=report.phase or "UNKNOWN",
                message="报告暂停超过24小时，自动标记为失败",
            )
        await asyncio.sleep(1.0)
