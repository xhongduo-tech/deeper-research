from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.api_key import ApiKey
from app.models.knowledge_base import KnowledgeBase
from app.models.report import Report
from app.models.user import User

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

COMPLETED_STATUSES = {"completed", "delivered"}
RUNNING_STATUSES = {"pending", "running", "intake", "planning", "researching", "writing"}
FAILED_STATUSES = {"failed", "error"}


@router.get("/metrics")
async def get_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate real operational metrics for the dashboard.

    The current schema does not persist per-call LLM token usage yet, so token
    consumption is explicitly marked unavailable instead of being estimated.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    system_report_filters = [Report.created_at >= month_start]
    user_report_filters = [Report.created_at >= month_start, Report.user_id == current_user.id]

    monthly_calls = await _scalar_count(db, select(func.count(Report.id)).where(*system_report_filters))
    generated_reports = await _scalar_count(
        db,
        select(func.count(Report.id)).where(*system_report_filters, Report.status.in_(COMPLETED_STATUSES)),
    )
    running_tasks = await _scalar_count(
        db,
        select(func.count(Report.id)).where(*user_report_filters, Report.status.in_(RUNNING_STATUSES)),
    )
    failed_tasks = await _scalar_count(
        db,
        select(func.count(Report.id)).where(*user_report_filters, Report.status.in_(FAILED_STATUSES)),
    )

    reports = (
        await db.execute(
            select(
                Report.report_type,
                Report.output_format,
                Report.status,
                Report.created_at,
                Report.completed_at,
                Report.scoping_plan,
                Report.data_context,
            ).where(*system_report_filters)
        )
    ).all()

    user_reports = (
        await db.execute(
            select(Report.status, Report.created_at, Report.completed_at).where(*user_report_filters)
        )
    ).all()

    scenario_counter: Counter[str] = Counter()
    format_counter: Counter[str] = Counter()
    user_durations: list[float] = []
    for row in reports:
        scenario = _extract_business_scenario(row.scoping_plan, row.data_context, row.report_type)
        scenario_counter[scenario] += 1
        format_counter[_normalize_format(row.output_format)] += 1
    user_total_tasks = len(user_reports)
    user_completed_tasks = 0
    for row in user_reports:
        if row.status in COMPLETED_STATUSES:
            user_completed_tasks += 1
        if row.completed_at and row.created_at:
            user_durations.append(max(0.0, (row.completed_at - row.created_at).total_seconds() / 60))

    kb_totals = (
        await db.execute(
            select(
                func.count(KnowledgeBase.id),
                func.coalesce(func.sum(KnowledgeBase.doc_count), 0),
                func.coalesce(func.sum(KnowledgeBase.chunk_count), 0),
                func.coalesce(func.sum(KnowledgeBase.total_size), 0),
            )
        )
    ).one()

    kb_category_rows = (
        await db.execute(
            select(
                KnowledgeBase.kb_type,
                func.count(KnowledgeBase.id),
                func.coalesce(func.sum(KnowledgeBase.doc_count), 0),
                func.coalesce(func.sum(KnowledgeBase.chunk_count), 0),
                func.coalesce(func.sum(KnowledgeBase.total_size), 0),
            ).group_by(KnowledgeBase.kb_type)
        )
    ).all()

    active_api_keys = await _scalar_count(
        db,
        select(func.count(ApiKey.id)).where(ApiKey.status == "active"),
    )

    user_success_rate = round(user_completed_tasks / user_total_tasks * 100, 1) if user_total_tasks else 0

    return {
        "period": {
            "type": "month",
            "started_at": month_start.isoformat(),
            "updated_at": now.isoformat(),
        },
        "metrics": {
            "monthly_calls": monthly_calls,
            "token_consumption": None,
            "token_consumption_available": False,
            "generated_reports": generated_reports,
            "kb_documents": int(kb_totals[1] or 0),
            "active_api_keys": active_api_keys,
        },
        "user_metrics": {
            "running_tasks": running_tasks,
            "failed_tasks": failed_tasks,
            "success_rate": user_success_rate,
            "avg_completion_minutes": round(sum(user_durations) / len(user_durations), 1) if user_durations else 0,
            "monthly_tasks": user_total_tasks,
        },
        "business_scenarios": _to_distribution(scenario_counter),
        "output_formats": _to_distribution(format_counter),
        "knowledge_base": {
            "total": int(kb_totals[0] or 0),
            "documents": int(kb_totals[1] or 0),
            "chunks": int(kb_totals[2] or 0),
            "total_size": int(kb_totals[3] or 0),
            "total_size_gb": round(int(kb_totals[3] or 0) / 1024 / 1024 / 1024, 2),
            "categories": [
                {
                    "type": row[0] or "general",
                    "label": _kb_type_label(row[0] or "general"),
                    "count": int(row[1] or 0),
                    "documents": int(row[2] or 0),
                    "chunks": int(row[3] or 0),
                    "total_size": int(row[4] or 0),
                    "total_size_gb": round(int(row[4] or 0) / 1024 / 1024 / 1024, 2),
                }
                for row in kb_category_rows
            ],
        },
        "notes": {
            "business_scenarios": "来自用户提交需求在 scoping_plan/data_context 中沉淀的自动识别结果；缺失时回退到报告类型。",
            "token_consumption": "当前版本尚未持久化每次模型调用 token usage，需接入 LLM usage 明细表后展示真实值。",
        },
    }


async def _scalar_count(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


def _extract_business_scenario(scoping_plan: dict | None, data_context: dict | None, fallback: str | None) -> str:
    for payload in (scoping_plan or {}, data_context or {}):
        for key in ("business_scenario", "scenario", "intent_category", "task_category"):
            value = payload.get(key) if isinstance(payload, dict) else None
            if isinstance(value, str) and value.strip():
                return value.strip()
    return (fallback or "未分类场景").strip()


def _normalize_format(value: str | None) -> str:
    value = (value or "").lower()
    if value in {"ppt", "pptx", "presentation"}:
        return "PPT 生成"
    if value in {"doc", "docx", "word", "document"}:
        return "Word 生成"
    if value in {"xls", "xlsx", "excel", "sheet"}:
        return "Excel 生成"
    return "其他格式"


def _kb_type_label(value: str) -> str:
    labels = {
        "general": "通用知识",
        "policy": "制度政策",
        "research": "研究资料",
        "contract": "合同法务",
        "finance": "财务经营",
        "tech": "技术文档",
        "meeting": "会议纪要",
    }
    return labels.get(value, value)


def _to_distribution(counter: Counter[str]) -> list[dict]:
    total = sum(counter.values())
    if not total:
        return []
    return [
        {"label": label, "count": count, "percent": round(count / total * 100, 1)}
        for label, count in counter.most_common(8)
    ]
