"""ModelRouter — Route tasks to appropriate LLM based on complexity.

Inspired by Kimi K2.6 Claw Groups: route tasks to different LLMs
based on task type and complexity, optimizing cost-quality tradeoff.

Routing strategy:
  - light:   fast, cheap — for summarization, formatting
  - standard: balanced — for analysis, writing, chart generation
  - heavy:   slow, expensive — for deep reasoning, verification
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Profile of an LLM model."""
    name: str
    base_url: str
    api_key: str
    cost_level: int           # relative cost (1, 5, 10)
    strength: str             # speed | balanced | reasoning
    context_length: int = 8192
    supports_json: bool = True
    supports_tools: bool = False


class ModelRouter:
    """Route tasks to the most appropriate LLM model.

    Models are defined in priority order. The router selects the
    best model based on agent type, task characteristics, and
    optional complexity hints.
    """

    DEFAULT_PROFILES: dict[str, ModelProfile] = {
        "light": ModelProfile(
            name="qwen2.5:7b",
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            cost_level=1,
            strength="speed",
            context_length=32768,
            supports_json=True,
        ),
        "standard": ModelProfile(
            name="qwen2.5:72b",
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            cost_level=5,
            strength="balanced",
            context_length=131072,
            supports_json=True,
        ),
        "heavy": ModelProfile(
            name="deepseek-r1:32b",
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            cost_level=10,
            strength="reasoning",
            context_length=131072,
            supports_json=True,
        ),
    }

    # Agent type → default model tier mapping
    AGENT_TIER_MAP: dict[str, str] = {
        # Planning & high-level reasoning → heavy
        "chief": "heavy",
        "sage": "heavy",
        # Research & deep analysis → heavy
        "remy": "heavy",
        "nova": "heavy",
        # Data & analysis → standard
        "quinn": "standard",
        "adler": "standard",
        # Document processing → standard
        "vera": "standard",
        "orin": "standard",
        # Writing → standard (quality matters)
        "li_bai": "standard",
        # Visual & presentation → standard
        "iris": "standard",
        # Review → heavy (needs strong reasoning)
        "reviewer": "heavy",
        "citation": "standard",
        # PPT-specific agents
        "slide_editor": "standard",
        "ppt_research": "heavy",
        "visual": "standard",
    }

    # Task query keyword overrides (detect complexity from content)
    COMPLEXITY_KEYWORDS: dict[str, list[str]] = {
        "heavy": [
            "验证", "校验", "评审", "review", "verify", "validate",
            "推理", "reasoning", "深度分析", "deep analysis",
            "逻辑一致性", "交叉验证", "consensus",
            "多步推理", "chain of thought", "cot",
            "财务建模", "valuation", "量化", "quantitative",
        ],
        "light": [
            "格式化", "format", "摘要", "summarize", "提取",
            "简单", "simple", "列表", "list",
            "转义", "escape", "清洗", "clean",
        ],
    }

    def __init__(self, profiles: Optional[dict[str, ModelProfile]] = None):
        self.profiles = profiles or self.DEFAULT_PROFILES.copy()
        self._call_stats: dict[str, dict] = {
            tier: {"calls": 0, "tokens": 0}
            for tier in self.profiles
        }

    def route(self, agent_type: str, query: str = "", hint: Optional[str] = None) -> ModelProfile:
        """Select the best model for a task.

        Args:
            agent_type: The agent persona type (e.g., "remy", "quinn")
            query: The task query text (used for keyword detection)
            hint: Explicit complexity hint ("light", "standard", "heavy")

        Returns:
            The selected ModelProfile
        """
        # 1. Explicit hint takes highest priority
        if hint and hint in self.profiles:
            tier = hint
        else:
            # 2. Check query keywords for complexity override
            tier = self._detect_tier_from_query(query)
            if not tier:
                # 3. Fall back to agent type mapping
                tier = self.AGENT_TIER_MAP.get(agent_type, "standard")

        profile = self.profiles.get(tier, self.profiles["standard"])
        self._call_stats[tier]["calls"] += 1
        logger.debug(f"[ModelRouter] Route {agent_type} → {profile.name} (tier={tier})")
        return profile

    def route_for_chat(
        self,
        agent_type: str,
        messages: list[dict],
        hint: Optional[str] = None,
    ) -> tuple[str, str, str]:
        """Route and return (model_name, base_url, api_key).

        Priority: per-request profile → model_pool active entry → legacy llm_* keys → defaults.
        """
        import json as _json
        from app.services.llm_service import _runtime as _llm_runtime, get_selected_llm_profile

        selected = get_selected_llm_profile()
        if selected and selected.get("base_url") and selected.get("model"):
            return selected["model"], selected["base_url"], (selected.get("api_key") or "ollama")

        # Model pool is authoritative — prefer it over legacy individual keys
        pool_raw = _llm_runtime.get("model_pool")
        if pool_raw:
            try:
                pool = _json.loads(pool_raw) if isinstance(pool_raw, str) else pool_raw
                if isinstance(pool, list) and pool:
                    active = next(
                        (m for m in pool if m.get("active") and m.get("model") and m.get("base_url")),
                        next((m for m in pool if m.get("model") and m.get("base_url")), None),
                    )
                    if active:
                        return active["model"], active["base_url"].rstrip("/"), (active.get("api_key") or "ollama")
            except Exception:
                pass

        rt_base = _llm_runtime.get("llm_base_url")
        rt_model = _llm_runtime.get("llm_model")
        rt_key = _llm_runtime.get("llm_api_key")
        if rt_base and rt_model:
            return rt_model, rt_base, (rt_key or "ollama")

        query = messages[-1].get("content", "") if messages else ""
        profile = self.route(agent_type, query, hint)
        return profile.name, profile.base_url, profile.api_key

    def _detect_tier_from_query(self, query: str) -> Optional[str]:
        """Detect model tier from query keywords."""
        query_lower = query.lower()
        for tier, keywords in self.COMPLEXITY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in query_lower:
                    return tier
        return None

    def add_profile(self, name: str, profile: ModelProfile) -> None:
        """Add or override a model profile."""
        self.profiles[name] = profile
        if name not in self._call_stats:
            self._call_stats[name] = {"calls": 0, "tokens": 0}

    def get_stats(self) -> dict:
        """Get routing statistics."""
        return {
            "profiles": {name: p.name for name, p in self.profiles.items()},
            "calls": self._call_stats.copy(),
            "total_calls": sum(s["calls"] for s in self._call_stats.values()),
        }

    def estimate_cost(self, agent_type: str, query: str = "", hint: Optional[str] = None) -> int:
        """Estimate relative cost for a task."""
        profile = self.route(agent_type, query, hint)
        return profile.cost_level


