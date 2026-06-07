import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.report import Report
from app.models.clarification import Clarification
from app.models.message import Message
from app.models.system_config import SystemConfig
from app.models.timeline_event import TimelineEvent
from app.models.uploaded_file import UploadedFile
from app.services.orchestrator import (
    add_message, add_timeline_event, AGENT_DEFINITIONS,
)
from app.services.file_parser import extract_text
from app.services.excel_grounding import ground_excel_file, is_tabular
from app.services.request_intelligence import normalize_requested_title
from app.api.ws import broadcast_event

logger = logging.getLogger(__name__)


async def create_report(db: AsyncSession, user_id: int, data: dict) -> Report:
    """Create a new report and start the pipeline."""
    normalized_title = normalize_requested_title(
        data.get("title", ""),
        data.get("brief", ""),
        data.get("report_type", ""),
    )
    report = Report(
        user_id=user_id,
        title=normalized_title,
        brief=data["brief"],
        report_type=data.get("report_type", "经营分析"),
        output_format=data.get("output_format", "word"),
        status="pending",
        progress=0.0,
        phase="初始化",
        data_context={"model_id": data.get("model_id")} if data.get("model_id") else None,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    uploaded_texts = await _attach_uploaded_files(db, report, user_id, data.get("uploaded_files", []))

    # Add initial system message
    await add_message(db, report.id, "system",
                      f"报告任务已创建: {report.title}",
                      author_id="chief", author_name="Chief")
    await add_timeline_event(db, report.id, "created", f"报告创建: {report.title}")

    # Start pipeline in background
    pipeline_data = {**data, "uploaded_texts": uploaded_texts}
    asyncio.create_task(_run_pipeline_background(report.id, pipeline_data))

    return report


async def _attach_uploaded_files(
    db: AsyncSession,
    report: Report,
    user_id: int,
    uploaded_file_ids: list,
) -> list[str]:
    """Bind pre-uploaded files to a report and extract text for the pipeline."""
    ids: list[int] = []
    for raw_id in uploaded_file_ids or []:
        try:
            ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not ids:
        return []

    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.id.in_(ids), UploadedFile.user_id == user_id)
    )
    files = result.scalars().all()
    uploaded_texts: list[str] = []

    for f in files:
        f.report_id = report.id
        if f.is_template:
            if not f.extracted_text:
                f.extracted_text = await extract_text(f.file_path, f.file_type)
            text = (f.extracted_text or "").strip()
            if text:
                uploaded_texts.append(
                    f"【模板参考：{f.original_name}】（仅作为视觉/结构风格参考，禁止使用其中事实、数字、结论作为正文证据）\n{text}"
                )
            continue
        if is_tabular(f.file_type or ""):
            grounded = await ground_excel_file(
                f.file_path, f.file_type, f.original_name, report.brief or ""
            )
            if grounded:
                uploaded_texts.append(f"【{f.original_name}】（严格数据基准，报告中所有数字必须与此一致）\n{grounded}")
                continue
        if not f.extracted_text:
            f.extracted_text = await extract_text(f.file_path, f.file_type)
        text = (f.extracted_text or "").strip()
        if text:
            uploaded_texts.append(f"【{f.original_name}】\n{text}")

    await db.commit()
    return uploaded_texts


async def _run_pipeline_background(report_id: int, data: dict):
    """Run the report pipeline in the background."""
    async with async_session() as db:
        report = await db.get(Report, report_id)
        if not report:
            logger.warning(f"Background pipeline skipped; report {report_id} not found")
            return

        try:
            await _run_pipeline_with_session(db, report, data)
        except Exception as e:
            logger.exception(f"Background pipeline failed for report {report_id}")
            report.status = "failed"
            report.error_message = str(e)
            report.updated_at = datetime.now(timezone.utc)
            await db.commit()


