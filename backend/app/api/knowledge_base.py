"""Knowledge Base management API."""
import logging
import tempfile
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.models.knowledge_base import KnowledgeBase, KBDocument
from app.services import rag_service
from app.services.file_parser import extract_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


# ── Schemas ────────────────────────────────────────────────────────────────

class KBCreate(BaseModel):
    name: str
    description: str = ""
    scope: str = "personal"
    kb_type: str = "general"


class KBSearchRequest(BaseModel):
    query: str
    top_k: int = 8
    score_threshold: float = 0.15


# ── Public system KB listing (no auth required) ────────────────────────────

@router.get("/system")
async def list_system_kbs(
    kb_type: str | None = Query(None, description="Filter by kb_type"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all corp-scope (system) knowledge bases with real-time doc/size stats.
    Public endpoint — no authentication required.
    """
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.name,
            KnowledgeBase.description,
            KnowledgeBase.kb_type,
            KnowledgeBase.embed_model,
            KnowledgeBase.created_at,
            # real-time doc count
            func.count(KBDocument.id).label("real_doc_count"),
            # real-time total size
            func.coalesce(func.sum(KBDocument.file_size), 0).label("real_total_size"),
        )
        .outerjoin(KBDocument, KBDocument.kb_id == KnowledgeBase.id)
        .where(KnowledgeBase.scope == "corp")
        .group_by(KnowledgeBase.id)
        .order_by(func.count(KBDocument.id).desc())
    )
    if kb_type:
        stmt = stmt.where(KnowledgeBase.kb_type == kb_type)

    rows = (await db.execute(stmt)).all()

    type_labels = {
        "general": "通用", "policy": "政策法规", "research": "研究报告",
        "finance": "金融数据", "tech": "技术文档", "news": "新闻舆情",
        "academic": "学术论文", "code": "代码工程", "math": "数学知识",
        "statistics": "统计数据", "law": "法律法规", "trade": "贸易数据",
        "gov": "政府报告", "banking": "银行年报", "meeting": "会议纪要",
    }

    items = []
    for r in rows:
        size_mb = round((r.real_total_size or 0) / 1024 / 1024, 1)
        items.append({
            "id": r.id,
            "name": r.name,
            "description": r.description or "",
            "scope": "corp",
            "kb_type": r.kb_type or "general",
            "type_label": type_labels.get(r.kb_type or "general", r.kb_type or "general"),
            "doc_count": r.real_doc_count,
            "chunk_count": 0,          # vectors in Qdrant, not SQLite
            "total_size": r.real_total_size or 0,
            "size_display": f"{size_mb} MB" if size_mb >= 0.1 else f"{r.real_total_size or 0} B",
            "embed_model": r.embed_model or "",
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    total_docs = sum(i["doc_count"] for i in items)
    total_size = sum(i["total_size"] for i in items)

    return {
        "items": items,
        "total": len(items),
        "total_docs": total_docs,
        "total_size": total_size,
        "size_display": f"{round(total_size / 1024 / 1024, 1)} MB",
    }


# ── KB CRUD ────────────────────────────────────────────────────────────────

@router.get("")
async def list_knowledge_bases(
    scope: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Admins can pass scope=all to see every KB; regular users see only their own.
    owner_id = None if (current_user.role == "admin" and scope == "all") else current_user.id
    kbs = await rag_service.list_kbs(db, owner_id=owner_id)
    return {"items": [_kb_to_dict(kb) for kb in kbs], "total": len(kbs)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KBCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    kb = await rag_service.create_kb(
        db,
        name=data.name,
        description=data.description,
        scope=data.scope,
        kb_type=data.kb_type,
        owner_id=current_user.id,
    )
    return _kb_to_dict(kb)


@router.get("/{kb_id}")
async def get_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.knowledge_base import KnowledgeBase
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return _kb_to_dict(kb)


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可删除知识库")
    ok = await rag_service.delete_kb(db, kb_id)
    if not ok:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return {"message": "已删除"}


# ── Documents ──────────────────────────────────────────────────────────────

@router.get("/{kb_id}/documents")
async def list_documents(
    kb_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await rag_service.list_kb_documents(db, kb_id)
    return {"items": [_doc_to_dict(d) for d in docs], "total": len(docs)}


@router.post("/{kb_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file and ingest it into the knowledge base."""
    from app.models.knowledge_base import KnowledgeBase
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    content_bytes = await file.read()
    file_size = len(content_bytes)

    suffix = (file.filename or "txt").rsplit(".", 1)[-1].lower()

    # Write to temp file for file_parser / structured_data_service (both need a path)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as tmp:
            tmp.write(content_bytes)
            tmp_path = tmp.name

        # ── Structured data path (Excel / CSV) ────────────────────────────────
        from app.services.structured_data_service import is_structured_file, get_structured_data_service
        if is_structured_file(file.filename or ""):
            sds = get_structured_data_service()
            # Also ingest a text preview into RAG so the doc appears in the KB listing
            try:
                text = await extract_text(tmp_path, suffix)
            except Exception:
                text = f"[结构化数据文件: {file.filename}]"
            doc = await rag_service.ingest_document(
                db,
                kb_id=kb_id,
                title=file.filename or "未命名表格",
                content=text or f"[结构化数据文件: {file.filename}]",
                file_type=suffix,
                file_size=file_size,
            )
            # Load the actual table into DuckDB
            try:
                table_meta = sds.ingest_file(
                    kb_id=str(kb_id),
                    doc_id=str(doc.id),
                    file_path=tmp_path,
                    file_name=file.filename or "data",
                )
                doc_dict = _doc_to_dict(doc)
                doc_dict["structured"] = True
                doc_dict["table_name"] = table_meta["table_name"]
                doc_dict["row_count"] = table_meta["row_count"]
                doc_dict["columns"] = table_meta["columns"]
                return doc_dict
            except Exception as e:
                # Non-fatal: RAG doc already created, just log the DuckDB failure
                import logging
                logging.getLogger(__name__).warning("DuckDB ingest failed for %s: %s", file.filename, e)
                return _doc_to_dict(doc)

        # ── Standard RAG path (PDF, DOCX, TXT, …) ────────────────────────────
        try:
            text = await extract_text(tmp_path, suffix)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"文件解析失败: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    if not text.strip():
        raise HTTPException(status_code=422, detail="无法从文件中提取文本内容")

    doc = await rag_service.ingest_document(
        db,
        kb_id=kb_id,
        title=file.filename or "未命名文档",
        content=text,
        file_type=suffix,
        file_size=file_size,
    )
    return _doc_to_dict(doc)


@router.post("/{kb_id}/documents/text", status_code=status.HTTP_201_CREATED)
async def upload_text_document(
    kb_id: int,
    title: str = Form(...),
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Directly ingest plain text into the knowledge base."""
    from app.models.knowledge_base import KnowledgeBase
    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    doc = await rag_service.ingest_document(
        db,
        kb_id=kb_id,
        title=title,
        content=content,
        file_type="text",
        file_size=len(content.encode()),
    )
    return _doc_to_dict(doc)


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = await rag_service.delete_document(db, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "已删除"}


# ── Structured Data Query ──────────────────────────────────────────────────

class KBQueryRequest(BaseModel):
    query: str
    nl: bool = True   # True = 自然语言，False = 直接 SQL


@router.post("/{kb_id}/query")
async def query_kb_structured(
    kb_id: int,
    req: KBQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对知识库中的结构化数据表执行查询（自然语言 → SQL 或直接 SQL）."""
    from app.models.knowledge_base import KnowledgeBase
    from app.services.structured_data_service import get_structured_data_service

    kb = await db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问该知识库")

    sds = get_structured_data_service()

    if req.nl:
        result = await sds.nl_query(str(kb_id), req.query)
        return result
    else:
        try:
            rows = sds.execute_query(str(kb_id), req.query)
            return {"success": True, "sql": req.query, "rows": rows, "row_count": len(rows)}
        except Exception as e:
            return {"success": False, "error": str(e), "sql": req.query}


# ── Search ─────────────────────────────────────────────────────────────────

@router.post("/{kb_id}/search")
async def search_knowledge_base(
    kb_id: int,
    req: KBSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await rag_service.search_kb(
        db,
        kb_ids=[kb_id],
        query=req.query,
        top_k=req.top_k,
        score_threshold=req.score_threshold,
    )
    return {"query": req.query, "results": results, "total": len(results)}


@router.post("/search/multi")
async def search_multiple_kbs(
    req: KBSearchRequest,
    kb_ids: list[int] = [],
    include_system: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Search across multiple KBs. If include_system is true, also search all corp-scope KBs."""
    all_kb_ids = list(kb_ids)
    if include_system:
        from app.models.knowledge_base import KnowledgeBase
        from sqlalchemy import select
        system_kbs = (await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.scope == "corp")
        )).scalars().all()
        all_kb_ids.extend([k for k in system_kbs if k not in all_kb_ids])

    results = await rag_service.search_kb(
        db,
        kb_ids=all_kb_ids,
        query=req.query,
        top_k=req.top_k,
        score_threshold=req.score_threshold,
    )
    return {"query": req.query, "results": results, "total": len(results), "kb_ids_searched": all_kb_ids}


# ── Response formatters ────────────────────────────────────────────────────

def _kb_to_dict(kb) -> dict:
    scope_labels = {"personal": "个人", "dept": "部门", "team": "团队", "corp": "全公司"}
    type_labels = {
        "general": "通用", "policy": "政策法规", "research": "研究报告",
        "contract": "合同法务", "finance": "金融数据", "tech": "技术文档",
        "meeting": "会议纪要", "banking": "银行年报", "news": "新闻舆情",
        "academic": "学术论文", "code": "代码工程", "math": "数学知识",
        "gov": "政府报告", "statistics": "统计数据",
    }
    size_mb = round((kb.total_size or 0) / 1024 / 1024, 1)
    return {
        "id": kb.id,
        "name": kb.name,
        "description": kb.description,
        "scope": kb.scope,
        "scope_label": scope_labels.get(kb.scope, kb.scope),
        "kb_type": kb.kb_type,
        "type_label": type_labels.get(kb.kb_type, kb.kb_type),
        "doc_count": kb.doc_count or 0,
        "chunk_count": kb.chunk_count or 0,
        "total_size": kb.total_size or 0,
        "size_display": f"{size_mb} MB" if size_mb >= 0.1 else f"{kb.total_size or 0} B",
        "embed_model": kb.embed_model or "",
        "owner_id": kb.owner_id,
        "created_at": kb.created_at.isoformat() if kb.created_at else None,
        "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
    }


def _doc_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "kb_id": doc.kb_id,
        "title": doc.title,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "content_preview": doc.content_preview,
        "chunk_count": doc.chunk_count or 0,
        "status": doc.status,
        "error_msg": doc.error_msg or "",
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
