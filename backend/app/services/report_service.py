"""
ReportService, MessageService, ClarificationService.

These are pure data-access + event-emission helpers. Business decisions
(phase transitions, team selection, etc.) live in SupervisorService.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import (
    Clarification,
    Evidence,
    Message,
    MessageRole,
    Report,
    ReportStatus,
    ReportType,
    TimelineEvent,
)
from app.models.uploaded_file import UploadedFile
from app.services.event_bus import event_bus
from app.services.report_types import get_report_type


# ---------------------------------------------------------------------------
# Serializers (keep API response shaping in one place)
# ---------------------------------------------------------------------------

def serialize_report(r: Report) -> Dict[str, Any]:
    return {
        "id": r.id,
        "user_id": r.user_id,
        "title": r.title,
        "brief": r.brief,
        "report_type": r.report_type,
        "depth": r.depth,
        "status": r.status,
        "phase": r.phase,
        "progress": r.progress,
        "scoping_plan": r.scoping_plan,
        "team_roster": r.team_roster,
        "section_outline": r.section_outline,
        "output_index": r.output_index,
        "template_file_id": r.template_file_id,
        "final_file_path": r.final_file_path,
        "final_file_name": r.final_file_name,
        "error_message": r.error_message,
        "data_context": r.data_context,
        "trace_log": r.trace_log,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


def serialize_message(m: Message) -> Dict[str, Any]:
    return {
        "id": m.id,
        "report_id": m.report_id,
        "role": m.role,
        "author_id": m.author_id,
        "author_name": m.author_name,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def serialize_clarification(c: Clarification) -> Dict[str, Any]:
    return {
        "id": c.id,
        "report_id": c.report_id,
        "question": c.question,
        "default_answer": c.default_answer,
        "answer": c.answer,
        "status": c.status,
        "priority": getattr(c, "priority", None) or "medium",
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "answered_at": c.answered_at.isoformat() if c.answered_at else None,
    }


def serialize_timeline(t: TimelineEvent) -> Dict[str, Any]:
    return {
        "id": t.id,
        "report_id": t.report_id,
        "event_type": t.event_type,
        "label": t.label,
        "payload": t.payload,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def serialize_evidence(e: Evidence) -> Dict[str, Any]:
    return {
        "id": e.id,
        "report_id": e.report_id,
        "file_id": e.file_id,
        "source_name": e.source_name,
        "locator": e.locator,
        "snippet": e.snippet,
        "kind": e.kind,
        "meta": e.meta,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


# ---------------------------------------------------------------------------
# ReportService
# ---------------------------------------------------------------------------

class ReportService:
    @staticmethod
    async def create(
        db: AsyncSession,
        *,
        user_id: int,
        title: str,
        brief: str,
        report_type: str,
        depth: str = "standard",
        api_key_id: Optional[int] = None,
        template_file_id: Optional[int] = None,
    ) -> Report:
        rt = get_report_type(report_type)
        outline = rt["section_skeleton"] if rt else []
        team = rt["default_team"] if rt else []

        report = Report(
            user_id=user_id,
            api_key_id=api_key_id,
            title=title.strip() or "未命名报告",
            brief=brief.strip(),
            report_type=report_type,
            depth=depth,
            status=ReportStatus.draft.value,
            phase="draft",
            progress=0.0,
            section_outline=outline,
            team_roster=team,
            template_file_id=template_file_id,
        )
        db.add(report)
        await db.flush()
        await db.refresh(report)
        return report

    @staticmethod
    async def get(db: AsyncSession, report_id: int, *, user_id: Optional[int] = None) -> Optional[Report]:
        stmt = select(Report).where(Report.id == report_id)
        if user_id is not None:
            stmt = stmt.where(Report.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        user_id: int,
        *,
        status_filter: Optional[List[str]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Report]:
        stmt = select(Report).where(Report.user_id == user_id)
        if status_filter:
            stmt = stmt.where(Report.status.in_(status_filter))
        stmt = stmt.order_by(Report.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_status(
        db: AsyncSession,
        report: Report,
        *,
        status: Optional[str] = None,
        phase: Optional[str] = None,
        progress: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        changed = False
        if status is not None and report.status != status:
            report.status = status
            changed = True
            if status == ReportStatus.producing.value and not report.started_at:
                report.started_at = datetime.utcnow()
            if status in (ReportStatus.delivered.value, ReportStatus.failed.value, ReportStatus.cancelled.value):
                report.completed_at = datetime.utcnow()
        if phase is not None and report.phase != phase:
            report.phase = phase
            changed = True
        if progress is not None and report.progress != progress:
            report.progress = max(0.0, min(1.0, progress))
            changed = True
        if error_message is not None:
            report.error_message = error_message
            changed = True

        if changed:
            await db.flush()
            payload: Dict[str, Any] = {
                "status": report.status,
                "phase": report.phase,
                "progress": report.progress,
                "error_message": report.error_message,
            }
            # Include delivery fields so the frontend can show the download
            # button without an extra round-trip.
            if report.status == ReportStatus.delivered.value:
                payload["final_file_name"] = report.final_file_name
                payload["final_file_path"] = report.final_file_path
                payload["completed_at"] = (
                    report.completed_at.isoformat() if report.completed_at else None
                )
            await event_bus.publish(report.id, {"type": "status", "payload": payload})

    @staticmethod
    async def delete(db: AsyncSession, report: Report) -> None:
        await db.delete(report)
        await db.flush()

    # --- v2: plan / outline / output_index / files -----------------------

    @staticmethod
    async def attach_files(
        db: AsyncSession,
        report: Report,
        *,
        file_ids: List[int],
        user_id: int,
    ) -> List[UploadedFile]:
        """Bind uploaded files owned by ``user_id`` to ``report``.

        Files that don't exist or aren't owned by the user are silently
        skipped — this prevents cross-tenant leakage via spoofed ids.
        """
        if not file_ids:
            return []
        stmt = select(UploadedFile).where(
            UploadedFile.id.in_(file_ids),
            UploadedFile.user_id == user_id,
        )
        result = await db.execute(stmt)
        files = list(result.scalars().all())
        for f in files:
            f.report_id = report.id
        await db.flush()
        return files

    @staticmethod
    async def list_files(
        db: AsyncSession, report_id: int
    ) -> List[UploadedFile]:
        stmt = select(UploadedFile).where(UploadedFile.report_id == report_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def save_scoping_plan(
        db: AsyncSession,
        report: Report,
        *,
        plan: Dict[str, Any],
        outline: Optional[List[Dict[str, Any]]] = None,
        team: Optional[List[str]] = None,
    ) -> None:
        report.scoping_plan = plan
        if outline is not None:
            report.section_outline = outline
        if team is not None:
            report.team_roster = team
        await db.flush()

    @staticmethod
    async def save_output_section(
        db: AsyncSession,
        report: Report,
        *,
        section_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """Persist one section's output into ``report.output_index``.

        ``output_index`` is a dict ``{section_id: {text, employee_id, note, ...}}``
        kept as a JSON blob. We assign a new dict reference so SQLAlchemy
        picks up the mutation on JSON columns.
        Also broadcasts a ``section_output`` SSE event so the collaboration
        room right panel updates in real-time without polling.
        """
        current: Dict[str, Any] = dict(report.output_index or {})
        current[section_id] = payload
        report.output_index = current
        await db.flush()
        await event_bus.publish(
            report.id,
            {
                "type": "section_output",
                "payload": {
                    "section_id": section_id,
                    "output": payload,
                },
            },
        )


# ---------------------------------------------------------------------------
# MessageService
# ---------------------------------------------------------------------------

class MessageService:
    @staticmethod
    async def append(
        db: AsyncSession,
        *,
        report_id: int,
        role: str,
        content: str,
        author_id: Optional[str] = None,
        author_name: Optional[str] = None,
        meta: Optional[dict] = None,
    ) -> Message:
        # Validate role (raises ValueError if bad)
        MessageRole(role)
        msg = Message(
            report_id=report_id,
            role=role,
            author_id=author_id,
            author_name=author_name,
            content=content,
            meta=meta,
        )
        db.add(msg)
        await db.flush()
        await db.refresh(msg)
        await event_bus.publish(
            report_id, {"type": "message", "payload": serialize_message(msg)}
        )
        return msg

    @staticmethod
    async def list_for_report(
        db: AsyncSession, report_id: int, *, limit: int = 500
    ) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.report_id == report_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# ClarificationService
# ---------------------------------------------------------------------------

class ClarificationService:
    @staticmethod
    async def create_many(
        db: AsyncSession,
        *,
        report_id: int,
        items: List[Dict[str, Any]],
    ) -> List[Clarification]:
        """items: [{"question": str, "default_answer": str | None}]"""
        created: List[Clarification] = []
        for it in items:
            q = (it.get("question") or "").strip()
            if not q:
                continue
            pri = str(it.get("priority") or "medium").lower()
            if pri not in ("high", "medium", "low"):
                pri = "medium"
            c = Clarification(
                report_id=report_id,
                question=q,
                default_answer=it.get("default_answer"),
                priority=pri,
            )
            db.add(c)
            created.append(c)
        await db.flush()
        for c in created:
            await db.refresh(c)
            await event_bus.publish(
                report_id,
                {"type": "clarification", "payload": serialize_clarification(c)},
            )
        return created

    @staticmethod
    async def answer(
        db: AsyncSession,
        clarification: Clarification,
        *,
        answer: Optional[str] = None,
        use_default: bool = False,
    ) -> Clarification:
        if use_default:
            clarification.answer = clarification.default_answer
            clarification.status = "defaulted"
        else:
            clarification.answer = answer
            clarification.status = "answered"
        clarification.answered_at = datetime.utcnow()
        await db.flush()
        await db.refresh(clarification)
        await event_bus.publish(
            clarification.report_id,
            {"type": "clarification", "payload": serialize_clarification(clarification)},
        )
        return clarification

    @staticmethod
    async def list_for_report(
        db: AsyncSession, report_id: int
    ) -> List[Clarification]:
        stmt = (
            select(Clarification)
            .where(Clarification.report_id == report_id)
            .order_by(Clarification.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# EvidenceService
# ---------------------------------------------------------------------------

class EvidenceService:
    """CRUD for report-scoped evidence chunks.

    These rows are what powers "cite the original material" behavior: each
    employee section can reference ``evidence_id`` tokens, and the UI resolves
    them to the snippet/source.
    """

    @staticmethod
    async def replace_for_report(
        db: AsyncSession,
        *,
        report_id: int,
        chunks: List[Dict[str, Any]],
    ) -> List[Evidence]:
        """Wipe-and-reinsert the evidence for a report. Called once per
        scoping pass, so it's deterministic regardless of re-runs."""
        # Delete existing
        await db.execute(
            Evidence.__table__.delete().where(Evidence.report_id == report_id)
        )
        created: List[Evidence] = []
        for ch in chunks:
            e = Evidence(
                report_id=report_id,
                file_id=ch.get("file_id"),
                source_name=ch.get("file_name") or "未命名材料",
                locator=f"chunk#{ch.get('chunk_index', 0) + 1}",
                snippet=(ch.get("text") or "")[:4000],
                kind=ch.get("kind") or "text",
                meta={
                    "evidence_id": ch.get("evidence_id"),
                    "keywords": ch.get("keywords") or [],
                    "preview": ch.get("preview"),
                    "has_embedding": bool(ch.get("embedding")),
                },
            )
            db.add(e)
            created.append(e)
        await db.flush()
        return created

    @staticmethod
    async def list_for_report(
        db: AsyncSession, report_id: int
    ) -> List[Evidence]:
        stmt = (
            select(Evidence)
            .where(Evidence.report_id == report_id)
            .order_by(Evidence.id.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# TimelineService
# ---------------------------------------------------------------------------

class TimelineService:
    @staticmethod
    async def append(
        db: AsyncSession,
        *,
        report_id: int,
        event_type: str,
        label: str,
        payload: Optional[dict] = None,
    ) -> TimelineEvent:
        evt = TimelineEvent(
            report_id=report_id,
            event_type=event_type,
            label=label,
            payload=payload,
        )
        db.add(evt)
        await db.flush()
        await db.refresh(evt)
        await event_bus.publish(
            report_id, {"type": "timeline", "payload": serialize_timeline(evt)}
        )
        return evt

    @staticmethod
    async def list_for_report(db: AsyncSession, report_id: int) -> List[TimelineEvent]:
        stmt = (
            select(TimelineEvent)
            .where(TimelineEvent.report_id == report_id)
            .order_by(TimelineEvent.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
