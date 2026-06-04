"""official_sources.py — REST API for the official data source registry.

GET  /api/v1/official-sources          — list all sources (with optional filters)
POST /api/v1/official-sources/{key}/toggle — admin-only: toggle is_active
"""
from __future__ import annotations

import json
import logging

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
