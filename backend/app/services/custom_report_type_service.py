"""
CustomReportTypeService — handles user-defined report templates.

Flow:
  1) user submits {label, description, visibility}  →  status = "draft"
     LLM is invoked to propose an improved description, section skeleton
     and a default team roster. User sees a draft preview.
  2) user confirms (optionally tweaks)  →  status = "active".
  3) when creating a report with report_type = "custom:<id>" the system
     adapts the normal scoping / production pipeline to use this template.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.employees.registry import EMPLOYEES
from app.models.custom_report_type import CustomReportType
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


CUSTOM_PREFIX = "custom:"


def _fallback_skeleton(label: str) -> List[Dict[str, str]]:
    return [
        {"id": "background", "title": "背景与目标", "kind": "narrative"},
        {"id": "method", "title": "分析方法与数据来源", "kind": "narrative"},
        {"id": "findings", "title": "核心发现", "kind": "narrative_with_chart"},
        {"id": "details", "title": "分项详述", "kind": "table_with_narrative"},
        {"id": "recommendations", "title": "结论与建议", "kind": "narrative"},
    ]


def _fallback_team() -> List[str]:
    return [
        "intake_officer",
        "material_analyst",
        "structured_writer",
        "qa_reviewer",
        "layout_designer",
    ]


def serialize(rt: CustomReportType) -> Dict[str, Any]:
    return {
        "id": f"{CUSTOM_PREFIX}{rt.id}",
        "raw_id": rt.id,
        "user_id": rt.user_id,
        "label": rt.label,
        "label_en": "Custom",
        "description": rt.improved_description or rt.description,
        "original_description": rt.description,
        "visibility": rt.visibility,
        "status": rt.status,
        "typical_output": rt.typical_output or "Word 报告",
        "typical_inputs": [],
        "section_skeleton": list(rt.section_skeleton or []),
        "default_team": list(rt.default_team or []),
        "is_custom": True,
        "created_at": rt.created_at.isoformat() if rt.created_at else None,
        "updated_at": rt.updated_at.isoformat() if rt.updated_at else None,
    }


class CustomReportTypeService:
    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_report_type_id(report_type: str) -> Optional[int]:
        if not report_type or not report_type.startswith(CUSTOM_PREFIX):
            return None
        try:
            return int(report_type[len(CUSTOM_PREFIX):])
        except Exception:
            return None

    @staticmethod
    async def get(db: AsyncSession, raw_id: int) -> Optional[CustomReportType]:
        result = await db.execute(
            select(CustomReportType).where(CustomReportType.id == raw_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_for_user(
        db: AsyncSession, user_id: int
    ) -> List[CustomReportType]:
        # Show owner's types + all public types.
        stmt = (
            select(CustomReportType)
            .where(
                (CustomReportType.user_id == user_id)
                | (CustomReportType.visibility == "public")
            )
            .order_by(CustomReportType.created_at.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def as_registry_entry(
        db: AsyncSession, raw_id: int
    ) -> Optional[Dict[str, Any]]:
        rt = await CustomReportTypeService.get(db, raw_id)
        if not rt or rt.status != "active":
            return None
        return {
            "id": f"{CUSTOM_PREFIX}{rt.id}",
            "label": rt.label,
            "label_en": "Custom",
            "description": rt.improved_description or rt.description,
            "typical_inputs": [],
            "typical_output": rt.typical_output or "Word 报告",
            "default_team": list(rt.default_team or _fallback_team()),
            "section_skeleton": list(
                rt.section_skeleton or _fallback_skeleton(rt.label)
            ),
        }

    # ------------------------------------------------------------------
    # Create / improve / confirm
    # ------------------------------------------------------------------

    @classmethod
    async def create_and_improve(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        label: str,
        description: str,
        visibility: str = "private",
    ) -> CustomReportType:
        label = (label or "").strip() or "自定义报告"
        description = (description or "").strip()
        visibility = "public" if visibility == "public" else "private"

        rt = CustomReportType(
            user_id=user_id,
            label=label[:200],
            description=description,
            visibility=visibility,
            status="draft",
            section_skeleton=_fallback_skeleton(label),
            default_team=_fallback_team(),
            typical_output="Word 报告",
        )
        db.add(rt)
        await db.flush()
        await db.refresh(rt)

        # Best-effort LLM improvement. Falls back to the seed skeleton.
        try:
            improved = await cls._improve_with_llm(label, description)
            if improved:
                rt.improved_description = improved.get("improved_description") or description
                rt.typical_output = improved.get("typical_output") or rt.typical_output
                if improved.get("section_skeleton"):
                    rt.section_skeleton = improved["section_skeleton"]
                if improved.get("default_team"):
                    rt.default_team = improved["default_team"]
                await db.flush()
        except Exception:
            logger.exception("LLM improvement failed for custom report type")

        return rt

    @classmethod
    async def _improve_with_llm(
        cls, label: str, description: str
    ) -> Optional[Dict[str, Any]]:
        roster_desc = "\n".join(
            f"- {e['id']} · {e['first_name_en']} ({e['role_title_en']})"
            for e in EMPLOYEES
        )
        sys_prompt = (
            "你是报告模板设计师。根据用户输入的报告类型名称与需求，"
            "产出一份专业的模板骨架。输出严格 JSON，字段：\n"
            '{\n'
            '  "improved_description": "<精炼的需求描述，2-3 句话，中文>",\n'
            '  "typical_output": "<典型输出，例如 Word 报告>",\n'
            '  "section_skeleton": [{"id":"<英文 id>","title":"<中文章节名>",'
            '"kind":"<narrative|narrative_with_chart|table_with_narrative|matrix|qa_list|evidence_list>"}],\n'
            '  "default_team": ["<employee_id>", ...]\n'
            "}\n"
            f"可用员工只能从以下 roster 里选：\n{roster_desc}\n"
            "章节不超过 8 个；不要输出代码围栏。"
        )
        user_prompt = f"报告类型名称：{label}\n用户需求：\n{description or '（未提供额外需求）'}"

        try:
            raw = await asyncio.wait_for(
                LLMService().chat(
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1200,
                ),
                timeout=45.0,
            )
        except Exception as e:
            logger.warning("Custom RT LLM failed: %s", e)
            return None

        if not raw:
            return None
        s = raw.strip()
        if s.startswith("```"):
            s = s.strip("`")
            nl = s.find("\n")
            if nl >= 0:
                s = s[nl + 1:]
            s = s.rstrip("`").strip()
        try:
            obj = json.loads(s)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None

        valid_ids = {e["id"] for e in EMPLOYEES}
        team = [eid for eid in (obj.get("default_team") or []) if eid in valid_ids]
        outline: List[Dict[str, str]] = []
        for s in (obj.get("section_skeleton") or [])[:8]:
            sid = str(s.get("id") or "").strip()
            title = str(s.get("title") or "").strip()
            kind = str(s.get("kind") or "narrative").strip()
            if sid and title:
                outline.append({"id": sid, "title": title, "kind": kind})

        return {
            "improved_description": str(
                obj.get("improved_description") or ""
            ).strip(),
            "typical_output": str(obj.get("typical_output") or "").strip(),
            "section_skeleton": outline,
            "default_team": team,
        }

    @staticmethod
    async def confirm(
        db: AsyncSession,
        rt: CustomReportType,
        *,
        label: Optional[str] = None,
        improved_description: Optional[str] = None,
        typical_output: Optional[str] = None,
        section_skeleton: Optional[List[Dict[str, str]]] = None,
        default_team: Optional[List[str]] = None,
        visibility: Optional[str] = None,
    ) -> CustomReportType:
        if label:
            rt.label = label.strip()[:200]
        if improved_description is not None:
            rt.improved_description = improved_description.strip()
        if typical_output is not None:
            rt.typical_output = typical_output.strip()[:500]
        if section_skeleton is not None:
            rt.section_skeleton = section_skeleton
        if default_team is not None:
            valid_ids = {e["id"] for e in EMPLOYEES}
            rt.default_team = [eid for eid in default_team if eid in valid_ids]
        if visibility in ("private", "public"):
            rt.visibility = visibility
        rt.status = "active"
        await db.flush()
        return rt

    @staticmethod
    async def delete(db: AsyncSession, rt: CustomReportType) -> None:
        await db.delete(rt)
        await db.flush()
