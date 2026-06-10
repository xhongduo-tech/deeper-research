"""Project management API."""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str
    status: str
    owner_id: int | None
    created_at: str | None
    updated_at: str | None

    class Config:
        from_attributes = True


def _project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description or "",
        "status": p.status,
        "owner_id": p.owner_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


# ── CRUD ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List projects for the current user."""
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .where(Project.status == "active")
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return {"items": [_project_to_dict(p) for p in projects], "total": len(projects)}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project."""
    project = Project(
        name=data.name,
        description=data.description,
        owner_id=current_user.id,
        status="active",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_to_dict(project)


@router.get("/{project_id}")
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get project details including associated knowledge bases."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.owner_id == current_user.id)
        .options(selectinload(Project.knowledge_bases))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        **_project_to_dict(project),
        "knowledge_bases": [
            {
                "id": kb.id,
                "name": kb.name,
                "kb_type": kb.kb_type,
                "doc_count": kb.doc_count,
                "chunk_count": kb.chunk_count,
            }
            for kb in project.knowledge_bases
        ],
    }


@router.put("/{project_id}")
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.status is not None:
        project.status = data.status

    await db.commit()
    await db.refresh(project)
    return _project_to_dict(project)


@router.delete("/{project_id}")
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a project by setting status to 'deleted'."""
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project.status = "deleted"
    await db.commit()
    return {"ok": True}


# ── Project Knowledge Bases ─────────────────────────────────────────────────

@router.get("/{project_id}/kbs")
async def list_project_kbs(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List knowledge bases associated with a project."""
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.project_id == project_id)
        .where(KnowledgeBase.owner_id == current_user.id)
        .order_by(KnowledgeBase.created_at.desc())
    )
    kbs = result.scalars().all()
    return {
        "items": [
            {
                "id": kb.id,
                "name": kb.name,
                "kb_type": kb.kb_type,
                "doc_count": kb.doc_count,
                "chunk_count": kb.chunk_count,
                "total_size": kb.total_size,
                "created_at": kb.created_at.isoformat() if kb.created_at else None,
            }
            for kb in kbs
        ],
        "total": len(kbs),
    }


@router.post("/{project_id}/kbs", status_code=status.HTTP_201_CREATED)
async def create_project_kb(
    project_id: int,
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a knowledge base under a project."""
    from app.services import rag_service

    # Verify project ownership
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.owner_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    kb = await rag_service.create_kb(
        db,
        name=data.name,
        description=data.description,
        scope="personal",
        kb_type="general",
        owner_id=current_user.id,
    )
    kb.project_id = project_id
    await db.commit()
    await db.refresh(kb)

    return {
        "id": kb.id,
        "name": kb.name,
        "kb_type": kb.kb_type,
        "doc_count": kb.doc_count,
        "chunk_count": kb.chunk_count,
        "project_id": kb.project_id,
    }