# Singleton instance
_default_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get the default model router instance."""
    global _default_router
    if _default_router is None:
        # Override defaults from settings if available
        profiles = ModelRouter.DEFAULT_PROFILES.copy()
        configured_url = getattr(settings, "default_llm_base_url", "") or "http://localhost:11434/v1"
        configured_key = getattr(settings, "default_llm_api_key", "") or "ollama"
        configured_model = getattr(settings, "default_llm_model", "") or "qwen2.5:72b"
        if configured_url != "http://localhost:11434/v1" or configured_model != "qwen2.5:72b":
            # Update all profiles to use the configured endpoint; only model name differs
            profiles["standard"] = ModelProfile(
                name=configured_model,
                base_url=configured_url,
                api_key=configured_key,
                cost_level=5,
                strength="balanced",
                context_length=131072,
                supports_json=True,
            )
            # Light and heavy fall back to the same endpoint if not separately configured
            profiles["light"] = ModelProfile(
                name=getattr(settings, "light_llm_model", configured_model),
                base_url=getattr(settings, "light_llm_base_url", configured_url),
                api_key=configured_key,
                cost_level=1,
                strength="speed",
                context_length=32768,
                supports_json=True,
            )
            profiles["heavy"] = ModelProfile(
                name=getattr(settings, "heavy_llm_model", configured_model),
                base_url=getattr(settings, "heavy_llm_base_url", configured_url),
                api_key=configured_key,
                cost_level=10,
                strength="reasoning",
                context_length=131072,
                supports_json=True,
            )
        _default_router = ModelRouter(profiles)
    return _default_router


def reset_model_router() -> None:
    """Reset the singleton (useful for testing)."""
    global _default_router
    _default_router = None
