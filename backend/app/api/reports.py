import base64
import json
import os
import re
import tempfile
import zipfile
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import quote

from app.database import get_db
from app.schemas.report import (
    ReportCreate, ReportResponse, ReportListResponse,
    ClarificationResponse, ClarificationAnswer, TimelineEventResponse,
)
from app.services.report_service import (
    create_report, get_report_detail, list_reports, answer_clarifications,
)
from app.services.llm_service import chat_json, selected_llm_profile
from app.api.ws import broadcast_event
from app.middleware.auth_middleware import get_current_user
from app.models.clarification import Clarification
from app.models.evidence import Evidence
from app.models.message import Message
from app.models.system_config import SystemConfig
from app.models.timeline_event import TimelineEvent
from app.models.uploaded_file import UploadedFile
from app.models.user import User

router = APIRouter(prefix="/api/reports", tags=["reports"])


class DocumentPlanRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    template: str | None = None
    scenario: str | None = None
    output_format: str = "word"
    uploaded_files: list[int] = Field(default_factory=list)
    file_names: list[str] = Field(default_factory=list)
    model_id: str | None = None
    effort: str = "low"


class DocumentPlanQuestion(BaseModel):
    question: str
    type: str = "text"
    options: list[str] = Field(default_factory=list)
    default_answer: str = ""


class DocumentPlanResponse(BaseModel):
    summary: str = ""
    steps: list[str] = Field(default_factory=list)
    questions: list[DocumentPlanQuestion] = Field(default_factory=list)
    should_ask: bool = False
    reasoning: str = ""

_FINANCIAL_REPORT_TYPES = {
    "financial", "financial_research",
    "股票研报", "研报", "业绩点评", "投资简报", "投资报告", "深度报告",
    "公司研究", "卖方研报", "年报点评", "季报点评", "券商研报",
    "行业研报", "宏观研报", "financial research",
}


def _build_financial_metadata(report) -> dict | None:
    """Build report_metadata for financial PDF header, or None if not financial."""
    rtype = (report.report_type or "").strip()
    if rtype not in _FINANCIAL_REPORT_TYPES:
        return None

    meta: dict = {
        "institution": "DataAgent Studio",
        "report_date": (
            report.created_at.strftime("%Y-%m-%d") if report.created_at else ""
        ),
        "industry": rtype,
    }

    # Try to extract stock code / company name from title (e.g. "比亚迪(002594)投资简报")
    import re as _re
    title = report.title or ""
    code_match = _re.search(r"[（(](\d{6}(?:\.[A-Z]{2})?)[）)]", title)
    if code_match:
        meta["stock_code"] = code_match.group(1)

    # Try to extract rating from brief (looks for 买入/增持/中性/减持/回避)
    brief_text = (report.brief or "") + title
    rating_match = _re.search(r"(买入|增持|中性|减持|回避)", brief_text)
    if rating_match:
        meta["rating"] = rating_match.group(1)

    return meta


def _cfg_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


async def _selected_model_profile(db: AsyncSession, model_id: str | None) -> dict | None:
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
        if not isinstance(item, dict) or not item.get("enabled", True):
            continue
        if str(item.get("id") or item.get("model")) == clean_id:
            return {
                "model": str(item.get("model") or "").strip(),
                "base_url": str(item.get("base_url") or "").strip().rstrip("/"),
                "api_key": str(item.get("api_key") or "ollama").strip(),
            }
    return None


