"""Admin API — system config management and user administration."""
from __future__ import annotations

import importlib.util
import json
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import get_current_admin
from app.models.knowledge_base import KBDocument, KnowledgeBase
from app.models.report import Report
from app.models.system_config import SystemConfig
from app.models.timeline_event import TimelineEvent
from app.models.user import User

router = APIRouter(prefix="/api/admin", tags=["admin"])

CONFIG_KEYS = {
    "llm_base_url", "llm_model", "llm_api_key",
    "embed_model", "embed_base_url", "embed_api_key",
    "rerank_model", "rerank_base_url", "rerank_api_key",
    "enable_external_search", "enable_browser", "external_search_max_results",
    "sandbox_timeout", "max_workers",
    "rag_chunk_size", "rag_chunk_overlap", "rag_top_k", "rag_score_threshold",
    "rag_enabled", "rag_hybrid_retrieval", "rag_rerank_enabled",
    "quality_gate_mode", "ppt_render_qa_required", "word_claim_gate_required",
    "excel_quality_gate_required",
    "model_pool",
}

BOOL_KEYS = {
    "enable_external_search", "enable_browser", "rag_enabled",
    "rag_hybrid_retrieval", "rag_rerank_enabled", "ppt_render_qa_required",
    "word_claim_gate_required", "excel_quality_gate_required",
}

INT_LIMITS = {
    "external_search_max_results": (1, 10),
    "sandbox_timeout": (5, 300),
    "max_workers": (1, 50),
    "rag_chunk_size": (100, 2000),
    "rag_chunk_overlap": (0, 400),
    "rag_top_k": (1, 20),
}


def _require_admin(current_user: User = Depends(get_current_admin)) -> User:
    return current_user