async def _run_pipeline_with_session(db: AsyncSession, report: Report, data: dict):
    uploaded_texts = data.get("uploaded_texts") or []
    if not uploaded_texts:
        uploaded_texts = await _load_report_uploaded_texts(db, report)
    skip_clarify = data.get("skip_clarify", False)

    # Progress broadcaster (used by both pipeline modes)
    async def _progress(data: dict):
        await broadcast_event(report.id, "research.progress", {
            "stage": data.get("phase", "researching"),
            "progress_pct": int((data.get("progress", 0)) * 100),
            "current_task": data.get("phase", ""),
            "detail": data,
        })
        section_preview = (data.get("section_preview") or "").strip()
        if section_preview:
            lines = [line.strip() for line in section_preview.splitlines() if line.strip()]
            title = next((line.lstrip("#").strip() for line in lines if line.startswith("#")), "")
            content = "\n".join(line for line in lines if not line.startswith("#")).strip()
            await broadcast_event(report.id, "document.section.draft", {
                "section_idx": int(data.get("completed") or 1) - 1,
                "section_id": data.get("section_id"),
                "title": title or f"章节 {data.get('completed') or ''}".strip(),
                "content": content or section_preview,
                "word_count": len(content or section_preview),
                "source": "unified_spec_preview",
                "completed": data.get("completed"),
                "total": data.get("total"),
            })

    kb_ids = data.get("kb_ids", [])
    skills = list(data.get("skills", []) or [])
    try:
        from app.services.document_standards import skill_for_standard
        standard_skill = skill_for_standard(report.report_type or "", report.brief or "")
        if standard_skill and standard_skill not in skills:
            skills.append(standard_skill)
        is_word = (report.output_format or "").lower() in {"word", "doc", "docx", "wps"}
        if "word-authoring" not in skills and is_word:
            skills.append("word-authoring")
        if is_word:
            from app.services.request_intelligence import wants_charts
            if wants_charts(report.brief or "", report.report_type or "", report.output_format or ""):
                for chart_skill in ("data-grounding", "advanced-charting", "table-figure-authoring"):
                    if chart_skill not in skills:
                        skills.append(chart_skill)
    except Exception:
        pass

    selected_model = await _load_selected_model_profile(db, data.get("model_id"))
    effort = str(data.get("effort") or "low").lower()

    from app.services.llm_service import selected_llm_profile, effort_context
    if selected_model:
        with selected_llm_profile(selected_model), effort_context(effort):
            await _run_unified(db, report, uploaded_texts, _progress, kb_ids, skills)
        return

    with effort_context(effort):
        await _run_unified(db, report, uploaded_texts, _progress, kb_ids, skills)


async def _load_selected_model_profile(db: AsyncSession, model_id: str | None) -> dict | None:
    if not model_id:
        return None
    clean_id = str(model_id).replace("pool:", "", 1)
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "model_pool"))
    ).scalar_one_or_none()
    if not row or not row.value:
        return None
    try:
        items = json.loads(row.value)
    except Exception:
        return None
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or item.get("model")) == clean_id and item.get("enabled", True):
            return {
                "model": str(item.get("model") or "").strip(),
                "base_url": str(item.get("base_url") or "").strip().rstrip("/"),
                "api_key": str(item.get("api_key") or "ollama").strip(),
            }
    return None


async def _run_unified(
    db: AsyncSession,
    report: Report,
    uploaded_texts: list[str],
    progress_callback,
    kb_ids: list,
    skills: list,
):
    """Run the unified 7-phase pipeline — the single production path.

    UNDERSTAND → PLAN → RESEARCH → SPEC_GEN → DOC_RENDER → QA → EXPORT.
    Clarification pause/resume is handled inside the UNDERSTAND phase, which
    restores from scoping_plan["answered_clarifications"] on resume.
    """
    from app.pipeline import run_unified_pipeline
    await run_unified_pipeline(
        db, report,
        uploaded_texts=uploaded_texts,
        progress_callback=progress_callback,
        kb_ids=kb_ids,
        skills=skills,
    )


