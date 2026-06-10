import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.uploaded_file import UploadedFile as UploadedFileModel
from app.schemas.file import FileUploadResponse
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/files", tags=["files"])

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".txt", ".csv", ".md", ".json", ".png", ".jpg", ".jpeg",
}


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    report_id: int | None = Form(None),
    is_template: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ext}"
    file_path = upload_dir / safe_name

    content = await file.read()
    file_path.write_bytes(content)

    db_file = UploadedFileModel(
        report_id=report_id,
        user_id=current_user.id,
        filename=safe_name,
        original_name=file.filename or "unknown",
        file_type=ext.lstrip("."),
        file_path=str(file_path),
        file_size=len(content),
        is_template=is_template,
    )
    db.add(db_file)
    await db.commit()
    await db.refresh(db_file)

    return db_file


@router.get("")
async def list_files(
    report_id: int | None = None,
    templates_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select
    query = select(UploadedFileModel).where(UploadedFileModel.user_id == current_user.id)
    if report_id:
        query = query.where(UploadedFileModel.report_id == report_id)
    if templates_only:
        query = query.where(UploadedFileModel.is_template == True)
    query = query.order_by(UploadedFileModel.created_at.desc())

    result = await db.execute(query)
    files = result.scalars().all()
    return {
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "original_name": f.original_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "report_id": f.report_id,
                "is_template": f.is_template,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in files
        ]
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UploadedFileModel).where(
            UploadedFileModel.id == file_id,
            UploadedFileModel.user_id == current_user.id,
        )
    )
    db_file = result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在或无权删除")

    try:
        if db_file.file_path and os.path.exists(db_file.file_path):
            os.remove(db_file.file_path)
    except OSError:
        pass

    await db.delete(db_file)
    await db.commit()
    return {"message": "文件已删除", "id": file_id}