def _clean_string_list(value, limit: int, item_limit: int = 180) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        cleaned.append(text[:item_limit])
        seen.add(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def _is_yes_no_question(question: str) -> bool:
    text = question.strip()
    return bool(re.search(r"(是否|是不是|能否|可否|要不要|需要不需要|需不需要|有没有|是否需要|确认.*吗|吗[？?]?$)", text))


def _normalize_plan_questions(value) -> list[DocumentPlanQuestion]:
    items = value if isinstance(value, list) else ([value] if value else [])
    questions: list[DocumentPlanQuestion] = []
    for item in items:
        if isinstance(item, dict):
            question = str(item.get("question") or item.get("title") or item.get("content") or "").strip()
            raw_type = str(item.get("type") or item.get("question_type") or "").strip().lower()
            raw_options = item.get("options") or item.get("choices") or []
            default_answer = str(item.get("default_answer") or item.get("default") or "").strip()
        else:
            question = str(item or "").strip()
            raw_type = ""
            raw_options = []
            default_answer = ""
        if not question:
            continue
        options = _clean_string_list(raw_options if isinstance(raw_options, list) else [raw_options], 8, 80)
        is_multi = raw_type in {"multi_choice", "multi_select", "checkbox", "multiple"}
        is_single = raw_type in {"single_choice", "choice", "select", "radio", "yes_no"}
        is_choice = is_multi or is_single or bool(options)
        if not is_choice and _is_yes_no_question(question):
            is_single = True
            is_choice = True
            options = ["是", "否", "暂不确定"]
        if is_choice and len(options) < 2:
            options = ["是", "否", "暂不确定"]
        if is_multi and len(options) >= 2:
            question_type = "multi_choice"
        elif is_choice:
            question_type = "single_choice"
        else:
            question_type = "text"
        questions.append(DocumentPlanQuestion(
            question=question[:180],
            type=question_type,
            options=options if question_type != "text" else [],
            default_answer=default_answer[:100],
        ))
        if len(questions) >= 5:
            break
    return questions


async def _load_delivery_quality_config(db: AsyncSession) -> dict:
    keys = {
        "quality_gate_mode",
        "ppt_render_qa_required",
        "word_claim_gate_required",
        "excel_quality_gate_required",
    }
    rows = (await db.execute(select(SystemConfig).where(SystemConfig.key.in_(keys)))).scalars().all()
    cfg = {r.key: r.value for r in rows}
    return {
        "quality_gate_mode": (cfg.get("quality_gate_mode") or "strict").lower(),
        "ppt_render_qa_required": _cfg_bool(cfg.get("ppt_render_qa_required"), True),
        "word_claim_gate_required": _cfg_bool(cfg.get("word_claim_gate_required"), True),
        "excel_quality_gate_required": _cfg_bool(cfg.get("excel_quality_gate_required"), True),
    }


def _apply_admin_delivery_policy(fmt: str, gate: dict, cfg: dict) -> dict:
    gate = dict(gate or {})
    blockers = list(gate.get("blockers") or [])
    warnings = list(gate.get("warnings") or [])
    if fmt in {"ppt", "pptx", "powerpoint"} and not cfg.get("ppt_render_qa_required", True):
        blockers = [b for b in blockers if b != "PPT_RENDER_CRITICAL"]
        warnings.append("管理员已将 PPT 渲染图像级 QA 设置为非强制门禁")
    elif fmt in {"word", "doc", "docx", "wps"} and not cfg.get("word_claim_gate_required", True):
        blockers = [b for b in blockers if b != "WORD_NUMERIC_CLAIMS_UNVERIFIED"]
        warnings.append("管理员已将 Word 数字 claim 核验设置为非强制门禁")
    elif fmt in {"excel", "sheet", "xlsx", "xls"} and not cfg.get("excel_quality_gate_required", True):
        blockers = [b for b in blockers if not (str(b).startswith("EXCEL") or str(b).startswith("XLSX"))]
        warnings.append("管理员已将 Excel 工作簿 QA 设置为非强制门禁")
    gate["blockers"] = blockers
    gate["warnings"] = warnings
    gate["passed"] = not blockers
    gate["admin_policy"] = cfg
    return gate


_COMPLETION_NOTICE_RE = re.compile(
    r"^(报告已生成完毕|已全部生成完毕|生成完成)[！!，,：:\s]*(?:包含\s*\d+\s*个章节)?.{0,120}$",
    re.S,
)


def _is_completion_notice(content: str) -> bool:
    text = (content or "").strip()
    return bool(text) and len(text) <= 180 and bool(_COMPLETION_NOTICE_RE.match(text))


def _looks_like_report_draft(content: str) -> bool:
    text = (content or "").strip()
    if not text:
        return False
    heading_count = len(re.findall(r"(?m)^#{1,3}\s+\S+", text))
    return (heading_count >= 2 and len(text) >= 300) or len(text) >= 1200


def _select_download_markdown_content(messages: list[Message]) -> str:
    """Pick the latest substantive draft, not the post-completion chat notice."""
    fallback = ""
    for msg in messages:
        content = (getattr(msg, "content", "") or "").strip()
        if not content:
            continue
        if not fallback and not _is_completion_notice(content):
            fallback = content
        if _is_completion_notice(content):
            continue
        if _looks_like_report_draft(content):
            return content
    return fallback or ((messages[0].content or "") if messages else "")


def _artifact_extension(path_or_name: str | None) -> str:
    if not path_or_name:
        return ""
    return os.path.splitext(str(path_or_name))[1].lower().lstrip(".")


def _existing_final_artifact(report) -> tuple[str, str] | None:
    path = str(getattr(report, "final_file_path", "") or "").strip()
    if not path or not os.path.isfile(path):
        return None
    ext = _artifact_extension(getattr(report, "final_file_name", None) or path)
    if not ext:
        return None
    return path, ext


def _download_response(data: bytes, filename: str, ext: str, media_type: str, headers: dict | None = None) -> Response:
    ascii_name = f"report.{ext}"
    encoded_name = quote(filename)
    response_headers = {
        "Content-Disposition": f"attachment; filename={ascii_name}; filename*=UTF-8''{encoded_name}",
    }
    if headers:
        response_headers.update(headers)
    return Response(content=data, media_type=media_type, headers=response_headers)


def _docx_plain_text(docx_bytes: bytes) -> str:
    try:
        import io

        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip()
    except Exception:
        return ""


def _final_docx_has_substance(docx_bytes: bytes, report) -> bool:
    text = _docx_plain_text(docx_bytes)
    if len(text) >= 300:
        return True
    markdown = _markdown_from_spec_json((report.scoping_plan or {}).get("spec_json"))
    return not markdown or len(markdown) < 300


async def _build_report_sections_for_export(
    report,
    report_id: int,
    normalized_fmt: str,
    db: AsyncSession,
) -> tuple[list[dict], str, list[UploadedFile]]:
    """Build the same markdown sections used by download and file preview."""
    from app.models.message import Message
    from app.services.document_generator import markdown_to_sections
    from app.services.file_parser import extract_text
    from app.services.excel_grounding import ground_excel_file, is_tabular

    result = await db.execute(
        select(Message)
        .where(Message.report_id == report_id, Message.author_id == "li_bai")
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(20)
    )
    li_bai_messages = result.scalars().all()
    markdown_content = _select_download_markdown_content(li_bai_messages)
    if not (markdown_content or "").strip():
        markdown_content = _markdown_from_spec_json((report.scoping_plan or {}).get("spec_json"))
    files: list[UploadedFile] = []
    uploaded_texts: list[str] = []
    try:
        from app.services.orchestrator import (
            build_source_grounded_draft,
            clean_generated_content,
        )
        from app.services.delivery_quality import polish_final_report_markdown

        markdown_content = clean_generated_content(markdown_content)
        markdown_content = polish_final_report_markdown(
            markdown_content,
            f"{report.title or ''}\n{report.brief or ''}",
        )
        should_check_uploads = normalized_fmt in ("pdf", "pptx", "ppt", "powerpoint", "docx", "doc", "wps")
        if should_check_uploads:
            file_result = await db.execute(
                select(UploadedFile)
                .where(UploadedFile.report_id == report_id, UploadedFile.is_template == False)
                .order_by(UploadedFile.created_at.desc())
            )
            files = file_result.scalars().all()
            for f in files:
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
            if not (markdown_content or "").strip():
                grounded = build_source_grounded_draft(
                    report.brief, report.report_type, uploaded_texts, normalized_fmt,
                )
                if grounded:
                    markdown_content = grounded
    except Exception:
        pass
    if not (markdown_content or "").strip():
        markdown_content = _markdown_from_spec_json((report.scoping_plan or {}).get("spec_json"))

    sections = markdown_to_sections(markdown_content)
    if not sections:
        sections = [{"title": "报告内容", "content": markdown_content}]
    return sections, markdown_content, files


@router.post("/document-plan", response_model=DocumentPlanResponse)
async def create_document_plan(
    data: DocumentPlanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prompt = (data.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="请输入文档需求")

    file_notes = list(data.file_names or [])
    if data.uploaded_files:
        result = await db.execute(
            select(UploadedFile).where(
                UploadedFile.id.in_(data.uploaded_files),
                UploadedFile.user_id == current_user.id,
            )
        )
        files = result.scalars().all()
        for file in files[:8]:
            note = file.original_name or file.file_name or f"文件 {file.id}"
            snippet = (file.extracted_text or "").strip()
            if snippet:
                note = f"{note}：{snippet[:600]}"
            file_notes.append(note)

    messages = [
        {
            "role": "system",
            "content": (
                "你是 DataAgent Word 的首席文档规划智能体。你的任务不是套模板，而是像资深顾问和写作负责人一样，"
                "根据用户输入、所选文档模板、上传资料和交付场景，判断这份文档是否需要先追问用户。"
                "你必须同时做宏观判断（目标、受众、交付物、是否需要外部调研/数据读取/合规格式）和微观判断"
                "（哪些缺失信息会显著影响文档质量，哪些问题可以由模型自行合理假设）。"
                "只在问题确实会影响执行方向、事实口径、格式或交付成败时追问；简单明确的任务 questions 返回空数组。"
                "返回严格 JSON，不要 Markdown，不要解释 JSON 之外的文字。JSON 字段："
                "summary: string；steps: string[]，3到7步，必须是针对该任务的真实执行步骤；"
                "questions: object[]，0到5个高价值问题，每项格式为 "
                "{\"question\": string, \"type\": \"text\"|\"single_choice\"|\"multi_choice\", \"options\": string[], \"default_answer\": string}；"
                "should_ask: boolean，questions 为空时为 false；reasoning: string，用一句话说明为什么问或不问。"
                "如果问题是\"是否/能否/要不要/选择哪一种\"等单选封闭问题，必须使用 single_choice 并给出2到5个可选项；"
                "如果问题允许用户选择多个方向/维度/模块（例如\"希望包含哪些分析维度\"\"需要哪些图表类型\"），使用 multi_choice 并给出3到8个可选项（可包含\"其他\"）；"
                "只有需要用户自由补充背景、范围、口径或资料时才使用 text。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "用户需求": prompt,
                    "所选模板": data.template or "",
                    "场景": data.scenario or "",
                    "输出格式": data.output_format,
                    "上传文件与资料摘要": file_notes[:10],
                },
                ensure_ascii=False,
            ),
        },
    ]

    profile = await _selected_model_profile(db, data.model_id)
    try:
        if profile:
            with selected_llm_profile(profile):
                raw = await chat_json(messages, temperature=0.2, max_tokens=1800)
        else:
            raw = await chat_json(messages, temperature=0.2, max_tokens=1800)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型规划失败：{exc}") from exc

    if raw.get("error"):
        raise HTTPException(status_code=502, detail=f"模型规划失败：{raw.get('error')}")

    steps = _clean_string_list(raw.get("steps"), 7, 220)
    questions = _normalize_plan_questions(raw.get("questions"))
    should_ask = bool(raw.get("should_ask")) and bool(questions)
    if not steps:
        raise HTTPException(status_code=502, detail="模型没有返回有效计划，请重试")

    return DocumentPlanResponse(
        summary=str(raw.get("summary") or "").strip()[:300],
        steps=steps,
        questions=questions if should_ask else [],
        should_ask=should_ask,
        reasoning=str(raw.get("reasoning") or "").strip()[:300],
    )


@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_new_report(
    data: ReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = data.model_dump()
    # Resolve system KBs if requested
    if data.include_system_kb:
        from app.models.knowledge_base import KnowledgeBase
        from sqlalchemy import select
        system_kb_ids = (await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.scope == "corp")
        )).scalars().all()
        existing = set(data.kb_ids)
        for kb_id in system_kb_ids:
            if kb_id not in existing:
                payload["kb_ids"].append(kb_id)
    report = await create_report(db, current_user.id, payload)
    return _report_to_response(report)


