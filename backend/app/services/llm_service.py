import asyncio
from contextvars import ContextVar
from contextlib import contextmanager
import json
import logging
import httpx
from openai import AsyncOpenAI

from app.config import settings

# Runtime config overlay — set by admin API and loaded from DB on startup
_runtime: dict = {}
_selected_profile: ContextVar[dict | None] = ContextVar("selected_llm_profile", default=None)
_effort_level: ContextVar[str] = ContextVar("effort_level", default="low")
LLM_HEALTH_TIMEOUT = 15.0
LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0  # seconds, doubled each retry

# Effort level configuration.
# The real differentiator is the thinking instruction injected into the system
# prompt — this changes HOW the model reasons, not just how long it can respond.
# max_tokens and temperature are secondary adjustments.
_EFFORT_CONFIGS: dict[str, dict] = {
    "low": {
        "tokens_scale": 1.0,
        "temp_scale":   1.0,
        "thinking_prompt": "",   # no injection; direct response
    },
    "medium": {
        "tokens_scale": 1.8,
        "temp_scale":   0.9,
        # Ask the model to reason step-by-step before answering.
        "thinking_prompt": (
            "\n\n[Reasoning requirement] Before producing your final answer, "
            "think through the problem step by step: identify key assumptions, "
            "consider relevant angles, and check your reasoning for gaps. "
            "Then give a clear, well-supported response."
        ),
    },
    "high": {
        "tokens_scale": 3.0,
        "temp_scale":   0.75,
        # Ask for deep, multi-perspective analysis with explicit reasoning chain.
        "thinking_prompt": (
            "\n\n[Deep analysis requirement] Perform thorough, rigorous analysis before answering:\n"
            "1. Decompose the problem and identify core assumptions and constraints.\n"
            "2. Reason from multiple perspectives; actively seek counterarguments.\n"
            "3. Identify edge cases, risks, or information gaps.\n"
            "4. Synthesise the above into a well-evidenced, logically tight conclusion.\n"
            "Your response must demonstrate clear reasoning at each step."
        ),
    },
}

logger = logging.getLogger(__name__)


def apply_runtime_config(cfg: dict) -> None:
    """Apply DB-persisted config values to the runtime overlay.

    model_pool is the authoritative LLM source.  When a pool is present its
    active entry is synced into the legacy llm_* keys so that all call-sites
    (including those that only read _runtime["llm_api_key"]) use the right
    credentials automatically.
    """
    import json as _json
    from app.services.runtime_config import apply_runtime_config as apply_system_runtime_config

    apply_system_runtime_config(cfg)
    for key in ("llm_base_url", "llm_model", "llm_api_key", "model_pool"):
        if cfg.get(key):
            _runtime[key] = cfg[key]

    # Sync active model_pool entry → legacy llm_* keys so every code-path
    # that reads _runtime["llm_api_key"] gets the correct credentials.
    pool_raw = _runtime.get("model_pool") or cfg.get("model_pool")
    if pool_raw:
        try:
            pool = _json.loads(pool_raw) if isinstance(pool_raw, str) else pool_raw
            if isinstance(pool, list) and pool:
                active = next(
                    (m for m in pool if m.get("active") and m.get("model") and m.get("base_url")),
                    next((m for m in pool if m.get("model") and m.get("base_url")), None),
                )
                if active:
                    _runtime["llm_base_url"] = active["base_url"].rstrip("/")
                    _runtime["llm_model"] = active["model"]
                    _runtime["llm_api_key"] = active.get("api_key") or "ollama"
        except Exception:
            pass


@contextmanager
def selected_llm_profile(profile: dict | None):
    """Temporarily route LLM calls in the current async task to a selected model."""
    token = _selected_profile.set(profile or None)
    try:
        yield
    finally:
        _selected_profile.reset(token)


@contextmanager
def effort_context(level: str):
    """Set the thinking-effort level for all LLM calls in the current async task."""
    token = _effort_level.set(level if level in _EFFORT_CONFIGS else "low")
    try:
        yield
    finally:
        _effort_level.reset(token)


