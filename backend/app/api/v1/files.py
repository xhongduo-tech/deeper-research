import os
import uuid
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import aiofiles

from app.database import get_db
from app.models.user import User
from app.models.uploaded_file import UploadedFile
from app.api.v1.auth import get_current_user
from app.config import settings
from app.tools.file_reader import FileReader

router = APIRouter(prefix="/files", tags=["files"])

file_reader = FileReader()


# --- Schemas ---
class FileResponse(BaseModel):
    id: int
    report_id: Optional[int]
    filename: str
    original_name: str
    file_type: str
    file_size: int
    extracted_text: Optional[str]
    is_template: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    file_id: int
    filename: str
    original_name: str
    file_type: str
    file_size: int
    extracted_text: Optional[str]
    message: str


# --- Routes ---
@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    report_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Save file
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    file_size = len(content)

    # Determine file type
    file_type = _get_file_type(file.filename, file_ext)

    # Extract text content
    try:
        extracted_text = await file_reader.extract_text(file_path, file_type, file.filename)
    except Exception as e:
        extracted_text = f"[文件内容提取失败: {str(e)}]"

    # Save to DB
    db_file = UploadedFile(
        report_id=report_id,
        user_id=current_user.id,
        filename=unique_filename,
        original_name=file.filename,
        file_type=file_type,
        file_path=file_path,
        file_size=file_size,
        extracted_text=extracted_text,
        is_template=False,
    )
    db.add(db_file)
    await db.flush()
    await db.refresh(db_file)

    return FileUploadResponse(
        file_id=db_file.id,
        filename=unique_filename,
        original_name=file.filename,
        file_type=file_type,
        file_size=file_size,
        extracted_text=extracted_text[:2000] if extracted_text else None,
        message="File uploaded and processed successfully",
    )


@router.post("/template", response_model=FileUploadResponse)
async def upload_template(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    os.makedirs(settings.TEMPLATE_DIR, exist_ok=True)

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in [".pptx", ".docx", ".xlsx"]:
        raise HTTPException(
            status_code=400,
            detail="Templates must be .pptx, .docx, or .xlsx files",
        )

    unique_filename = f"template_{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(settings.TEMPLATE_DIR, unique_filename)

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    file_size = len(content)
    file_type = _get_file_type(file.filename, file_ext)

    db_file = UploadedFile(
        report_id=None,
        user_id=current_user.id,
        filename=unique_filename,
        original_name=file.filename,
        file_type=file_type,
        file_path=file_path,
        file_size=file_size,
        extracted_text=None,
        is_template=True,
    )
    db.add(db_file)
    await db.flush()
    await db.refresh(db_file)

    return FileUploadResponse(
        file_id=db_file.id,
        filename=unique_filename,
        original_name=file.filename,
        file_type=file_type,
        file_size=file_size,
        extracted_text=None,
        message="Template uploaded successfully",
    )


@router.get("/templates", response_model=List[FileResponse])
async def list_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all available templates: built-in (user_id=0) + user's own uploads.
    Ordered: built-ins first, then user uploads newest-first.
    """
    query = (
        select(UploadedFile)
        .where(
            UploadedFile.is_template == True,
            (UploadedFile.user_id == 0) | (UploadedFile.user_id == current_user.id),
        )
        .order_by(UploadedFile.user_id.asc(), UploadedFile.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/", response_model=List[FileResponse])
async def list_files(
    report_id: Optional[int] = None,
    is_template: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(UploadedFile).where(UploadedFile.user_id == current_user.id)
    if report_id is not None:
        query = query.where(UploadedFile.report_id == report_id)
    if is_template is not None:
        query = query.where(UploadedFile.is_template == is_template)
    query = query.order_by(UploadedFile.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{file_id}", response_model=FileResponse)
async def get_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == current_user.id,
        )
    )
    db_file = result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == current_user.id,
        )
    )
    db_file = result.scalar_one_or_none()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete physical file
    if os.path.exists(db_file.file_path):
        os.remove(db_file.file_path)

    await db.delete(db_file)
    return {"message": "File deleted successfully"}


def _get_file_type(filename: str, ext: str) -> str:
    type_map = {
        ".pdf": "pdf",
        ".docx": "docx",
        ".doc": "doc",
        ".xlsx": "xlsx",
        ".xls": "xls",
        ".csv": "csv",
        ".pptx": "pptx",
        ".ppt": "ppt",
        ".txt": "txt",
        ".md": "markdown",
        ".json": "json",
        ".xml": "xml",
        ".html": ".html",
        ".htm": "html",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".gif": "image",
        ".bmp": "image",
        ".webp": "image",
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".go": "go",
        ".rs": "rust",
        ".sql": "sql",
        ".sh": "shell",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".ini": "ini",
        ".cfg": "config",
    }
    return type_map.get(ext.lower(), "binary")
