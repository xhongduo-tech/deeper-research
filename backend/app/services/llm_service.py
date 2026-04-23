from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.agent_config import AgentConfig
from app.services.config_service import ConfigService


async def resolve_runtime_llm_config() -> dict:
    """Look up the latest system-config LLM values from the DB, falling back
    to env. This is the single source of truth consumed by LLMService and the
    scoping/production flows, so admin-saved values take effect without a
    process restart."""
    try:
        async with AsyncSessionLocal() as db:
            return await ConfigService(db).get_llm_config()
    except Exception:
        return {
            "api_key": settings.DEFAULT_LLM_API_KEY,
            "base_url": settings.DEFAULT_LLM_BASE_URL,
            "model": settings.DEFAULT_LLM_MODEL,
            "temperature": None,
            "max_tokens": None,
        }


async def resolve_runtime_embedding_config() -> dict:
    """Same as above but for the embedding endpoint."""
    try:
        async with AsyncSessionLocal() as db:
            return await ConfigService(db).get_embedding_config()
    except Exception:
        return {
            "api_key": settings.DEFAULT_LLM_API_KEY,
            "base_url": settings.DEFAULT_LLM_BASE_URL,
            "model": "text-embedding-3-small",
            "enabled": False,
            "chunk_size": 1200,
            "top_k": 12,
        }


class LLMService:
    """
    Service for making OpenAI-compatible LLM API calls.
    Supports per-employee configuration with fallback to system defaults.

    Defaults are resolved dynamically from admin-saved config (DB) on every
    call, so changes made in /admin take effect immediately without a process
    restart. An explicit ``base_url`` / ``api_key`` passed to ``chat`` still
    wins — used for per-employee overrides.
    """

    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db

    async def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        """
        Make an OpenAI-compatible chat completion request.

        Args:
            messages: List of {"role": str, "content": str} dicts
            model: Model name (falls back to DEFAULT_LLM_MODEL)
            base_url: API base URL (falls back to DEFAULT_LLM_BASE_URL)
            api_key: API key (falls back to DEFAULT_LLM_API_KEY)
            stream: Whether to stream the response
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            If stream=False: content string
            If stream=True: async generator of content chunks
        """
        # Runtime defaults from admin config (falls back to env if DB empty).
        runtime = await resolve_runtime_llm_config()
        effective_key = api_key or runtime["api_key"]
        effective_url = base_url or runtime["base_url"]
        effective_model = model or runtime["model"]
        client = AsyncOpenAI(api_key=effective_key, base_url=effective_url)

        if stream:
            return self._stream_chat(client, effective_model, messages, temperature, max_tokens)
        else:
            response = await client.chat.completions.create(
                model=effective_model,
                messages=messages,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

    async def _stream_chat(
        self,
        client: AsyncOpenAI,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion response."""
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def get_employee_llm_config(self, employee_id: str) -> dict:
        """
        Fetch LLM configuration for a specific employee from the database.
        Falls back to system defaults if no config found.
        """
        if self.db:
            try:
                result = await self.db.execute(
                    select(AgentConfig).where(AgentConfig.employee_id == employee_id)
                )
                config = result.scalar_one_or_none()
                if config and config.enabled:
                    default = await ConfigService(self.db).get_llm_config()
                    profile_id = (config.custom_params or {}).get("model_profile_id")
                    profile = await ConfigService(self.db).resolve_llm_profile(profile_id)
                    return {
                        "api_key": (profile or {}).get("api_key") or config.llm_api_key or default["api_key"],
                        "base_url": (profile or {}).get("base_url") or config.llm_base_url or default["base_url"],
                        "model": (profile or {}).get("model") or config.llm_model or default["model"],
                        "profile_id": profile_id or default.get("profile_id"),
                        "profile_name": (profile or {}).get("name") or default.get("profile_name"),
                        "temperature": config.temperature,
                        "max_tokens": config.max_tokens,
                        "custom_params": config.custom_params or {},
                    }
            except Exception:
                pass

        # Return system defaults
        return await self._get_default_config()

    async def get_all_employee_configs(self, employee_ids: list) -> dict:
        """
        Get LLM configurations for multiple employees at once.
        Returns dict of {employee_id: config}
        """
        configs = {}
        default = await self._get_default_config()

        if self.db and employee_ids:
            try:
                result = await self.db.execute(
                    select(AgentConfig).where(
                        AgentConfig.employee_id.in_(employee_ids)
                    )
                )
                db_configs = result.scalars().all()
                for cfg in db_configs:
                    if cfg.enabled:
                        profile_id = (cfg.custom_params or {}).get("model_profile_id")
                        profile = await ConfigService(self.db).resolve_llm_profile(profile_id)
                        configs[cfg.employee_id] = {
                            "api_key": (profile or {}).get("api_key") or cfg.llm_api_key or default["api_key"],
                            "base_url": (profile or {}).get("base_url") or cfg.llm_base_url or default["base_url"],
                            "model": (profile or {}).get("model") or cfg.llm_model or default["model"],
                            "profile_id": profile_id or default.get("profile_id"),
                            "profile_name": (profile or {}).get("name") or default.get("profile_name"),
                            "temperature": cfg.temperature,
                            "max_tokens": cfg.max_tokens,
                        }
            except Exception:
                pass

        # Fill missing with defaults
        for eid in employee_ids:
            if eid not in configs:
                configs[eid] = default

        return configs

    async def _get_default_config(self) -> dict:
        """Get system default LLM configuration."""
        if self.db:
            return await ConfigService(self.db).get_llm_config()
        return {
            "api_key": settings.DEFAULT_LLM_API_KEY,
            "base_url": settings.DEFAULT_LLM_BASE_URL,
            "model": settings.DEFAULT_LLM_MODEL,
            "temperature": None,
            "max_tokens": None,
        }

    async def test_connection(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict:
        """Test LLM connection with a simple hello message."""
        try:
            response = await self.chat(
                messages=[
                    {"role": "user", "content": "Reply with just 'OK' to confirm the connection works."}
                ],
                model=model,
                base_url=base_url,
                api_key=api_key,
                stream=False,
                max_tokens=10,
            )
            return {
                "success": True,
                "response": response,
                "model": model or settings.DEFAULT_LLM_MODEL,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": model or settings.DEFAULT_LLM_MODEL,
            }
