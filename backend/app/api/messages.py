from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.services.orchestrator import add_message
from app.services.report_service import get_report_messages, get_report_detail
from app.middleware.auth_middleware import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/reports/{report_id}/messages", tags=["messages"])


@router.get("", response_model=list[MessageResponse])
async def list_messages(
    report_id: int,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(404, detail="报告不存在")
    if report.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, detail="无权访问")

    messages = await get_report_messages(db, report_id, limit)
    return messages


@router.post("", response_model=MessageResponse, status_code=201)
async def send_message(
    report_id: int,
    data: MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = await get_report_detail(db, report_id)
    if not report:
        raise HTTPException(404, detail="报告不存在")
    if report.user_id != current_user.id:
        raise HTTPException(403, detail="无权访问")

    msg = await add_message(
        db, report_id, "user", data.content,
        author_id=str(current_user.id),
        author_name=current_user.username,
    )
    return msg