async def _load_report_uploaded_texts(db: AsyncSession, report: Report) -> list[str]:
    """Reload attached file text when a paused/clarified job resumes."""
    result = await db.execute(
        select(UploadedFile)
        .where(
            UploadedFile.report_id == report.id,
            UploadedFile.user_id == report.user_id,
        )
        .order_by(UploadedFile.created_at.asc())
    )
    files = result.scalars().all()
    uploaded_texts: list[str] = []
    for f in files:
        if f.is_template:
            if not f.extracted_text:
                f.extracted_text = await extract_text(f.file_path, f.file_type)
            text = (f.extracted_text or "").strip()
            if text:
                uploaded_texts.append(
                    f"【模板参考：{f.original_name}】（仅作为视觉/结构风格参考，禁止使用其中事实、数字、结论作为正文证据）\n{text}"
                )
            continue
        if is_tabular(f.file_type or ""):
            grounded = await ground_excel_file(
                f.file_path, f.file_type, f.original_name, report.brief or ""
            )
            if grounded:
                uploaded_texts.append(f"【{f.original_name}】（严格数据基准，报告中所有数字必须与此一致）\n{grounded}")
                continue
        if not f.extracted_text:
            f.extracted_text = await extract_text(f.file_path, f.file_type)
        text = (f.extracted_text or "").strip()
        if text:
            uploaded_texts.append(f"【{f.original_name}】\n{text}")
    if files:
        await db.commit()
    return uploaded_texts


async def answer_clarifications(db: AsyncSession, report: Report,
                                answers: list[dict]) -> Report:
    """Save clarification answers and resume pipeline."""
    answered_clarifications: list[dict] = []

    for ans in answers:
        result = await db.execute(
            select(Clarification).where(
                Clarification.id == ans["id"],
                Clarification.report_id == report.id,
            )
        )
        clarification = result.scalar_one_or_none()
        if clarification:
            clarification.answer = ans.get("answer", "")
            clarification.status = "answered"
            clarification.answered_at = datetime.now(timezone.utc)
            answered_clarifications.append({
                "question": clarification.question,
                "answer": ans.get("answer", ""),
            })

    await db.commit()

    # P2-F: Persist answers into scoping_plan so UNDERSTAND can restore from cache
    if answered_clarifications:
        scoping = report.scoping_plan or {}
        scoping["answered_clarifications"] = answered_clarifications
        report.scoping_plan = scoping

    # Resume pipeline
    report.status = "running"
    report.phase = "恢复生产"
    await db.commit()

    asyncio.create_task(_run_pipeline_background(report.id, {"skip_clarify": True}))

    return report


async def get_report_detail(db: AsyncSession, report_id: int) -> Report | None:
    """Get report with clarifications and timeline."""
    result = await db.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        return None

    # Load related data
    clarifications_result = await db.execute(
        select(Clarification).where(Clarification.report_id == report_id)
    )
    report._clarifications = clarifications_result.scalars().all()

    timeline_result = await db.execute(
        select(TimelineEvent)
        .where(TimelineEvent.report_id == report_id)
        .order_by(TimelineEvent.created_at)
    )
    report._timeline = timeline_result.scalars().all()

    return report


async def list_reports(db: AsyncSession, user_id: int,
                       status: str | None = None,
                       limit: int = 20, offset: int = 0) -> tuple[list[Report], int]:
    """List reports for a user."""
    query = select(Report).where(Report.user_id == user_id)
    count_query = select(func.count(Report.id)).where(Report.user_id == user_id)

    if status:
        query = query.where(Report.status == status)
        count_query = count_query.where(Report.status == status)

    query = query.order_by(Report.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    reports = result.scalars().all()

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    return reports, total


async def get_report_messages(db: AsyncSession, report_id: int,
                              limit: int = 100) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.report_id == report_id)
        .order_by(Message.created_at)
        .limit(limit)
    )
    return result.scalars().all()


async def get_agent_list(db: AsyncSession) -> list[dict]:
    """Return the agent directory."""
    agents = []
    for agent_id, agent_def in AGENT_DEFINITIONS.items():
        agents.append({
            "employee_id": agent_def["employee_id"],
            "name": agent_def["name"],
            "role": agent_def["role"],
            "tag": agent_def["tag"],
            "enabled": True,
        })
    return agents
