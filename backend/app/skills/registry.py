"""Central skill registry — singleton with auto-registration."""
import logging
from typing import Type

from app.skills.base import Skill

logger = logging.getLogger(__name__)


class SkillRegistry:
    _skills: dict[str, Skill] = {}

    @classmethod
    def register(cls, skill: Skill):
        cls._skills[skill.name] = skill
        logger.info(f"[SkillRegistry] Registered skill: {skill.name} ({skill.category})")

    @classmethod
    def get(cls, name: str) -> Skill | None:
        return cls._skills.get(name)

    @classmethod
    def list_all(cls) -> list[dict]:
        return [s.to_dict() for s in cls._skills.values()]

    @classmethod
    def list_by_category(cls, category: str) -> list[dict]:
        return [s.to_dict() for s in cls._skills.values() if s.category == category]

    @classmethod
    async def execute(cls, name: str, params: dict, context: dict | None = None) -> dict:
        skill = cls.get(name)
        if not skill:
            return {"error": f"Skill '{name}' not found", "result": ""}
        try:
            return await skill.execute(params, context)
        except Exception as e:
            logger.exception(f"Skill '{name}' execution failed")
            return {"error": str(e), "result": ""}
