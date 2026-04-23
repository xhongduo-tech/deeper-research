"""
/api/v1/workforce — read-only view of the employee roster + Chief.

The Workforce page on the frontend is *display-only* in v2: users do not
pick employees, Chief does that. But we still want users to browse the
identity cards.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.employees.registry import (
    SUPERVISOR,
    get_employee,
    list_employees,
)
from app.api.v1.deps import AuthContext, get_auth_context
from app.database import get_db
from app.services.llm_service import LLMService


router = APIRouter(prefix="/workforce", tags=["workforce"])


def _serialize(emp: Dict[str, Any], resolved_llm: Dict[str, Any] | None = None) -> Dict[str, Any]:
    model_id = (resolved_llm or {}).get("model") or emp.get("default_model")
    profile_name = (resolved_llm or {}).get("profile_name")
    model_display = (
        f"{profile_name} · {model_id}"
        if profile_name and model_id
        else profile_name or model_id
    )
    return {
        "id": emp["id"],
        "name": emp["name"],
        "first_name_en": emp["first_name_en"],
        "role_title_en": emp["role_title_en"],
        "tagline_en": emp["tagline_en"],
        "portrait_seed": emp["portrait_seed"],
        "category": emp["category"],
        "description": emp["description"],
        "skills": emp.get("skills", []),
        "tools": emp.get("tools", []),
        "applicable_report_types": emp.get("applicable_report_types", []),
        "inputs": emp.get("inputs", []),
        "outputs": emp.get("outputs", []),
        "default_model": model_display,
        "resolved_model_id": model_id,
        "resolved_model_name": profile_name,
        "enabled": emp.get("enabled", True),
        "is_supervisor": emp.get("is_supervisor", False),
    }


@router.get("")
async def list_workforce(
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    roster = list_employees(include_supervisor=False)
    llm_configs = await LLMService(db).get_all_employee_configs(
        [e["id"] for e in [*roster, SUPERVISOR]]
    )
    employees = [_serialize(e, llm_configs.get(e["id"])) for e in roster]
    return {
        "supervisor": _serialize(SUPERVISOR, llm_configs.get(SUPERVISOR["id"])),
        "employees": employees,
    }


@router.get("/{employee_id}")
async def get_one(
    employee_id: str,
    ctx: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    emp = get_employee(employee_id)
    if not emp:
        from fastapi import HTTPException
        raise HTTPException(404, "Employee not found")
    llm_config = await LLMService(db).get_employee_llm_config(employee_id)
    return _serialize(emp, llm_config)
