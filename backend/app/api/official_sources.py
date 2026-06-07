"""official_sources.py — REST API for the official data source registry.

GET  /api/v1/official-sources                  — list all sources (with optional filters)
POST /api/v1/official-sources/{key}/toggle     — admin-only: toggle is_active
GET  /api/v1/official-sources/{key}/preview    — preview connector result (no auth)
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user, get_current_admin
from app.models.official_datasource import OfficialDataSource
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/official-sources", tags=["official-sources"])


def _source_to_dict(src: OfficialDataSource) -> dict:
    """Serialize OfficialDataSource ORM row to a JSON-friendly dict."""
    try:
        domain_tags = json.loads(src.domain_tags or "[]")
    except (ValueError, TypeError):
        domain_tags = []
    try:
        sample_queries = json.loads(src.sample_queries or "[]")
    except (ValueError, TypeError):
        sample_queries = []

    return {
        "key": src.key,
        "name": src.name,
        "description": src.description or "",
        "category": src.category,
        "domain_tags": domain_tags,
        "is_active": src.is_active,
        "source_type": src.source_type,
        "icon_color": src.icon_color,
        "icon_bg": src.icon_bg,
        "sample_queries": sample_queries,
        "coverage": src.coverage,
        "doc_count": src.doc_count,
        "offline_doc_count": src.offline_doc_count or 0,
        "offline_available": src.offline_available,
        "requires_api_key": src.requires_api_key,
        "last_synced_at": src.last_synced_at.isoformat() if src.last_synced_at else None,
        "created_at": src.created_at.isoformat() if src.created_at else None,
    }


@router.get("")
async def list_official_sources(
    category: str | None = Query(None, description="Filter by category"),
    active_only: bool = Query(False, description="Only return active sources"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all registered official data sources."""
    stmt = select(OfficialDataSource).order_by(OfficialDataSource.category, OfficialDataSource.name)
    rows = (await db.execute(stmt)).scalars().all()

    sources = []
    for src in rows:
        if active_only and not src.is_active:
            continue
        if category and src.category != category:
            continue
        sources.append(_source_to_dict(src))

    # Group by category for convenience
    categories: dict[str, list[dict]] = {}
    for src in sources:
        cat = src["category"]
        categories.setdefault(cat, []).append(src)

    return {
        "sources": sources,
        "total": len(sources),
        "categories": list(categories.keys()),
        "by_category": categories,
    }


@router.get("/{key}")
async def get_source_detail(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed info for a single official data source."""
    src = (await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source key '{key}' not found")
    return _source_to_dict(src)


@router.get("/{key}/sample")
async def get_source_sample(
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return up to 3 sample content snippets from the offline KB for this source."""
    from app.models.knowledge_base import KnowledgeBase, KBChunk
    from sqlalchemy import func

    # Find system KBs that match this source key (by name or domain tags)
    # First try exact match on metadata source_keys, then fallback to name similarity
    kbs = (await db.execute(
        select(KnowledgeBase).where(
            (KnowledgeBase.scope == "corp") &
            (KnowledgeBase.name.ilike(f"%{key}%"))
        ).limit(3)
    )).scalars().all()

    if not kbs:
        # Fallback: any corp KB in the same category
        src = (await db.execute(
            select(OfficialDataSource).where(OfficialDataSource.key == key)
        )).scalar_one_or_none()
        if src:
            kbs = (await db.execute(
                select(KnowledgeBase).where(
                    (KnowledgeBase.scope == "corp") &
                    (KnowledgeBase.kb_type.ilike(f"%{src.category[:4]}%"))
                ).limit(3)
            )).scalars().all()

    samples = []
    for kb in kbs:
        chunks = (await db.execute(
            select(KBChunk).where(KBChunk.kb_id == kb.id).limit(3)
        )).scalars().all()
        for chunk in chunks:
            samples.append({
                "kb_id": kb.id,
                "kb_name": kb.name,
                "content": (chunk.content or "")[:500],
            })
        if len(samples) >= 3:
            break

    return {
        "source_key": key,
        "samples": samples[:3],
        "total_kb_matched": len(kbs),
    }


@router.post("/{key}/toggle")
async def toggle_source(
    key: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
):
    """Toggle the is_active flag for a data source (admin only)."""
    result = await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )
    src = result.scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source key '{key}' not found")

    src.is_active = not src.is_active
    await db.commit()
    await db.refresh(src)

    logger.info("[official_sources] %s toggled is_active → %s", key, src.is_active)
    return {"key": src.key, "is_active": src.is_active}


