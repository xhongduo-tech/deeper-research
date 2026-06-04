"""admin_datasources.py — Admin API endpoints for OfficialDataSource configuration.

Endpoints:
  GET    /api/admin/datasources                  — list all official sources
  PUT    /api/admin/datasources/{key}/apikey     — set API key for a source
  DELETE /api/admin/datasources/{key}/apikey     — clear API key
  GET    /api/admin/datasources/{key}/test       — test connector with sample query
"""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_admin
from app.models.official_datasource import OfficialDataSource
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/datasources", tags=["admin-datasources"])


def _require_admin(current_user: User = Depends(get_current_admin)) -> User:
    return current_user


def _source_to_admin_dict(src: OfficialDataSource) -> dict:
    """Serialize source for admin view — masks api_key_value."""
    return {
        "key": src.key,
        "name": src.name,
        "category": src.category,
        "requires_api_key": bool(src.requires_api_key),
        "api_key_name": src.api_key_name or "",
        "has_api_key": bool(src.api_key_value),
        "offline_available": bool(src.offline_available),
        "offline_doc_count": int(src.offline_doc_count or 0),
        "is_active": bool(src.is_active),
    }


@router.get("")
async def list_official_datasources(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """List all official data sources with capability metadata (masked API keys)."""
    rows = (
        await db.execute(
            select(OfficialDataSource).order_by(OfficialDataSource.category, OfficialDataSource.name)
        )
    ).scalars().all()
    return {"sources": [_source_to_admin_dict(src) for src in rows], "total": len(rows)}


@router.put("/{key}/apikey")
async def set_datasource_apikey(
    key: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Save an API key value for a data source."""
    src = (await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Data source '{key}' not found")

    api_key = str(data.get("api_key") or "").strip()
    src.api_key_value = api_key
    await db.commit()

    logger.info("[admin_datasources] API key %s for source '%s'", "set" if api_key else "cleared", key)
    return {
        "key": src.key,
        "has_api_key": bool(src.api_key_value),
        "message": f"API key {'saved' if api_key else 'cleared'} for {src.name}",
    }


@router.delete("/{key}/apikey")
async def clear_datasource_apikey(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Clear the stored API key for a data source."""
    src = (await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Data source '{key}' not found")

    src.api_key_value = ""
    await db.commit()

    logger.info("[admin_datasources] API key cleared for source '%s'", key)
    return {"key": src.key, "has_api_key": False, "message": f"API key cleared for {src.name}"}


@router.get("/{key}/test")
async def test_datasource(
    key: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """Test a data source connector with a sample query.

    Returns latency, success status, and a sample result snippet.
    """
    import json

    src = (await db.execute(
        select(OfficialDataSource).where(OfficialDataSource.key == key)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Data source '{key}' not found")

    # Pick sample query
    try:
        sample_queries: list[str] = json.loads(src.sample_queries or "[]")
    except Exception:
        sample_queries = []
    test_query = sample_queries[0] if sample_queries else src.name

    from app.services.datasource_connectors import get_connector
    connector = get_connector(key)

    start_ms = int(time.time() * 1000)
    try:
        result = await asyncio.wait_for(connector.search(test_query, limit=3), timeout=10.0)
        latency_ms = int(time.time() * 1000) - start_ms
        ok = result.error is None

        # Build a compact sample_result for the response
        sample_result: dict | None = None
        if ok and result.data:
            data = result.data
            rtype = result.result_type
            if rtype in ("table", "financial"):
                cols = data.get("columns", [])
                rows = data.get("rows", [])
                sample_result = {
                    "type": rtype,
                    "columns": cols[:5],
                    "rows": [row[:5] for row in rows[:3]],
                    "row_count": result.row_count,
                }
            elif rtype == "articles":
                arts = data.get("articles", [])[:2]
                sample_result = {
                    "type": rtype,
                    "articles": [
                        {"title": a.get("title", ""), "published": a.get("published", "")}
                        for a in arts
                    ],
                    "row_count": result.row_count,
                }
            else:
                # stats / text — trim to first 3 keys
                sample_result = {
                    "type": rtype,
                    "data": {k: v for k, v in list((data or {}).items())[:3]},
                }

        return {
            "ok": ok,
            "latency_ms": latency_ms,
            "message": result.error or f"返回 {result.row_count} 条数据",
            "sample_result": sample_result,
        }

    except asyncio.TimeoutError:
        latency_ms = int(time.time() * 1000) - start_ms
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "message": "连接超时（10秒）",
            "sample_result": None,
        }
    except Exception as exc:
        latency_ms = int(time.time() * 1000) - start_ms
        logger.warning("[admin_datasources] Test connector %s failed: %s", key, exc)
        return {
            "ok": False,
            "latency_ms": latency_ms,
            "message": str(exc),
            "sample_result": None,
        }
