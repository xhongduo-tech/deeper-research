import os
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.uploaded_file import UploadedFile
from app.tools.file_reader import FileReader


class FileService:
    """
    Service for managing uploaded files and extracting their content.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.reader = FileReader()

    async def get_files_for_task(self, task_file_ids: list) -> List[dict]:
        """
        Fetch file metadata and content for a list of file IDs.

        Returns:
            List of {id, name, type, content, path} dicts
        """
        if not task_file_ids:
            return []

        result = await self.db.execute(
            select(UploadedFile).where(UploadedFile.id.in_(task_file_ids))
        )
        files = result.scalars().all()

        file_contexts = []
        for f in files:
            content = f.extracted_text or ""

            # If no extracted text, try to extract now
            if not content and os.path.exists(f.file_path):
                try:
                    content = await self.reader.extract_text(
                        f.file_path, f.file_type, f.original_name
                    )
                    # Update in DB
                    f.extracted_text = content[:50000]
                    await self.db.flush()
                except Exception:
                    content = f"[无法读取文件: {f.original_name}]"

            file_contexts.append({
                "id": f.id,
                "name": f.original_name,
                "type": f.file_type,
                "content": content[:20000],  # Limit per file
                "path": f.file_path,
                "size": f.file_size,
            })

        return file_contexts

    async def get_templates(self, user_id: int) -> List[dict]:
        """Get all templates uploaded by a user."""
        result = await self.db.execute(
            select(UploadedFile).where(
                UploadedFile.user_id == user_id,
                UploadedFile.is_template == True,
            )
        )
        templates = result.scalars().all()
        return [
            {
                "id": t.id,
                "name": t.original_name,
                "type": t.file_type,
                "path": t.file_path,
            }
            for t in templates
        ]

    async def get_file_by_id(self, file_id: int, user_id: int) -> Optional[UploadedFile]:
        """Get a specific file belonging to a user."""
        result = await self.db.execute(
            select(UploadedFile).where(
                UploadedFile.id == file_id,
                UploadedFile.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