def _apply_effort(
    messages: list[dict], temperature: float, max_tokens: int
) -> tuple[list[dict], float, int]:
    """Apply the current effort level to an LLM call.

    - Injects a thinking instruction into the system message (the real lever).
    - Scales temperature and max_tokens as secondary adjustments.
    Returns the (possibly modified) messages list, adjusted temperature, and max_tokens.
    """
    cfg = _EFFORT_CONFIGS.get(_effort_level.get(), _EFFORT_CONFIGS["low"])
    thinking_prompt: str = cfg["thinking_prompt"]
    adj_temp = round(min(1.0, temperature * cfg["temp_scale"]), 4)
    adj_tokens = int(max_tokens * cfg["tokens_scale"])

    if not thinking_prompt:
        return messages, adj_temp, adj_tokens

    # Append the thinking instruction to the existing system message, or prepend
    # a new one so callers don't need to know about effort at all.
    patched = list(messages)
    sys_idx = next((i for i, m in enumerate(patched) if m.get("role") == "system"), None)
    if sys_idx is not None:
        sys_msg = dict(patched[sys_idx])
        sys_msg["content"] = str(sys_msg.get("content") or "") + thinking_prompt
        patched[sys_idx] = sys_msg
    else:
        patched = [{"role": "system", "content": thinking_prompt.strip()}] + patched

    return patched, adj_temp, adj_tokens


def get_selected_llm_profile() -> dict | None:
    return _selected_profile.get()


def _rt(key: str, fallback: str) -> str:
    profile = get_selected_llm_profile()
    if profile:
        if key == "llm_base_url" and profile.get("base_url"):
            return profile["base_url"]
        if key == "llm_model" and profile.get("model"):
            return profile["model"]
        if key == "llm_api_key" and profile.get("api_key"):
            return profile["api_key"]
    return _runtime.get(key) or fallback


def get_client(base_url: str | None = None, api_key: str | None = None) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=base_url or _rt("llm_base_url", settings.default_llm_base_url),
        api_key=api_key or _rt("llm_api_key", settings.default_llm_api_key),
    )


async def check_llm_connection(
    base_url: str,
    api_key: str,
    model: str | None = None,
    timeout: float = LLM_HEALTH_TIMEOUT,
) -> dict:
    """Validate an OpenAI-compatible endpoint.

    Strategy:
      1. GET /models  — collect available model IDs (best-effort, some APIs skip auth here)
      2. POST /chat/completions with max_tokens=1 — the only truly reliable way to verify
         that this (key, model) pair is authorised to generate text.
    """
    normalized_base_url = (base_url or "").rstrip("/")
    if not normalized_base_url:
        return {"ok": False, "error": "请填写推理服务地址"}

    headers = {"Authorization": f"Bearer {api_key or 'ollama'}"}

    # ── Step 1: /models (optional, collect list) ──────────────────────────────
    models: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{normalized_base_url}/models", headers=headers)
        if resp.status_code < 400:
            try:
                models = [m["id"] for m in resp.json().get("data", [])]
            except Exception:
                pass
        # If /models returns 403/404 we continue — some internal APIs restrict it
    except Exception:
        pass

    # ── Step 2: minimal chat completion — real auth + model validation ─────────
    if not model:
        return {"ok": True, "model": "", "models": models}

    try:
        client = AsyncOpenAI(base_url=normalized_base_url, api_key=api_key or "ollama")
        await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
            temperature=0,
        )
        return {"ok": True, "model": model, "models": models}
    except Exception as e:
        err_str = str(e)
        # Surface the raw API error so the user sees the exact rejection reason
        # (e.g. "Key does not have access to model", "model not found", etc.)
        return {
            "ok": False,
            "error": err_str,
            "available": models[:10],
        }


