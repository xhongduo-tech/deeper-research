"""admin_bulk.py — Admin API for the offline bulk-import pipeline.

This is the **admin lane** for sinking massive offline corpora (~2TB across
finance / banking / gov reports / policy / news / papers / code / math …) into
the Vector RAG knowledge base. It does NOT accept browser uploads — the corpus
is placed on the server filesystem (or MinIO mount) as a `kb_sources/` tree and
ingested by `BulkImporter`, which is resumable and incremental.

Endpoints:
  GET  /api/admin/bulk-import/scan    — preview the kb_sources/ tree (no writes)
  POST /api/admin/bulk-import/run     — launch BulkImporter in the background
  GET  /api/admin/bulk-import/status  — running flag + progress + last summary
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.middleware.auth_middleware import get_current_admin
from app.models.user import User
from app.services.bulk_importer import BulkImporter, ProgressTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/bulk-import", tags=["admin-bulk-import"])

_DOC_EXTS = {".md", ".txt", ".markdown"}

# Module-level run state (single concurrent import; survives across requests)
_run_state: dict = {
    "running": False,
    "source_dir": "",
    "started_at": None,
    "finished_at": None,
    "last_summary": None,
    "error": None,
}


def _default_source_dir() -> str:
    base = getattr(settings, "data_dir", None) or "./data"
    return str(Path(base) / "kb_sources")


class BulkRunRequest(BaseModel):
    source_dir: str | None = None


@router.get("/scan")
async def scan_source_dir(
    source_dir: str | None = None,
    current_user: User = Depends(get_current_admin),
):
    """Preview the kb_sources/ tree without ingesting anything.

    Returns one entry per KB sub-directory: name, declared metadata, and the
    count/size of ingestable document files.
    """
    root = Path(source_dir or _default_source_dir())
    if not root.exists():
        return {
            "source_dir": str(root),
            "exists": False,
            "kb_dirs": [],
            "hint": "目录不存在。请将语料按 kb_sources/kb_XXX_域名/ 结构放置（每个子目录含 metadata.json 与 .md/.txt 文档），再扫描。",
        }

    import json
    kb_dirs = []
    total_files = 0
    total_bytes = 0
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        meta = {}
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        files = [f for f in d.iterdir() if f.is_file() and f.suffix.lower() in _DOC_EXTS]
        size = sum(f.stat().st_size for f in files)
        total_files += len(files)
        total_bytes += size
        kb_dirs.append({
            "dir": d.name,
            "name": meta.get("name", d.name),
            "kb_type": meta.get("kb_type", "general"),
            "has_metadata": meta_path.exists(),
            "file_count": len(files),
            "size_mb": round(size / 1024 / 1024, 1),
        })

    return {
        "source_dir": str(root),
        "exists": True,
        "kb_dirs": kb_dirs,
        "total_kb": len(kb_dirs),
        "total_files": total_files,
        "total_size_mb": round(total_bytes / 1024 / 1024, 1),
    }


@router.post("/run")
async def run_bulk_import(
    req: BulkRunRequest,
    current_user: User = Depends(get_current_admin),
):
    """Launch the bulk importer in the background. Idempotent / resumable.

    Returns immediately; poll /status for progress. Refuses to start a second
    concurrent run.
    """
    if _run_state["running"]:
        raise HTTPException(409, "已有批量入库任务在运行，请等待其完成或查看 /status")

    source_dir = req.source_dir or _default_source_dir()
    root = Path(source_dir)
    if not root.exists():
        raise HTTPException(404, f"源目录不存在: {source_dir}")

    async def _job():
        from datetime import datetime, timezone
        _run_state.update({
            "running": True,
            "source_dir": str(root),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "error": None,
        })
        try:
            importer = BulkImporter()
            summary = await importer.run(root)
            _run_state["last_summary"] = summary
        except Exception as exc:
            logger.exception("[bulk-import] run failed")
            _run_state["error"] = str(exc)
        finally:
            from datetime import datetime, timezone
            _run_state["running"] = False
            _run_state["finished_at"] = datetime.now(timezone.utc).isoformat()

    asyncio.create_task(_job())
    logger.info("[bulk-import] launched for %s", root)
    return {"status": "started", "source_dir": str(root)}


@router.get("/status")
async def bulk_import_status(
    current_user: User = Depends(get_current_admin),
):
    """Return running flag + persisted progress (resumable checkpoint) + last summary."""
    tracker = ProgressTracker()
    return {
        "running": _run_state["running"],
        "source_dir": _run_state["source_dir"],
        "started_at": _run_state["started_at"],
        "finished_at": _run_state["finished_at"],
        "last_summary": _run_state["last_summary"],
        "error": _run_state["error"],
        "checkpoint": tracker.stats(),  # {files_processed, chunks_ingested, last_updated}
    }
