"""数据计算 API.

POST /api/compute/duckdb/register   — 将已上传文件注册为 DuckDB 表
POST /api/compute/duckdb/query      — 执行 SQL 或自然语言查询
POST /api/compute/sandbox/run       — 多语言代码执行
POST /api/compute/widget/generate   — 自然语言 → ECharts widget
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.compute.duckdb_engine import DuckDBEngine
from app.compute.polyglot_sandbox import PolyglotSandbox

router = APIRouter(prefix="/api/compute", tags=["compute"])


# ── DuckDB ────────────────────────────────────────────────────────────────────

class DuckDBRegisterReq(BaseModel):
    session_id: str
    file_id: int
    table_name: str | None = None


class DuckDBQueryReq(BaseModel):
    session_id: str
    query: str          # SQL 语句 或 自然语言（nl=True 时）
    nl: bool = False    # True = 自然语言，调 LLM 生成 SQL


@router.post("/duckdb/register")
async def duckdb_register(
    req: DuckDBRegisterReq,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """将已上传的结构化文件（Excel/CSV/Parquet）注册为 DuckDB 内存表."""
    from sqlalchemy import select
    from app.models.uploaded_file import UploadedFile
    from pathlib import Path

    row = (await db.execute(
        select(UploadedFile).where(UploadedFile.id == req.file_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"文件 {req.file_id} 不存在")
    if row.user_id != current_user.id:
        raise HTTPException(403, "无权访问该文件")

    content = Path(row.file_path).read_bytes()
    engine = DuckDBEngine.get_or_create(req.session_id)
    table_name = engine.register_file(row.original_name, content, req.table_name)
    schema_text = engine.table_schema_text()
    sample = engine.sample(table_name, n=3)

    return {
        "session_id": req.session_id,
        "table_name": table_name,
        "schema": schema_text,
        "sample": sample.to_json_records(max_rows=3),
    }


@router.post("/duckdb/query")
async def duckdb_query(
    req: DuckDBQueryReq,
    current_user: User = Depends(get_current_user),
):
    """执行 SQL 查询 或 自然语言 → SQL 查询."""
    engine = DuckDBEngine.get_or_create(req.session_id)
    if not engine._tables:
        raise HTTPException(400, "该 session 尚未注册任何数据表，请先调用 /duckdb/register")

    if req.nl:
        result = await engine.nl_query(req.query)
    else:
        result = engine.execute(req.query)

    if result.error:
        return {"success": False, "error": result.error, "sql": result.sql}

    return {
        "success": True,
        "sql": result.sql,
        "columns": result.columns,
        "rows": result.to_json_records(),
        "row_count": result.row_count,
        "exec_ms": result.exec_ms,
        "markdown": result.to_markdown(max_rows=30),
    }


# ── Polyglot Sandbox ──────────────────────────────────────────────────────────

class SandboxRunReq(BaseModel):
    code: str
    language: str = "python"
    timeout: int | None = None
    env_vars: dict[str, str] | None = None


@router.post("/sandbox/run")
async def sandbox_run(
    req: SandboxRunReq,
    current_user: User = Depends(get_current_user),
):
    """在多语言沙箱中执行代码."""
    if len(req.code) > 50000:
        raise HTTPException(400, "代码长度超过限制（50KB）")

    result = await PolyglotSandbox.run(
        req.code,
        req.language,
        timeout=req.timeout,
        env_vars=req.env_vars,
    )
    return {
        "success": result.success,
        "language": result.language,
        "stdout": result.stdout[:10000],
        "stderr": result.stderr[:5000],
        "error": result.error,
        "exec_ms": result.exec_ms,
        "figures": result.figures,
    }


# ── Widget 生成器 ─────────────────────────────────────────────────────────────

class WidgetGenReq(BaseModel):
    question: str
    records: list[dict]
    title: str = ""


@router.post("/widget/generate")
async def widget_generate(
    req: WidgetGenReq,
    current_user: User = Depends(get_current_user),
):
    """从自然语言 + 数据记录生成可交互 ECharts iframe widget."""
    from app.rendering.widget_renderer import WidgetRenderer

    if not req.records:
        raise HTTPException(400, "records 不能为空")

    iframe_html = await WidgetRenderer.generate_from_nl(
        question=req.question,
        records=req.records,
        title=req.title,
    )
    if not iframe_html:
        raise HTTPException(500, "Widget 生成失败，请检查 LLM 配置")

    return {"html": iframe_html}
