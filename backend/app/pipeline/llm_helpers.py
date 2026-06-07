"""LLM call helpers for pipeline phases.

Ported from simple_pipeline.py. All functions raise on persistent failure
rather than returning silent fallback values — callers are responsible for
handling errors via PipelineError.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Lazy singleton so we don't import heavy deps at module level
_model_router = None


def _get_router():
    global _model_router
    if _model_router is None:
        from app.services.model_router import ModelRouter
        _model_router = ModelRouter()
    return _model_router


def _coerce_json_object(value: Any, fallback: dict | None = None, *, context: str = "") -> dict:
    """Best-effort conversion for unreliable LLM JSON responses."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        candidates = [text]
        if "{" in text and "}" in text:
            candidates.append(text[text.find("{"):text.rfind("}") + 1])
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list):
                    return {"items": parsed}
            except Exception:
                continue
    if isinstance(value, list):
        return {"items": value}
    if value is not None:
        logger.warning("Expected JSON object for %s, got %s", context or "pipeline", type(value).__name__)
    return dict(fallback or {})


def _listify(value) -> list:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    return [value]


def _coerce_bool(value, default: bool = False) -> bool:
    """Interpret JSON-ish booleans from LLMs without treating 'false' as true."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "y", "1", "需要", "是", "需澄清"}:
            return True
        if text in {"false", "no", "n", "0", "不需要", "否", "无需", "none", "null", ""}:
            return False
    return default


def _resolve_llm_endpoint(messages: list[dict], tier: str) -> tuple[str, str, str]:
    """Resolve (model, base_url, api_key).

    Priority order:
    1. Per-request selected_llm_profile context (set by chat API for user model selection)
    2. Active entry in model_pool (admin-configured authoritative source)
    3. Legacy llm_base_url / llm_api_key runtime keys
    4. ModelRouter defaults (Ollama localhost)
    """
    import json as _json
    from app.services.llm_service import _runtime as _llm_runtime, get_selected_llm_profile

    # 1. Per-request profile (user selected a specific pool entry)
    selected = get_selected_llm_profile()
    if selected and selected.get("base_url") and selected.get("model"):
        return selected["model"], selected["base_url"], (selected.get("api_key") or "ollama")

    # 2. Active model from pool — most reliable source
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

    # 3. Legacy individual keys
    rt_base = _llm_runtime.get("llm_base_url")
    rt_model = _llm_runtime.get("llm_model")
    rt_key = _llm_runtime.get("llm_api_key")
    if rt_base and rt_model:
        return rt_model, rt_base, (rt_key or "ollama")

    return _get_router().route_for_chat("pipeline", messages, hint=tier)


def _adaptive_timeout(max_tokens: int) -> float:
    """P2-E: Return a timeout (seconds) proportional to max_tokens.

    Rationale: a 4096-token generation at 8 tok/s takes ~512s worst-case; applying
    1.5× safety factor gives the adaptive floor. Hard minimum is 60s so short calls
    never time out prematurely.
    """
    return max(60.0, max_tokens / 8 * 1.5)


async def call_llm_json(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    fallback: dict | None = None,
    tier: str = "standard",
) -> dict:
    """Call chat_json with retry and model routing. Returns a dict.

    Unlike the original _call_llm_json, this does NOT silently return an
    empty dict on failure — it returns the fallback if provided, or raises.
    The spec_gen phase uses this and handles errors explicitly.
    """
    from app.services.llm_service import chat_json

    model, base_url, api_key = _resolve_llm_endpoint(messages, tier)
    timeout = _adaptive_timeout(max_tokens)
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = await asyncio.wait_for(
                chat_json(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                ),
                timeout=timeout,
            )
            normalized = _coerce_json_object(result, context="llm_json")
            if normalized:
                return normalized
            logger.warning("LLM JSON returned non-object: %s", type(result))
        except asyncio.TimeoutError:
            last_exc = asyncio.TimeoutError(f"LLM JSON call timed out after {timeout:.0f}s (model={model})")
            logger.warning("LLM JSON call timed out (attempt %d, model=%s, timeout=%.0fs)", attempt + 1, model, timeout)
            if attempt == 0:
                await asyncio.sleep(0.5)
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM JSON call failed (attempt %d, model=%s): %s", attempt + 1, model, exc)
            if attempt == 0:
                await asyncio.sleep(0.5)

    if fallback is not None:
        return dict(fallback)
    raise RuntimeError(f"LLM JSON call exhausted retries. Last error: {last_exc}")


async def call_llm_text(
    messages: list[dict],
    temperature: float = 0.45,
    max_tokens: int = 4096,
    fallback: str = "",
    tier: str = "standard",
) -> str:
    """Call chat with retry and model routing."""
    from app.services.llm_service import chat

    model, base_url, api_key = _resolve_llm_endpoint(messages, tier)
    timeout = _adaptive_timeout(max_tokens)
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            result = await asyncio.wait_for(
                chat(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=model,
                    base_url=base_url,
                    api_key=api_key,
                ),
                timeout=timeout,
            )
            if result and result.strip():
                return result
            logger.warning("LLM text call returned empty (attempt %d, model=%s)", attempt + 1, model)
        except asyncio.TimeoutError:
            last_exc = asyncio.TimeoutError(f"LLM text call timed out after {timeout:.0f}s (model={model})")
            logger.warning("LLM text call timed out (attempt %d, model=%s, timeout=%.0fs)", attempt + 1, model, timeout)
            if attempt == 0:
                await asyncio.sleep(0.5)
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM text call failed (attempt %d, model=%s): %s", attempt + 1, model, exc)
            if attempt == 0:
                await asyncio.sleep(0.5)

    if last_exc:
        logger.error("LLM text exhausted retries, model=%s, error=%s", model, last_exc)
    return fallback
