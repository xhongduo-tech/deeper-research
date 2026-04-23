import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.system_config import SystemConfig


class ConfigService:
    """Reads runtime configuration saved from /admin with environment fallbacks."""

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def _load_rows(self) -> dict:
        rows = {}
        if self.db:
            try:
                result = await self.db.execute(select(SystemConfig))
                rows = {r.key: r.value for r in result.scalars().all()}
            except Exception:
                rows = {}
        return rows

    def _default_llm_profile(self) -> dict:
        return {
            "id": "default",
            "name": "默认模型",
            "base_url": settings.DEFAULT_LLM_BASE_URL,
            "model": settings.DEFAULT_LLM_MODEL,
            "api_key": settings.DEFAULT_LLM_API_KEY or "",
            "description": "系统默认兜底模型",
        }

    def _json(self, value, default):
        if value is None:
            return default
        try:
            return json.loads(value)
        except Exception:
            return default

    def _normalize_profile(self, raw: dict, idx: int) -> Optional[dict]:
        if not isinstance(raw, dict):
            return None
        base_url = str(raw.get("base_url") or "").strip()
        model = str(raw.get("model") or "").strip()
        if not base_url or not model:
            return None
        profile_id = str(raw.get("id") or f"profile_{idx + 1}").strip()
        return {
            "id": profile_id,
            "name": str(raw.get("name") or model).strip() or model,
            "base_url": base_url,
            "model": model,
            "api_key": str(raw.get("api_key") or "").strip(),
            "description": str(raw.get("description") or "").strip(),
        }

    def _parse_profiles(self, rows: dict) -> list[dict]:
        profiles = []
        raw_profiles = self._json(rows.get("llm_profiles"), [])
        if isinstance(raw_profiles, list):
            for idx, raw in enumerate(raw_profiles):
                normalized = self._normalize_profile(raw, idx)
                if normalized:
                    profiles.append(normalized)

        if profiles:
            return profiles

        # Backward-compatible fallback from the legacy single-model fields.
        return [
            {
                "id": "default",
                "name": "默认模型",
                "base_url": rows.get("default_llm_base_url") or settings.DEFAULT_LLM_BASE_URL,
                "model": rows.get("default_llm_model") or settings.DEFAULT_LLM_MODEL,
                "api_key": rows.get("default_llm_api_key") or settings.DEFAULT_LLM_API_KEY or "",
                "description": "从旧版单模型配置自动迁移",
            }
        ]

    def _get_default_profile_id(self, rows: dict, profiles: list[dict]) -> str:
        configured = rows.get("default_llm_profile_id")
        valid_ids = {p["id"] for p in profiles}
        if configured in valid_ids:
            return configured
        return profiles[0]["id"] if profiles else self._default_llm_profile()["id"]

    async def get_flat_config(self) -> dict:
        rows = await self._load_rows()
        llm_profiles = self._parse_profiles(rows)
        default_profile_id = self._get_default_profile_id(rows, llm_profiles)
        default_profile = next(
            (p for p in llm_profiles if p["id"] == default_profile_id),
            llm_profiles[0] if llm_profiles else self._default_llm_profile(),
        )

        return {
            "enable_external_search": self._bool(rows.get("enable_external_search"), settings.ENABLE_EXTERNAL_SEARCH),
            "enable_browser": self._bool(rows.get("enable_browser"), settings.ENABLE_BROWSER),
            "default_llm_base_url": default_profile["base_url"],
            "default_llm_model": default_profile["model"],
            "default_llm_api_key": default_profile["api_key"],
            "default_llm_profile_id": default_profile_id,
            "llm_profiles": llm_profiles,
            "embedding_base_url": rows.get("embedding_base_url") or default_profile["base_url"] or settings.DEFAULT_LLM_BASE_URL,
            "embedding_model": rows.get("embedding_model") or "text-embedding-3-small",
            "embedding_api_key": rows.get("embedding_api_key") or default_profile["api_key"] or settings.DEFAULT_LLM_API_KEY,
            "vector_store_enabled": self._bool(rows.get("vector_store_enabled"), False),
            "kb_chunk_size": self._int(rows.get("kb_chunk_size"), 1200),
            "kb_top_k": self._int(rows.get("kb_top_k"), 12),
            "sandbox_timeout": self._int(rows.get("sandbox_timeout"), settings.SANDBOX_TIMEOUT),
            "max_workers": self._int(rows.get("max_workers"), settings.MAX_WORKERS),
        }

    async def get_llm_config(self) -> dict:
        config = await self.get_flat_config()
        default_profile = next(
            (
                profile
                for profile in config.get("llm_profiles", [])
                if profile["id"] == config.get("default_llm_profile_id")
            ),
            None,
        )
        return {
            "api_key": config["default_llm_api_key"],
            "base_url": config["default_llm_base_url"],
            "model": config["default_llm_model"],
            "profile_id": config.get("default_llm_profile_id"),
            "profile_name": (default_profile or {}).get("name"),
            "temperature": None,
            "max_tokens": None,
        }

    async def get_llm_profiles(self) -> list[dict]:
        rows = await self._load_rows()
        return self._parse_profiles(rows)

    async def resolve_llm_profile(self, profile_id: Optional[str]) -> Optional[dict]:
        if not profile_id:
            return None
        profiles = await self.get_llm_profiles()
        for profile in profiles:
            if profile["id"] == profile_id:
                return profile
        return None

    async def get_embedding_config(self) -> dict:
        config = await self.get_flat_config()
        return {
            "api_key": config["embedding_api_key"],
            "base_url": config["embedding_base_url"],
            "model": config["embedding_model"],
            "enabled": config["vector_store_enabled"],
            "chunk_size": config["kb_chunk_size"],
            "top_k": config["kb_top_k"],
        }

    def _bool(self, value, default: bool) -> bool:
        if value is None:
            return default
        return str(value).lower() in ("true", "1", "yes", "on")

    def _int(self, value, default: int) -> int:
        try:
            return int(value) if value is not None else default
        except (TypeError, ValueError):
            return default
