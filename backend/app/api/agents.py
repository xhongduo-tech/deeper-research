from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.report_service import get_agent_list
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    agents = await get_agent_list(db)
    return {"agents": agents, "total": len(agents)}