def _user_dict(u: User, report_stats: dict[int, dict] | None = None) -> dict:
    stats = (report_stats or {}).get(u.id, {})
    return {
        "id": u.id,
        "auth_id": u.auth_id or "",
        "username": u.username,
        "department": u.department or "",
        "scene": u.scene or "",
        "description": u.description or "",
        "role": u.role,
        "is_active": u.is_active,
        "report_count": int(stats.get("report_count") or 0),
        "last_report_at": stats.get("last_report_at"),
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _default_config() -> dict[str, str]:
    return {
        "llm_base_url": settings.default_llm_base_url,
        "llm_model": settings.default_llm_model,
        "llm_api_key": settings.default_llm_api_key,
        "embed_model": settings.embed_model,
        "embed_base_url": settings.embed_base_url,
        "embed_api_key": settings.embed_api_key,
        "rerank_model": "",
        "rerank_base_url": "",
        "rerank_api_key": "",
        "enable_external_search": "false",
        "external_search_policy": "intranet_disabled",
        "enable_browser": str(settings.enable_browser).lower(),
        "external_search_max_results": "5",
        "sandbox_timeout": str(settings.sandbox_timeout),
        "max_workers": str(settings.max_workers),
        "rag_enabled": "true",
        "rag_hybrid_retrieval": "true",
        "rag_rerank_enabled": "false",
        "rag_chunk_size": str(settings.rag_chunk_size),
        "rag_chunk_overlap": str(settings.rag_chunk_overlap),
        "rag_top_k": str(settings.rag_top_k),
        "rag_score_threshold": str(settings.rag_score_threshold),
        "quality_gate_mode": "strict",
        "ppt_render_qa_required": "true",
        "word_claim_gate_required": "true",
        "excel_quality_gate_required": "true",
        "model_pool": json.dumps([
            {
                "id": "standard",
                "name": "DataAgent 默认模型",
                "model": settings.default_llm_model,
                "base_url": settings.default_llm_base_url,
                "api_key": settings.default_llm_api_key,
                "tier": "standard",
                "description": "后台默认生效模型",
                "enabled": True,
                "active": True,
            }
        ], ensure_ascii=False),
    }


async def _load_config_map(db: AsyncSession) -> dict[str, str]:
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    db_cfg = {r.key: r.value for r in rows}
    return {**_default_config(), **{k: v for k, v in db_cfg.items() if k in CONFIG_KEYS}}


def _bool_str(value) -> str:
    return "true" if str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"} else "false"


def _normalize_config_value(key: str, value) -> str:
    if key == "enable_external_search":
        # Public internet search is hard-disabled for intranet deployment.
        return "false"
    if key in BOOL_KEYS:
        return _bool_str(value)
    if key in INT_LIMITS:
        lo, hi = INT_LIMITS[key]
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(_default_config()[key])
        return str(min(max(parsed, lo), hi))
    if key == "rag_score_threshold":
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            parsed = float(_default_config()[key])
        return str(min(max(parsed, 0.0), 1.0))
    if key == "quality_gate_mode":
        value = str(value or "strict").strip().lower()
        return value if value in {"strict", "warn"} else "strict"
    if key == "model_pool":
        try:
            rows = json.loads(value if isinstance(value, str) else json.dumps(value))
            if not isinstance(rows, list):
                rows = []
            normalized = []
            for idx, item in enumerate(rows):
                if not isinstance(item, dict):
                    continue
                model = str(item.get("model") or "").strip()
                base_url = str(item.get("base_url") or "").strip().rstrip("/")
                if not model or not base_url:
                    continue
                normalized.append({
                    "id": str(item.get("id") or f"model-{idx + 1}").strip(),
                    "name": str(item.get("name") or model).strip(),
                    "model": model,
                    "base_url": base_url,
                    "api_key": str(item.get("api_key") or "").strip(),
                    "tier": str(item.get("tier") or "standard").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "enabled": _bool_str(item.get("enabled", True)) == "true",
                    "active": _bool_str(item.get("active", idx == 0)) == "true",
                })
            if normalized and not any(m.get("active") for m in normalized):
                normalized[0]["active"] = True
            return json.dumps(normalized, ensure_ascii=False)
        except Exception:
            return _default_config()["model_pool"]
    return "" if value is None else str(value)


def _parse_model_pool(cfg: dict[str, str]) -> list[dict]:
    raw = cfg.get("model_pool") or _default_config()["model_pool"]
    try:
        rows = json.loads(raw)
    except Exception:
        rows = []
    if not isinstance(rows, list):
        rows = []
    return [m for m in rows if isinstance(m, dict) and m.get("model") and m.get("base_url")]


def _public_model_pool(cfg: dict[str, str]) -> list[dict]:
    return [
        {k: v for k, v in m.items() if k != "api_key"}
        for m in _parse_model_pool(cfg)
    ]


def _dep(name: str, *, binary: str | None = None, module: str | None = None) -> dict:
    path = shutil.which(binary) if binary else None
    module_found = importlib.util.find_spec(module) is not None if module else None
    ok = bool(path) if binary else bool(module_found)
    if binary and module:
        ok = bool(path) or bool(module_found)
    return {
        "name": name,
        "ok": ok,
        **({"path": path} if path else {}),
        **({"module": module, "module_found": bool(module_found)} if module else {}),
    }


def _capability_status(ok: bool, warn: bool = False) -> str:
    if ok:
        return "ok"
    if warn:
        return "warn"
    return "error"


# ── Config ──────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    cfg = await _load_config_map(db)
    cfg["model_pool_items"] = _public_model_pool(cfg)
    return cfg


@router.put("/config")
async def update_config(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    saved: dict[str, str] = {}
    for key, value in data.items():
        if key not in CONFIG_KEYS:
            continue
        value = _normalize_config_value(key, value)
        saved[key] = value
        row = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
        if row:
            row.value = value
        else:
            db.add(SystemConfig(key=key, value=value, description=f"Admin config: {key}"))
    await db.commit()

    # Refresh in-memory system + LLM config
    from app.services.llm_service import apply_runtime_config
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    all_cfg = {r.key: r.value for r in rows}
    apply_runtime_config(all_cfg)

    return {"message": "配置已保存", "saved": saved}


@router.post("/config/test")
async def test_llm_connection(
    data: dict,
    _: User = Depends(_require_admin),
):
    from app.services.llm_service import check_llm_connection

    base_url = (data.get("llm_base_url") or "").rstrip("/")
    model = data.get("llm_model") or ""
    api_key = data.get("llm_api_key") or "ollama"
    return await check_llm_connection(base_url, api_key, model=model)


@router.get("/model-pool")
async def get_model_pool(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    cfg = await _load_config_map(db)
    return {"items": _parse_model_pool(cfg), "total": len(_parse_model_pool(cfg))}


@router.put("/model-pool")
async def update_model_pool(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    value = _normalize_config_value("model_pool", data.get("items", []))
    row = (await db.execute(select(SystemConfig).where(SystemConfig.key == "model_pool"))).scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(SystemConfig(key="model_pool", value=value, description="Admin config: model_pool"))

    # Sync the active model's credentials into the legacy llm_* keys so every
    # code-path that reads them directly gets the right values immediately.
    try:
        items_list = json.loads(value)
        active = next(
            (m for m in items_list if m.get("active") and m.get("model") and m.get("base_url")),
            next((m for m in items_list if m.get("model") and m.get("base_url")), None),
        )
        if active:
            for llm_key, llm_val in [
                ("llm_base_url", active["base_url"].rstrip("/")),
                ("llm_model",    active["model"]),
                ("llm_api_key",  active.get("api_key") or "ollama"),
            ]:
                llm_row = (await db.execute(select(SystemConfig).where(SystemConfig.key == llm_key))).scalar_one_or_none()
                if llm_row:
                    llm_row.value = llm_val
                else:
                    db.add(SystemConfig(key=llm_key, value=llm_val, description=f"Synced from model_pool"))
    except Exception:
        pass

    await db.commit()
    from app.services.llm_service import apply_runtime_config
    apply_runtime_config({"model_pool": value})
    items = json.loads(value)
    return {"message": "模型池已保存", "items": items, "total": len(items)}


@router.get("/capabilities")
async def admin_capabilities(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Return the real operational capability map for the admin console."""
    cfg = await _load_config_map(db)
    try:
        from app.services.prompt_assets import PPT_TEMPLATE_FILE_MAP, load_ppt_template_path
        bundled_templates = [
            {"name": name, "available": bool(load_ppt_template_path(name))}
            for name in PPT_TEMPLATE_FILE_MAP
        ]
    except Exception:
        bundled_templates = []
    deps = {
        "libreoffice": _dep("LibreOffice/soffice", binary="soffice"),
        "libreoffice_alt": _dep("LibreOffice", binary="libreoffice"),
        "pymupdf": _dep("PyMuPDF", module="fitz"),
        "pdftoppm": _dep("poppler pdftoppm", binary="pdftoppm"),
        "pillow": _dep("Pillow", module="PIL"),
        "openpyxl": _dep("openpyxl", module="openpyxl"),
        "pandas": _dep("pandas", module="pandas"),
    }
    has_office = deps["libreoffice"]["ok"] or deps["libreoffice_alt"]["ok"]
    has_pdf_to_png = deps["pymupdf"]["ok"] or deps["pdftoppm"]["ok"]
    has_render_qa = has_office and has_pdf_to_png and deps["pillow"]["ok"]
    has_excel_stack = deps["openpyxl"]["ok"] and deps["pandas"]["ok"]

    kb_totals = (
        await db.execute(
            select(
                func.count(KnowledgeBase.id),
                func.coalesce(func.sum(KnowledgeBase.doc_count), 0),
                func.coalesce(func.sum(KnowledgeBase.chunk_count), 0),
            )
        )
    ).one()
    indexed_docs = int((await db.execute(
        select(func.count(KBDocument.id)).where(KBDocument.status == "indexed")
    )).scalar() or 0)
    report_status_rows = (
        await db.execute(select(Report.status, func.count(Report.id)).group_by(Report.status))
    ).all()
    status_counts = {row[0] or "unknown": int(row[1] or 0) for row in report_status_rows}

    gate_mode = cfg.get("quality_gate_mode", "strict")
    capabilities = [
        {
            "id": "intranet_deployment",
            "title": "内网部署策略",
            "status": "ok",
            "summary": "公网检索硬禁用；系统依赖上传文件、数据源、离线能力和内网模型服务。",
        },
        {
            "id": "internet_search",
            "title": "联网搜索控制",
            "status": "ok" if cfg.get("enable_external_search") == "false" else "warn",
            "summary": "管理员界面保留开关位，但后端运行时强制返回 false，避免误触公网调用。",
            "effective": False,
        },
        {
            "id": "rag",
            "title": "数据源检索 / RAG",
            "status": "ok" if cfg.get("rag_enabled") == "true" else "warn",
            "summary": f"{int(kb_totals[0] or 0)} 个数据源，{int(kb_totals[1] or 0)} 篇文档，{int(kb_totals[2] or 0)} 个数据块；已索引文档 {indexed_docs} 篇。",
            "config": {
                "top_k": cfg.get("rag_top_k"),
                "chunk_size": cfg.get("rag_chunk_size"),
                "score_threshold": cfg.get("rag_score_threshold"),
                "hybrid_retrieval": cfg.get("rag_hybrid_retrieval") == "true",
                "rerank_enabled": cfg.get("rag_rerank_enabled") == "true",
            },
        },
        {
            "id": "ppt_render_qa",
            "title": "PPT 渲染图像级 QA",
            "status": _capability_status(has_render_qa, warn=True),
            "summary": "LibreOffice + PyMuPDF/poppler + Pillow 均可用时执行真实渲染像素级质检，否则自动降级到几何门禁并写入 warning。",
            "effective": has_render_qa,
        },
        {
            "id": "word_claims",
            "title": "Word 逐 claim 引用核验",
            "status": "ok" if cfg.get("word_claim_gate_required") == "true" else "warn",
            "summary": "导出 DOCX 时抽取数字 claim，按来源注册表匹配数字覆盖、来源锚点和置信度，严重未核验阻断下载。",
        },
        {
            "id": "excel_quality",
            "title": "Excel 数据分析与工作簿 QA",
            "status": _capability_status(has_excel_stack, warn=True),
            "summary": "检查真实 XLSX：Sheet 结构、公式、数值单元格、图表、冻结窗格与数据来源说明。",
            "effective": has_excel_stack,
        },
        {
            "id": "delivery_gate",
            "title": "交付质量门禁",
            "status": "ok" if gate_mode == "strict" else "warn",
            "summary": "strict 模式会阻断严重渲染、引用或工作簿 QA 失败；warn 模式仅放行带风险说明的下载。",
            "mode": gate_mode,
        },
        {
            "id": "generation_pipeline",
            "title": "生成流水线",
            "status": "ok",
            "summary": (
                "统一 7 阶段管线（UNDERSTAND→PLAN→RESEARCH→SPEC_GEN→DOC_RENDER→QA→EXPORT）：支持 "
                "VFS 工程解析、DuckDB 结构化分析、知识三角检索、真实 PPTX 模板 DNA 提取与模板基底渲染；"
                f"内置 PPT 模板 {sum(1 for t in bundled_templates if t.get('available'))}/{len(bundled_templates)} 个可用。"
            ),
            "mode": "unified",
            "templates": bundled_templates,
        },
    ]

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "quality_gate_mode": gate_mode,
            "internet_policy": "intranet_disabled",
            "enable_browser": cfg.get("enable_browser") == "true",
            "rag_enabled": cfg.get("rag_enabled") == "true",
            "pipeline_mode": "unified",
        },
        "dependencies": deps,
        "capabilities": capabilities,
        "operations": {
            "reports_by_status": status_counts,
            "data_sources": {
                "total": int(kb_totals[0] or 0),
                "documents": int(kb_totals[1] or 0),
                "chunks": int(kb_totals[2] or 0),
                "indexed_documents": indexed_docs,
            },
        },
    }


# ── Users ───────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    users = (await db.execute(select(User).order_by(User.created_at.desc()))).scalars().all()
    rows = (
        await db.execute(
            select(
                Report.user_id,
                func.count(Report.id),
                func.max(Report.created_at),
            ).group_by(Report.user_id)
        )
    ).all()
    report_stats = {
        int(user_id): {
            "report_count": int(count or 0),
            "last_report_at": last.isoformat() if last else None,
        }
        for user_id, count, last in rows
        if user_id is not None
    }
    return {"users": [_user_dict(u, report_stats) for u in users], "total": len(users)}


@router.get("/reports")
async def list_admin_reports(
    status_filter: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    query = select(Report, User).join(User, Report.user_id == User.id)
    total_query = select(func.count(Report.id))
    if status_filter:
        query = query.where(Report.status == status_filter)
        total_query = total_query.where(Report.status == status_filter)
    rows = (
        await db.execute(
            query.order_by(Report.created_at.desc(), Report.id.desc()).limit(limit).offset(offset)
        )
    ).all()
    total = int((await db.execute(total_query)).scalar() or 0)
    return {
        "items": [
            {
                "id": report.id,
                "title": report.title,
                "report_type": report.report_type,
                "output_format": report.output_format,
                "status": report.status,
                "progress": report.progress,
                "phase": report.phase,
                "model_id": (report.data_context or {}).get("model_id") if report.data_context else None,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "auth_id": user.auth_id,
                    "department": user.department,
                },
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "completed_at": report.completed_at.isoformat() if report.completed_at else None,
                "error_message": report.error_message,
            }
            for report, user in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/data-sources")
async def list_admin_data_sources(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    rows = (
        await db.execute(
            select(KnowledgeBase, User)
            .outerjoin(User, KnowledgeBase.owner_id == User.id)
            .order_by(KnowledgeBase.updated_at.desc(), KnowledgeBase.id.desc())
        )
    ).all()
    return {
        "items": [
            {
                "id": source.id,
                "name": source.name,
                "description": source.description or "",
                "scope": source.scope,
                "source_type": source.kb_type,
                "doc_count": int(source.doc_count or 0),
                "chunk_count": int(source.chunk_count or 0),
                "total_size": int(source.total_size or 0),
                "embed_model": source.embed_model or "",
                "owner": {
                    "id": owner.id,
                    "username": owner.username,
                    "auth_id": owner.auth_id,
                    "department": owner.department,
                } if owner else None,
                "created_at": source.created_at.isoformat() if source.created_at else None,
                "updated_at": source.updated_at.isoformat() if source.updated_at else None,
            }
            for source, owner in rows
        ],
        "total": len(rows),
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能修改自己的账户状态")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if "role" in data and data["role"] in ("admin", "user"):
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    await db.commit()
    return _user_dict(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账户")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await db.delete(user)
    await db.commit()
    return {"message": "用户已删除"}


# ── System stats ─────────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = int((await db.execute(select(func.count(User.id)))).scalar() or 0)
    active_users = int((await db.execute(select(func.count(User.id)).where(User.is_active == True))).scalar() or 0)
    total_reports = int((await db.execute(select(func.count(Report.id)))).scalar() or 0)
    today_reports = int((await db.execute(
        select(func.count(Report.id)).where(Report.created_at >= today_start)
    )).scalar() or 0)
    total_kb = int((await db.execute(select(func.count(KnowledgeBase.id)))).scalar() or 0)
    total_docs = int((await db.execute(
        select(func.coalesce(func.sum(KnowledgeBase.doc_count), 0))
    )).scalar() or 0)
    total_chunks = int((await db.execute(
        select(func.coalesce(func.sum(KnowledgeBase.chunk_count), 0))
    )).scalar() or 0)

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_reports": total_reports,
        "today_reports": today_reports,
        "total_kb": total_kb,
        "total_docs": total_docs,
        "total_chunks": total_chunks,
    }


@router.get("/audit-logs")
async def admin_audit_logs(
    limit: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Recent operational events for admin review.

    This reuses the existing timeline event store so the console can expose
    quality gates, export QA and workflow events without introducing a new
    migration in the current SQLite deployment.
    """
    rows = (
        await db.execute(
            select(TimelineEvent)
            .where(TimelineEvent.report_id > 0)
            .order_by(TimelineEvent.created_at.desc(), TimelineEvent.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "items": [
            {
                "id": item.id,
                "report_id": item.report_id,
                "event_type": item.event_type,
                "label": item.label,
                "payload": item.payload or {},
                "created_at": item.created_at.isoformat() if item.created_at else None,
            }
            for item in rows
        ],
        "total": len(rows),
    }