async def chat(
    messages: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict | None = None,
    max_retries: int = LLM_MAX_RETRIES,
) -> str:
    client = get_client(base_url, api_key)
    resolved_model = model or _rt("llm_model", settings.default_llm_model)
    messages, temperature, max_tokens = _apply_effort(messages, temperature, max_tokens)
    kwargs = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        kwargs["response_format"] = response_format

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = await client.chat.completions.create(**kwargs)
            msg = response.choices[0].message
            content = msg.content or ""
            if not content.strip():
                # DeepSeek V4 / R1 and other reasoning models return the answer in
                # reasoning_content when the model exhausts max_tokens on the thought
                # trace. Fall back to it so callers don't see a silent empty response.
                content = getattr(msg, "reasoning_content", "") or ""
            return content
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Don't retry on client errors that won't resolve with retries
            if any(code in err_str for code in ("401", "403", "404", "invalid_api_key", "model not found", "does not exist")):
                raise
            if attempt < max_retries - 1:
                delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1, max_retries, delay, e,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("LLM call failed after %d attempts: %s", max_retries, e)

    raise last_error


async def chat_stream(
    messages: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    on_token=None,           # async callable(token: str, accumulated: str) -> None
    on_first_token=None,     # async callable(latency_ms: int) -> None
    flush_every: int = 4,    # emit accumulated buffer every N tokens
):
    """Streaming chat completion. Yields token deltas via async generator AND
    invokes `on_token` callback after each chunk arrives (for WS broadcasting).

    Returns the final assembled string after the stream completes.
    Falls back to non-streaming `chat()` if the provider doesn't support streaming.
    """
    import time

    client = get_client(base_url, api_key)
    resolved_model = model or _rt("llm_model", settings.default_llm_model)
    messages, temperature, max_tokens = _apply_effort(messages, temperature, max_tokens)
    kwargs = {
        "model": resolved_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    start_ms = time.monotonic() * 1000
    first_token_seen = False
    accumulated = ""
    buffer = ""
    chunk_count = 0

    try:
        stream = await client.chat.completions.create(**kwargs)
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content or ""
            except (AttributeError, IndexError):
                delta = ""
            if not delta:
                continue
            if not first_token_seen:
                first_token_seen = True
                if on_first_token:
                    try:
                        await on_first_token(int(time.monotonic() * 1000 - start_ms))
                    except Exception:
                        pass
            accumulated += delta
            buffer += delta
            chunk_count += 1
            if chunk_count >= flush_every and on_token:
                try:
                    await on_token(buffer, accumulated)
                except Exception:
                    pass
                buffer = ""
                chunk_count = 0
        # Flush remainder
        if buffer and on_token:
            try:
                await on_token(buffer, accumulated)
            except Exception:
                pass
        return accumulated
    except Exception as exc:
        # Fall back to non-streaming on provider error.
        # Pass the already-effort-adjusted messages/params so _apply_effort
        # is not applied a second time inside chat().
        logger.warning("Streaming failed, falling back to non-stream: %s", exc)
        with effort_context("low"):  # neutralise effort inside chat(); already applied above
            return await chat(messages, model, base_url, api_key, temperature, max_tokens)


async def chat_json(
    messages: list[dict],
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    max_retries: int = LLM_MAX_RETRIES,
) -> dict:
    """Chat completion that returns parsed JSON dict.

    Retries on transient parse errors in addition to transport failures.
    """
    last_parse_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            text = await chat(
                messages=messages,
                model=model,
                base_url=base_url,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                max_retries=1,  # transport retry handled here
            )
        except Exception:
            if attempt < max_retries - 1:
                delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            raise

        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n", 1)
            text = lines[1] if len(lines) > 1 else ""
            text = text.rstrip()
            if text.endswith("```"):
                text = text[:-3].rstrip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            last_parse_error = e
            if attempt < max_retries - 1:
                delay = LLM_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "JSON parse failed (attempt %d/%d), retrying in %.1fs",
                    attempt + 1, max_retries, delay,
                )
                await asyncio.sleep(delay)
                continue
            logger.error("JSON parse failed after %d attempts: %s", max_retries, e)
            return {"_raw_response": text, "error": f"JSON parse error: {e}"}

        # Ensure we always return a dict, even if the model returns a string/number/list
        if isinstance(parsed, dict):
            return parsed
        return {"_raw_response": str(parsed), "error": "Expected JSON object, got other type"}

    # Should not reach here
    return {"error": str(last_parse_error)}
