"""统一接入网关 API.

POST /api/ingress/upload    — 上传任意文件（含 .zip/.tar.gz），返回解析资产摘要
POST /api/ingress/vfs/tree  — 返回 VFS 目录树（已上传的 zip 包）
GET  /api/ingress/asset/{file_id}  — 按路径获取 VFS 中某文件的解析内容
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.models.uploaded_file import UploadedFile as UploadedFileModel
from app.ingress.vfs import VirtualFileSystem
from app.ingress.dispatcher import IngressDispatcher

router = APIRouter(prefix="/api/ingress", tags=["ingress"])

_VFS_STORE: dict[str, VirtualFileSystem] = {}   # file_id → VFS（内存缓存）

_ARCHIVE_EXTS = {".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar"}


@router.post("/upload")
async def ingest_upload(
    file: UploadFile = File(...),
    report_id: int | None = Form(None),
    is_template: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """接收任意文件/压缩包，解析并返回标准化资产摘要.

    支持:
      - 普通文件（.pdf/.docx/.xlsx/.py/.java/...）
      - 压缩包（.zip/.tar.gz）→ 自动构建 VFS，解析所有内部文件
    """
    filename = file.filename or "upload"
    content = await file.read()

    # 保存原始文件
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = "".join(Path(filename).suffixes)[-10:] or ""
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = upload_dir / safe_name
    file_path.write_bytes(content)

    # 入库
    db_file = UploadedFileModel(
        report_id=report_id,
        user_id=current_user.id,
        filename=safe_name,
        original_name=filename,
        file_type=suffix.lstrip("."),
        file_path=str(file_path),
        file_size=len(content),
        is_template=is_template,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    # 构建 VFS
    vfs = VirtualFileSystem.from_bytes(filename, content)
    _VFS_STORE[str(db_file.id)] = vfs

    # 分发解析
    assets = await IngressDispatcher.dispatch_vfs(vfs)

    # 资产摘要列表
    asset_summaries = [
        {
            "path": a.path,
            "type": a.asset_type,
            "language": a.language,
            "size_bytes": a.size_bytes,
            "summary": a.summary[:300],
        }
        for a in assets
    ]

    return {
        "file_id": db_file.id,
        "filename": filename,
        "vfs_summary": vfs.summary(),
        "directory_tree": vfs.directory_tree()[:2000],
        "assets": asset_summaries,
        "total_assets": len(assets),
    }


@router.get("/vfs/{file_id}/tree")
async def get_vfs_tree(
    file_id: str,
    current_user: User = Depends(get_current_user),
):
    """返回已上传 zip 包的 VFS 目录树."""
    vfs = _VFS_STORE.get(file_id)
    if not vfs:
        raise HTTPException(404, "VFS 未找到，请重新上传文件")
    return {
        "file_id": file_id,
        "tree": vfs.directory_tree(),
        "summary": vfs.summary(),
    }


@router.get("/vfs/{file_id}/file")
async def get_vfs_file(
    file_id: str,
    path: str,
    current_user: User = Depends(get_current_user),
):
    """获取 VFS 中某个文件的解析内容."""
    vfs = _VFS_STORE.get(file_id)
    if not vfs:
        raise HTTPException(404, "VFS 未找到")
    node = vfs.get_file(path)
    if not node:
        raise HTTPException(404, f"文件路径不存在: {path}")

    assets = await IngressDispatcher.dispatch_node(node)
    if not assets:
        raise HTTPException(422, "无法解析该文件类型")

    return {
        "path": path,
        "type": assets.asset_type,
        "language": assets.language,
        "context_text": assets.context_text[:5000],
        "summary": assets.summary[:500],
    }
