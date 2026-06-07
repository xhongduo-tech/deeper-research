"""Base skill interface for all agent tools."""
from abc import ABC, abstractmethod
from typing import Any


class Skill(ABC):
    name: str = ""
    description: str = ""
    category: str = "offline"  # offline | web | data | doc
    parameters: dict = {}      # JSON-schema style param docs

    @abstractmethod
    async def execute(self, params: dict, context: dict | None = None) -> dict:
        """Execute the skill. Returns {"result": ..., "error": ...}."""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
        }
