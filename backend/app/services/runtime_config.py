"""Runtime system configuration loaded from admin-managed DB settings."""
from __future__ import annotations

from app.config import settings

_runtime: dict[str, str] = {}


def apply_runtime_config(cfg: dict) -> None:
    """Apply DB-persisted config values to the runtime overlay."""
    for key, value in (cfg or {}).items():
        if value is not None:
            _runtime[key] = str(value)


def _coerce_bool(value: str | bool | None, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}


def _coerce_int(value: str | int | None, fallback: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value) if value is not None else fallback
    except (TypeError, ValueError):
        parsed = fallback
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def get_config_value(key: str, fallback: str = "") -> str:
    return _runtime.get(key, fallback)


def is_external_search_enabled() -> bool:
    # Internet access is intentionally unavailable for intranet deployments.
    # Keep the setting readable for compatibility, but never permit outbound
    # public search from the production research pipeline.
    return False


def is_browser_enabled() -> bool:
    # Browser automation (Playwright) is not used in the intranet pipeline.
    # Kept for API compatibility; always returns False.
    return False


def is_rag_enabled() -> bool:
    return _coerce_bool(_runtime.get("rag_enabled"), True)


def external_search_max_results() -> int:
    return _coerce_int(_runtime.get("external_search_max_results"), 5, minimum=1, maximum=10)


def snapshot() -> dict:
    return {
        "enable_external_search": is_external_search_enabled(),
        "enable_browser": is_browser_enabled(),
        "rag_enabled": is_rag_enabled(),
        "external_search_max_results": external_search_max_results(),
        "external_search_policy": "intranet_disabled",
    }