@router.get("/{key}/preview")
async def preview_source(
    key: str,
    q: str | None = Query(None, description="Query string; defaults to first sample_query"),
    db: AsyncSession = Depends(get_db),
):
    """Preview a data source result — calls the connector directly.

    No authentication required (read-only).  Falls back to offline KB chunks
    when the connector returns no data (intranet / offline mode).

    Returns a DataSourceResult-like structure:
      source_key, source_name, result_type, data, row_count, error, offline
    """
    src = (await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source key '{key}' not found")

    # Determine query to use
    if not q:
        try:
            sq = json.loads(src.sample_queries or "[]")
            q = sq[0] if sq else src.name
        except Exception:
            q = src.name

    from app.services.datasource_connectors import get_connector

    connector = get_connector(key)
    start_ms = int(time.time() * 1000)
    offline = False
    error: str | None = None

    try:
        result = await asyncio.wait_for(connector.search(q, limit=5), timeout=8.0)
        latency_ms = int(time.time() * 1000) - start_ms
        if result.error:
            error = result.error

        # If no data returned, try offline KB fallback
        if (not result.data or result.row_count == 0) and src.offline_available:
            kb_result = await _search_offline_kb(db, key, q, limit=5)
            if kb_result:
                offline = True
                return {
                    "source_key": key,
                    "source_name": src.name,
                    "result_type": "text",
                    "data": {"articles": kb_result},
                    "row_count": len(kb_result),
                    "error": error,
                    "offline": True,
                    "latency_ms": latency_ms,
                }

        return {
            "source_key": result.source_key,
            "source_name": result.source_name,
            "result_type": result.result_type,
            "data": result.data,
            "row_count": result.row_count,
            "error": error,
            "offline": offline,
            "latency_ms": latency_ms,
        }

    except (asyncio.TimeoutError, Exception) as exc:
        latency_ms = int(time.time() * 1000) - start_ms
        error = str(exc) if not isinstance(exc, asyncio.TimeoutError) else "连接超时"

        # Fallback to offline KB
        if src.offline_available:
            kb_result = await _search_offline_kb(db, key, q, limit=5)
            if kb_result:
                return {
                    "source_key": key,
                    "source_name": src.name,
                    "result_type": "text",
                    "data": {"articles": kb_result},
                    "row_count": len(kb_result),
                    "error": None,
                    "offline": True,
                    "latency_ms": latency_ms,
                }

        return {
            "source_key": key,
            "source_name": src.name,
            "result_type": "stats",
            "data": {},
            "row_count": 0,
            "error": error,
            "offline": False,
            "latency_ms": latency_ms,
        }


async def _search_offline_kb(
    db: AsyncSession,
    source_key: str,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Simple text-substring search over offline KB chunks for a given source key.

    Since embeddings are not pre-computed for offline chunks (embedding_json=""),
    we use substring matching on chunk content.
    """
    from app.models.knowledge_base import KnowledgeBase, KBChunk
    from sqlalchemy import func

    # Find offline KBs associated with this source via offline_doc_count update trace.
    # We identify them by name prefix 【离线】 and search all chunks for keyword matches.
    offline_kbs = (await db.execute(
        select(KnowledgeBase.id).where(KnowledgeBase.name.like("【离线】%"))
    )).scalars().all()

    if not offline_kbs:
        return []

    # Extract keywords from query (split on Chinese chars + spaces)
    import re
    keywords = [kw.strip() for kw in re.split(r"[\s，。？！、]+", query) if len(kw.strip()) >= 2]
    if not keywords:
        keywords = [query[:10]] if query else []

    # Search chunks with matching content
    matched_chunks: list[tuple[str, str]] = []  # (title, content)
    for kb_id in offline_kbs:
        chunks = (await db.execute(
            select(KBChunk).where(KBChunk.kb_id == kb_id).limit(200)
        )).scalars().all()
        for chunk in chunks:
            content = chunk.content or ""
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                matched_chunks.append((score, content))

    if not matched_chunks:
        return []

    # Sort by relevance score (descending), take top `limit`
    matched_chunks.sort(key=lambda x: x[0], reverse=True)
    return [
        {"title": f"离线数据：{source_key}", "summary": content, "published": "离线预加载"}
        for _, content in matched_chunks[:limit]
    ]
