"""run_unified_pipeline — single entrypoint for the unified 7-phase pipeline.

Phase sequence:
  UNDERSTAND → PLAN → RESEARCH → SPEC_GEN → DOC_RENDER → QA → EXPORT

Each phase transition is committed to DB and broadcast over WebSocket.
Any PipelineError marks the report as failed with a descriptive message.
"""
from __future__ import annotations

import logging
from typing import Callable, TYPE_CHECKING

from app.pipeline.types import PipelineContext, PipelineError
from app.pipeline.state import PipelineState
from app.pipeline.db_helpers import add_timeline_event, wait_if_paused

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.report import Report

logger = logging.getLogger(__name__)


async def run_unified_pipeline(
    db: "AsyncSession",
    report: "Report",
    uploaded_texts: list[str] | None = None,
    progress_callback: Callable | None = None,
    kb_ids: list[int] | None = None,
    skills: list[str] | None = None,
) -> None:
    """Execute the full unified pipeline for a report.

    Called by report_service when USE_UNIFIED_PIPELINE=true.
    Never raises �� all errors are caught and stored in report.error_message.
    """
    from app.pipeline.phases.understand import UnderstandPhase
    from app.pipeline.phases.plan import PlanPhase
    from app.pipeline.phases.research import ResearchPhase
    from app.pipeline.phases.spec_gen import SpecGenPhase
    from app.pipeline.phases.doc_render import DocRenderPhase
    from app.pipeline.phases.qa import QAPhase
    from app.pipeline.phases.export import ExportPhase

    ctx = await PipelineContext.build(
        report=report,
        db=db,
        uploaded_texts=uploaded_texts,
        kb_ids=kb_ids,
        skills=skills,
        progress_callback=progress_callback,
    )
    state = PipelineState()

    phases = [
        ("UNDERSTAND", UnderstandPhase(ctx)),
        ("PLAN", PlanPhase(ctx)),
        ("RESEARCH", ResearchPhase(ctx)),
        ("SPEC_GEN", SpecGenPhase(ctx)),
        ("DOC_RENDER", DocRenderPhase(ctx)),
        ("QA", QAPhase(ctx)),
        ("EXPORT", ExportPhase(ctx, pipeline_state=state)),
    ]

    for phase_name, phase in phases:
        # Honour pause / cancel
        await wait_if_paused(db, report)

        try:
            await state.enter_phase(phase_name, db, report)
            await phase.run()
        except PipelineError as exc:
            await state.fail(db, report, exc)
            return
        except Exception as exc:
            logger.exception("[Pipeline] Unexpected error in phase %s", phase_name)
            await state.fail(
                db, report,
                PipelineError(phase=phase_name, message=f"意外错误: {exc}"),
            )
            return

        # Notify progress callback if provided
        if progress_callback:
            try:
                from app.pipeline.state import _PHASE_PROGRESS
                await progress_callback({
                    "phase": phase_name,
                    "progress": _PHASE_PROGRESS.get(phase_name, 0.0),
                })
            except Exception:
                pass

        # Handle UNDERSTAND clarification pause
        if phase_name == "UNDERSTAND" and ctx.understanding.get("clarification_needed"):
            logger.info("[Pipeline] Pausing for clarifications after UNDERSTAND")
            report.status = "pending"
            report.phase = "等待澄清回复"
            await db.commit()
            return  # Will be resumed by answer_clarifications flow


async def run_section_revision(
    db: "AsyncSession",
    report: "Report",
    section_id: str,
    instruction: str,
    progress_callback: Callable | None = None,
) -> None:
    """P3-1: Re-run SPEC_GEN (for one section) + DOC_RENDER + EXPORT.

    Restores pipeline context from scoping_plan (understanding, outline,
    research_findings) so we don't need to redo the full pipeline.
    The instruction is injected as QA feedback so the LLM knows what to change.
    """
    from app.pipeline.phases.spec_gen import SpecGenPhase
    from app.pipeline.phases.doc_render import DocRenderPhase
    from app.pipeline.phases.export import ExportPhase

    ctx = await PipelineContext.build(
        report=report,
        db=db,
        uploaded_texts=None,
        kb_ids=None,
        skills=None,
        progress_callback=progress_callback,
    )
    state = PipelineState()

    # P1-5: Validate scoping_plan before proceeding — missing keys would cause silent
    # failures where the revision runs with empty context and overwrites good content.
    scoping = dict(report.scoping_plan or {})
    _REQUIRED_SCOPING_KEYS = ("understanding", "outline")
    missing_keys = [k for k in _REQUIRED_SCOPING_KEYS if not scoping.get(k)]
    if missing_keys:
        logger.warning(
            "[Revision] scoping_plan missing required keys %s for report %s — aborting revision",
            missing_keys, report.id,
        )
        report.status = "failed"
        report.error_message = (
            f"[REVISION] 上下文数据不完整（缺少 {missing_keys}），"
            "无法执行章节修订，请重新生成完整报告"
        )
        await db.commit()
        return

    # Restore research findings from cache
    cached_findings = scoping.get("research_cache", {})
    if cached_findings:
        ctx.research_findings.update(cached_findings)

    # Restore existing spec if available
    spec_json = scoping.get("spec_json")
    if spec_json:
        try:
            from app.rendering.doc_spec import DocxSpec, PptxSpec, XlsxSpec
            fmt = ctx.output_format or "docx"
            if fmt in ("pptx", "ppt"):
                ctx.spec = PptxSpec.model_validate(spec_json)
            elif fmt in ("xlsx", "excel", "xls"):
                ctx.spec = XlsxSpec.model_validate(spec_json)
            else:
                ctx.spec = DocxSpec.model_validate(spec_json)
        except Exception as exc:
            logger.warning("[Revision] Could not restore spec from scoping_plan: %s", exc)

    qa_feedback = [{"severity": "p0", "section_id": section_id,
                    "message": f"用户修订指令：{instruction}"}] if instruction else []

    try:
        report.status = "processing"
        report.phase = f"修订章节 {section_id}"
        await db.commit()

        await state.enter_phase("SPEC_GEN", db, report)
        spec_gen = SpecGenPhase(ctx, qa_feedback=qa_feedback)
        await spec_gen.run(section_ids=[section_id])

        await state.enter_phase("DOC_RENDER", db, report)
        doc_render = DocRenderPhase(ctx)
        await doc_render.run()

        await state.enter_phase("EXPORT", db, report)
        export = ExportPhase(ctx, pipeline_state=state)
        await export.run()

    except PipelineError as exc:
        await state.fail(db, report, exc)
    except Exception as exc:
        logger.exception("[Revision] Unexpected error in section revision")
        await state.fail(db, report, PipelineError(phase="REVISION", message=f"意外错误: {exc}"))
    finally:
        if progress_callback:
            try:
                await progress_callback({"phase": "REVISION", "progress": 1.0})
            except Exception:
                pass
