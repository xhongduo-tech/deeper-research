"""EXPORT phase — writes rendered bytes to disk and broadcasts completion."""
from __future__ import annotations

import logging
import os
import uuid
from typing import TYPE_CHECKING

from app.pipeline.types import PipelineContext, PipelineError

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ExportPhase:
    PHASE_NAME = "EXPORT"

    def __init__(self, ctx: PipelineContext, pipeline_state=None):
        self.ctx = ctx
        self.pipeline_state = pipeline_state

    async def run(self) -> None:
        ctx = self.ctx
        if not ctx.rendered_bytes:
            raise PipelineError(self.PHASE_NAME, "No rendered bytes to export")

        ext = ctx.rendered_ext or "docx"
        upload_dir = _get_upload_dir()
        os.makedirs(upload_dir, exist_ok=True)

        unique_name = f"report_{ctx.report.id}_{uuid.uuid4().hex[:8]}.{ext}"
        file_path = os.path.join(upload_dir, unique_name)

        with open(file_path, "wb") as f:
            f.write(ctx.rendered_bytes)

        logger.info("[EXPORT] Saved report to %s (%d bytes)", file_path, len(ctx.rendered_bytes))

        # R18-OBS: Persist structured event log to scoping_plan for post-run analysis.
        try:
            scoping = dict(ctx.report.scoping_plan or {})
            scoping["event_log"] = ctx._event_log
            ctx.report.scoping_plan = scoping
        except Exception as _el_exc:
            logger.debug("[EXPORT] event_log persist failed (non-fatal): %s", _el_exc)

        if self.pipeline_state:
            await self.pipeline_state.complete(ctx.db, ctx.report, file_path, unique_name)
        else:
            ctx.report.final_file_path = file_path
            ctx.report.final_file_name = unique_name
            ctx.report.status = "completed"
            ctx.report.progress = 1.0
            ctx.report.phase = "完成"
            await ctx.db.commit()
            from app.api.ws import broadcast_event
            await broadcast_event(ctx.report.id, "pipeline.complete", {"file_name": unique_name})


def _get_upload_dir() -> str:
    from app.config import settings
    return getattr(settings, "upload_dir", "/app/data/uploads")