@router.get("", response_model=dict)
async def list_user_reports(
    status_filter: str | None = None,
    project_id: int | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports, total = await list_reports(db, current_user.id, status_filter, project_id, limit, offset)
    return {
        "reports": [_report_list_item(r) for r in reports],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    return _report_to_response(report)


@router.post("/{report_id}/clarify", response_model=ReportResponse)
async def answer_clarify(
    report_id: int,
    data: ClarificationAnswer,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    report = await answer_clarifications(db, report, data.answers)
    return _report_to_response(report)


@router.post("/{report_id}/pause", response_model=ReportResponse)
async def pause_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    if report.status not in ("pending", "running"):
        raise HTTPException(status_code=400, detail="当前任务状态不可暂停")
    report.status = "paused"
    report.phase = "已暂停"
    await db.commit()
    await db.refresh(report)
    await broadcast_event(report_id, "research.paused", {
        "report_id": report_id,
        "status": report.status,
        "progress_pct": int((report.progress or 0) * 100),
        "phase": report.phase,
    })
    return _report_to_response(report)


@router.post("/{report_id}/resume", response_model=ReportResponse)
async def resume_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    if report.status != "paused":
        raise HTTPException(status_code=400, detail="当前任务未暂停")
    report.status = "running"
    report.phase = "继续生成中"
    await db.commit()
    await db.refresh(report)
    await broadcast_event(report_id, "research.resumed", {
        "report_id": report_id,
        "status": report.status,
        "progress_pct": int((report.progress or 0) * 100),
        "phase": report.phase,
    })
    return _report_to_response(report)


@router.post("/{report_id}/edit-section")
async def edit_report_section(
    report_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Incrementally edit a specific section of a completed report."""
    from app.services.incremental_editor import IncrementalEditor

    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")

    editor = IncrementalEditor(db=db)
    result = await editor.edit_section(
        report_id=report_id,
        section_id=data.get("section_id", ""),
        instruction=data.get("instruction", ""),
        current_content=data.get("current_content", ""),
        neighbor_sections=data.get("neighbor_sections"),
        report_title=report.title,
    )

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "编辑失败"))

    return {
        "success": True,
        "section_id": result["section_id"],
        "edited_content": result["edited_content"],
        "changes_summary": result.get("changes_summary", ""),
        "word_count_delta": result.get("word_count_delta", 0),
    }


@router.post("/{report_id}/revise-section")
async def revise_report_section(
    report_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """P3-1: Re-run the pipeline for a specific section with a revision instruction.

    Unlike edit-section (text-level), this runs SPEC_GEN+DOC_RENDER to regenerate
    the section using the full pipeline with the instruction as QA feedback.
    Requires the report to have a stored spec_json (i.e. generated via unified pipeline).
    """
    import asyncio
    from app.pipeline.run import run_section_revision

    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")

    section_id = data.get("section_id", "")
    instruction = data.get("instruction", "")
    if not section_id:
        raise HTTPException(status_code=400, detail="section_id 不能为空")

    scoping = dict(report.scoping_plan or {})
    if not scoping.get("spec_json"):
        raise HTTPException(
            status_code=400,
            detail="该报告没有可用的规格快照（spec_json），无法进行章节修订。请使用 edit-section 接口。"
        )

    # Run revision in background so request returns quickly
    async def _run():
        async for _db in __import__("app.database", fromlist=["get_db"]).get_db():
            fresh_report = await get_report_detail(_db, report_id)
            if fresh_report:
                await run_section_revision(_db, fresh_report, section_id, instruction)
            break

    asyncio.create_task(_run())
    return {"success": True, "message": f"章节 '{section_id}' 修订已提交，正在后台重新生成"}


@router.post("/{report_id}/chat")
async def chat_with_report(
    report_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """P3-3: Multi-turn chat interface for report interaction.

    Routes user messages to:
    - Revision: triggers section re-generation (revise_section path)
    - Q&A: answers questions about the report content using LLM
    - Full regen: triggers full pipeline re-run with new instructions
    """
    from app.services.report_chat_service import handle_report_chat

    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")

    message = data.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    result = await handle_report_chat(db, report, message, user_id=current_user.id)
    return result


@router.get("/{report_id}/download")
async def download_report(
    report_id: int,
    fmt: str = "pptx",  # pptx | docx | xlsx
    style: str = "business",
    quality_mode: str = "admin",  # admin | strict | warn
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and download a PPTX, DOCX, or XLSX file for the report."""
    from app.services.document_generator import (
        convert_docx_bytes_to_pdf,
        generate_pptx,
        generate_docx,
        generate_xlsx,
        generate_pdf,
    )
    from app.services.delivery_quality import (
        append_source_appendix,
        build_source_registry,
        merge_slidespec_sections,
        repair_ppt_sections_for_quality,
    )
    from app.services.evaluation_service import build_delivery_gate, evaluate_generation

    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    if report.status not in ("completed", "delivered"):
        raise HTTPException(status_code=400, detail="报告尚未生成完成")

    normalized_fmt = fmt.lower()
    admin_quality_cfg = await _load_delivery_quality_config(db)
    effective_quality_mode = quality_mode.lower()
    if effective_quality_mode == "admin":
        effective_quality_mode = admin_quality_cfg.get("quality_gate_mode", "strict")
    if effective_quality_mode not in {"strict", "warn"}:
        effective_quality_mode = "strict"

    final_artifact = _existing_final_artifact(report)
    if final_artifact:
        final_path, final_ext = final_artifact
        safe_title = report.title.replace("/", "-").replace("\\", "-")[:60]
        if normalized_fmt in ("docx", "doc", "wps") and final_ext == "docx":
            final_bytes = open(final_path, "rb").read()
            if not _final_docx_has_substance(final_bytes, report):
                final_artifact = None
            else:
                return _download_response(
                    data=final_bytes,
                    filename=f"{safe_title}.docx",
                    ext="docx",
                    media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"X-DataAgent-Artifact-Source": "final_file"},
                )
        if final_artifact and normalized_fmt == "pdf" and final_ext == "pdf":
            return _download_response(
                data=open(final_path, "rb").read(),
                filename=f"{safe_title}.pdf",
                ext="pdf",
                media_type="application/pdf",
                headers={"X-DataAgent-Artifact-Source": "final_file"},
            )
        if final_artifact and normalized_fmt == "pdf" and final_ext == "docx":
            docx_bytes = open(final_path, "rb").read()
            if _final_docx_has_substance(docx_bytes, report):
                pdf_bytes = convert_docx_bytes_to_pdf(docx_bytes)
            else:
                pdf_bytes = None
            if pdf_bytes:
                return _download_response(
                    data=pdf_bytes,
                    filename=f"{safe_title}.pdf",
                    ext="pdf",
                    media_type="application/pdf",
                    headers={"X-DataAgent-Artifact-Source": "final_file"},
                )
        if final_artifact and normalized_fmt in ("pptx", "ppt", "powerpoint") and final_ext == "pptx":
            return _download_response(
                data=open(final_path, "rb").read(),
                filename=f"{safe_title}.pptx",
                ext="pptx",
                media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={"X-DataAgent-Artifact-Source": "final_file"},
            )
        if final_artifact and normalized_fmt in ("xlsx", "xls") and final_ext == "xlsx":
            return _download_response(
                data=open(final_path, "rb").read(),
                filename=f"{safe_title}.xlsx",
                ext="xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"X-DataAgent-Artifact-Source": "final_file"},
            )

    sections, markdown_content, files = await _build_report_sections_for_export(
        report,
        report_id,
        normalized_fmt,
        db,
    )

    source_registry = build_source_registry(files, report.output_index)
    claim_verification = {}
    # NOTE: source appendix, claim verification appendix, and risk appendix
    # were intentionally removed — the user wants the raw report content
    # without auto-injected boilerplate sections.

    if normalized_fmt in ("pptx", "ppt", "powerpoint"):
        sections = merge_slidespec_sections(sections, report.section_outline)

    safe_title = report.title.replace("/", "-").replace("\\", "-")[:60]
    artifact_metrics = {}

    if normalized_fmt == "pdf":
        docx_data = generate_docx(
            title=report.title,
            sections=sections,
            report_type=report.report_type,
        )
        data = convert_docx_bytes_to_pdf(docx_data) or generate_pdf(
            title=report.title,
            sections=sections,
            report_type=report.report_type,
            report_metadata=_build_financial_metadata(report),
        )
        ext = "pdf"
        filename = f"{safe_title}.{ext}"
        media_type = "application/pdf"
    elif normalized_fmt in ("docx", "doc", "wps"):
        data = generate_docx(
            title=report.title,
            sections=sections,
            report_type=report.report_type,
        )
        ext = "docx"
        filename = f"{safe_title}.{ext}"
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif normalized_fmt in ("xlsx", "xls"):
        data = generate_xlsx(
            title=report.title,
            sections=sections,
            report_type=report.report_type,
        )
        try:
            from app.services.excel_quality_service import score_xlsx_workbook

            artifact_metrics = {
                "excel_quality": score_xlsx_workbook(data, source_registry=source_registry)
            }
        except Exception as exc:
            artifact_metrics = {
                "excel_quality": {
                    "passed": False,
                    "overall_score": 0,
                    "warnings": [f"Excel 工作簿 QA 失败: {exc}"],
                    "blockers": ["EXCEL_QA_FAILED"],
                }
            }
        ext = "xlsx"
        filename = f"{safe_title}.{ext}"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        from app.services.ppt_aesthetic_scorer import PptAestheticScorer
        from app.services.ppt_render_qa_service import combine_ppt_quality, score_pptx_rendered

        attempts = []
        data = b""
        for attempt in range(1, 3):
            data = generate_pptx(
                title=report.title,
                sections=sections,
                report_type=report.report_type,
                style=style,
            )
            try:
                with tempfile.NamedTemporaryFile(suffix=".pptx") as tmp:
                    tmp.write(data)
                    tmp.flush()
                    geometry = PptAestheticScorer().score_pptx(tmp.name).to_dict()
                    render_visual = score_pptx_rendered(tmp.name)
                    artifact_metrics = combine_ppt_quality(geometry, render_visual)
            except Exception as exc:
                artifact_metrics = {
                    "overall_score": 0,
                    "passed": False,
                    "global_issues": [f"自动视觉质检失败: {exc}"],
                    "render_visual_qa": {"rendered": False, "issues": [str(exc)]},
                }
            attempts.append({
                "attempt": attempt,
                "overall_score": artifact_metrics.get("overall_score"),
                "passed": artifact_metrics.get("passed"),
                "issues": artifact_metrics.get("global_issues", [])[:6],
            })
            if artifact_metrics.get("passed") or attempt >= 2:
                break
            sections = repair_ppt_sections_for_quality(
                sections,
                artifact_metrics.get("global_issues") or [],
            )
        artifact_metrics["repair_attempts"] = attempts
        ext = "pptx"
        filename = f"{safe_title}.{ext}"
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    if claim_verification:
        artifact_metrics["claim_verification"] = claim_verification
    evaluation = evaluate_generation(
        output_format=normalized_fmt,
        brief=report.brief,
        sections=sections,
        source_registry=source_registry,
        artifact_metrics=artifact_metrics,
    )
    delivery_gate = build_delivery_gate(
        output_format=normalized_fmt,
        evaluation=evaluation,
        artifact_metrics=artifact_metrics,
    )
    delivery_gate = _apply_admin_delivery_policy(
        normalized_fmt,
        delivery_gate,
        admin_quality_cfg,
    )
    output_index = dict(report.output_index or {})
    if artifact_metrics:
        quality = dict(output_index.get("artifact_quality") or {})
        if normalized_fmt in ("xlsx", "xls"):
            quality["excel_quality"] = artifact_metrics.get("excel_quality", artifact_metrics)
        elif normalized_fmt in ("docx", "doc", "wps"):
            quality["word_quality"] = artifact_metrics
        elif normalized_fmt == "pdf":
            quality["pdf_quality"] = artifact_metrics
        else:
            quality["ppt_aesthetic"] = artifact_metrics
        output_index["artifact_quality"] = quality
    output_index["generation_evaluation"] = evaluation
    output_index["delivery_gate"] = delivery_gate
    output_index["source_registry"] = [
        {k: v for k, v in item.items() if k != "content"} for item in source_registry
    ]
    report.output_index = output_index
    db.add(TimelineEvent(
        report_id=report_id,
        event_type="artifact_quality",
        label=f"{(ext or normalized_fmt).upper()} 导出质检完成",
        payload={
            "format": normalized_fmt,
            "evaluation_score": evaluation.get("overall_score"),
            "evaluation_passed": evaluation.get("passed"),
            "delivery_gate_passed": delivery_gate.get("passed"),
            "delivery_gate_blockers": delivery_gate.get("blockers"),
            "ppt_aesthetic_score": artifact_metrics.get("overall_score") if artifact_metrics else None,
        },
    ))
    await db.commit()

    # ── Quality gate failures no longer block download ──────────────────────
    # The user wants the raw generated content without any auto-injected
    # appendix or risk-repair section. Risks are tracked in timeline only.
    risks_repaired = 0
    if False and not delivery_gate.get("passed"):
        blockers = list(delivery_gate.get("blockers") or [])
        warnings = list(delivery_gate.get("warnings") or [])
        eval_issues = []
        for cat in (evaluation.get("issues") or []):
            if isinstance(cat, dict):
                eval_issues.append(cat)
            elif isinstance(cat, str):
                eval_issues.append({"description": cat})
        # Build risk appendix markdown
        lines = ["", "## 风险解析与修复说明", "", "本报告在交付前自动检测到以下问题，已逐项解析记录："]
        if blockers:
            lines.append("")
            lines.append("**阻断性风险（已记录待人工复核）**")
            for b in blockers[:20]:
                if isinstance(b, dict):
                    desc = b.get("description") or b.get("message") or str(b)
                    suggestion = b.get("suggestion") or b.get("fix") or ""
                    lines.append(f"- {desc}" + (f"｜建议修复：{suggestion}" if suggestion else ""))
                else:
                    lines.append(f"- {b}")
                risks_repaired += 1
        if warnings:
            lines.append("")
            lines.append("**警示性风险（已在文档中标注）**")
            for w in warnings[:20]:
                if isinstance(w, dict):
                    desc = w.get("description") or w.get("message") or str(w)
                    lines.append(f"- {desc}")
                else:
                    lines.append(f"- {w}")
                risks_repaired += 1
        if eval_issues:
            lines.append("")
            lines.append("**生成评估问题**")
            for it in eval_issues[:20]:
                desc = it.get("description") or it.get("message") or ""
                sec = it.get("section") or ""
                sev = (it.get("severity") or "").upper()
                line = f"- "
                if sev: line += f"[{sev}] "
                if sec: line += f"{sec}："
                line += desc
                lines.append(line)
                risks_repaired += 1
        lines.extend([
            "",
            f"**质量得分**：{evaluation.get('overall_score', 'n/a')}",
            f"**自动修复条目数**：{risks_repaired}",
            "",
            "若需进一步修复，可重新提交生成请求，或在 admin 设置中调整质量门禁阈值。",
        ])
        risk_appendix = "\n".join(lines)
        # Append as a new section and rebuild the artifact
        sections = list(sections) + [{
            "title": "风险解析与修复说明",
            "content": risk_appendix,
        }]
        try:
            if normalized_fmt in ("docx", "doc", "wps"):
                data = generate_docx(title=report.title, sections=sections, report_type=report.report_type)
            elif normalized_fmt in ("xlsx", "xls"):
                data = generate_xlsx(title=report.title, sections=sections, report_type=report.report_type)
            elif normalized_fmt == "pdf":
                data = generate_pdf(title=report.title, sections=sections, report_type=report.report_type, report_metadata=_build_financial_metadata(report))
            else:
                data = generate_pptx(title=report.title, sections=sections, report_type=report.report_type, style=style)
        except Exception:
            pass  # fall back to original artifact if rebuild fails
        # Record the auto-repair event
        try:
            db.add(TimelineEvent(
                report_id=report_id,
                event_type="auto_repair",
                label=f"已自动修复 {risks_repaired} 项风险并写入文档",
                payload={
                    "risks_repaired": risks_repaired,
                    "blockers_count": len(blockers),
                    "warnings_count": len(warnings),
                },
            ))
            await db.commit()
        except Exception:
            pass

    ascii_name = f"report.{ext}"
    encoded_name = quote(filename)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={ascii_name}; filename*=UTF-8''{encoded_name}",
            "X-DataAgent-Quality-Gate": "passed" if delivery_gate.get("passed") else "warn",
            "X-DataAgent-Quality-Score": str(evaluation.get("overall_score", "")),
            "X-DataAgent-Risks-Repaired": str(risks_repaired),
        },
    )


@router.get("/{report_id}/preview")
async def preview_report_artifact(
    report_id: int,
    fmt: str = "docx",
    page_limit: int = 8,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Render the actual export artifact for right-pane preview.

    For Word/PDF documents, the browser preview should not re-render markdown;
    it should display rasterized pages from the same DOCX that powers download.
    This keeps embedded chart PNGs, table layout and PDF output synchronized.
    """
    from app.services.document_generator import generate_docx, render_docx_bytes_to_pngs

    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    if report.status not in ("completed", "delivered"):
        raise HTTPException(status_code=400, detail="报告尚未生成完成")

    normalized_fmt = fmt.lower()
    markdown_content = ""
    docx_data = b""
    final_artifact = _existing_final_artifact(report)
    if final_artifact and normalized_fmt in ("docx", "doc", "wps", "pdf"):
        final_path, final_ext = final_artifact
        if final_ext == "docx":
            final_bytes = open(final_path, "rb").read()
            if _final_docx_has_substance(final_bytes, report):
                docx_data = final_bytes
    if not docx_data:
        sections, markdown_content, _files = await _build_report_sections_for_export(
            report,
            report_id,
            "docx" if normalized_fmt == "pdf" else normalized_fmt,
            db,
        )
        docx_data = generate_docx(
            title=report.title,
            sections=sections,
            report_type=report.report_type,
        )
    images = render_docx_bytes_to_pngs(
        docx_data,
        max_pages=max(1, min(int(page_limit or 8), 20)),
    )
    if images:
        return {
            "mode": "rendered_pages",
            "source_format": "docx",
            "page_count": len(images),
            "pages": [
                "data:image/png;base64," + base64.b64encode(img).decode("ascii")
                for img in images
            ],
        }

    embedded_images = []
    try:
        import io

        with zipfile.ZipFile(io.BytesIO(docx_data)) as zf:
            for name in zf.namelist():
                if not name.startswith("word/media/"):
                    continue
                lower = name.lower()
                if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    continue
                blob = zf.read(name)
                mime = "image/jpeg" if lower.endswith((".jpg", ".jpeg")) else "image/webp" if lower.endswith(".webp") else "image/png"
                embedded_images.append(f"data:{mime};base64," + base64.b64encode(blob).decode("ascii"))
    except Exception:
        embedded_images = []
    if embedded_images:
        return {
            "mode": "docx_embedded_images",
            "source_format": "docx",
            "page_count": 0,
            "pages": [],
            "images": embedded_images,
            "warning": "缺少 LibreOffice/soffice，已展示 DOCX 内嵌图表兜底预览",
        }

    return JSONResponse(
        {
            "mode": "markdown_fallback",
            "source_format": "markdown",
            "title": report.title,
            "markdown": markdown_content or _markdown_from_spec_json((report.scoping_plan or {}).get("spec_json")),
            "warning": "缺少 LibreOffice/soffice 或 PDF raster 依赖，已退回 Markdown 预览",
        },
        headers={"X-DataAgent-Preview-Fallback": "markdown"},
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="无权访问")
    await db.execute(delete(Evidence).where(Evidence.report_id == report_id))
    await db.execute(delete(Message).where(Message.report_id == report_id))
    await db.execute(delete(Clarification).where(Clarification.report_id == report_id))
    await db.execute(delete(TimelineEvent).where(TimelineEvent.report_id == report_id))
    await db.execute(
        update(UploadedFile)
        .where(UploadedFile.report_id == report_id)
        .values(report_id=None)
    )
    await db.delete(report)
    await db.commit()
    return {"message": "已删除"}


def _report_to_response(report) -> dict:
    clarifications = getattr(report, "_clarifications", [])
    timeline = getattr(report, "_timeline", [])
    output_index = _response_output_index(report)
    return {
        "id": report.id,
        "title": report.title,
        "brief": report.brief,
        "report_type": report.report_type,
        "output_format": report.output_format,
        "status": report.status,
        "progress": report.progress,
        "phase": report.phase,
        "section_outline": report.section_outline,
        "output_index": output_index,
        "final_file_name": report.final_file_name,
        "final_file_path": report.final_file_path,
        "error_message": report.error_message,
        "clarifications": [
            {
                "id": c.id, "question": c.question,
                "default_answer": c.default_answer, "status": c.status,
                "priority": c.priority,
            }
            for c in clarifications
        ],
        "timeline": [
            {
                "id": t.id, "event_type": t.event_type,
                "label": t.label, "payload": t.payload,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in timeline
        ],
        "project_id": report.project_id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "started_at": report.started_at.isoformat() if report.started_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }


def _response_output_index(report) -> dict:
    output = dict(report.output_index or {})
    if not any(output.get(k) for k in ("markdown", "final_markdown", "content_markdown", "report_markdown", "draft_markdown")):
        markdown = _markdown_from_spec_json((report.scoping_plan or {}).get("spec_json"))
        if markdown:
            output["final_markdown"] = markdown
    standard = ((report.scoping_plan or {}).get("spec_json") or {}).get("metadata", {}).get("document_standard")
    if standard and "document_standard" not in output:
        output["document_standard"] = standard
    return output


def _markdown_from_spec_json(spec_json) -> str:
    if not isinstance(spec_json, dict):
        return ""
    sections = spec_json.get("sections") or []
    if not isinstance(sections, list) or not sections:
        return ""
    lines = [f"# {spec_json.get('title') or ''}".strip(), ""]
    for section in sections:
        if not isinstance(section, dict):
            continue
        _append_section_markdown(lines, section, level=2)
    return "\n".join(lines).strip()


def _append_section_markdown(lines: list[str], section: dict, level: int = 2) -> None:
    title = str(section.get("title") or "").strip()
    if title:
        lines.extend([f"{'#' * min(level, 6)} {title}", ""])
    for para in section.get("paragraphs") or []:
        text = str(para or "").strip()
        if text:
            lines.extend([text, ""])
    for bullet in section.get("bullets") or []:
        text = str(bullet or "").strip()
        if text:
            lines.append(f"- {text}")
    if section.get("bullets"):
        lines.append("")
    table = section.get("table")
    if isinstance(table, dict) and table.get("headers"):
        headers = [str(h) for h in table.get("headers") or []]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in table.get("rows") or []:
            cells = [str(c) for c in row]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    for sub in section.get("subsections") or []:
        if isinstance(sub, dict):
            _append_section_markdown(lines, sub, level + 1)


def _report_list_item(report) -> dict:
    return {
        "id": report.id,
        "title": report.title,
        "report_type": report.report_type,
        "brief": report.brief,
        "output_format": report.output_format,
        "status": report.status,
        "progress": report.progress,
        "phase": report.phase,
        "project_id": report.project_id,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "completed_at": report.completed_at.isoformat() if report.completed_at else None,
    }
