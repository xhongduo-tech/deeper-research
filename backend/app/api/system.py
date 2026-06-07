from fastapi import APIRouter
import json

from app.config import settings
from app.services.llm_service import check_llm_connection
from app.services.llm_service import _runtime as llm_runtime

router = APIRouter(tags=["system"])


@router.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "DataAgent Studio",
        "version": "1.0.0",
    }


@router.get("/api/system/llm/health")
async def llm_health():
    """Lightweight LLM reachability check.

    Used by the frontend to fail fast (with a clear "call model error" toast)
    before kicking off a creation flow when the model is misconfigured or down.
    Public — no auth required so unauthenticated users get a useful diagnosis
    instead of confusing failures.
    """
    base_url = (llm_runtime.get("llm_base_url") or settings.default_llm_base_url or "").rstrip("/")
    model = llm_runtime.get("llm_model") or settings.default_llm_model or ""
    api_key = llm_runtime.get("llm_api_key") or settings.default_llm_api_key or "ollama"

    if not base_url or not model:
        return {"ok": False, "error": "未配置大模型地址或模型名"}

    result = await check_llm_connection(base_url, api_key, model=model)
    return {
        "ok": result["ok"],
        "model": result.get("model") or model,
        **({"error": result["error"]} if result.get("error") else {}),
        **({"available": result["available"]} if result.get("available") else {}),
    }


@router.get("/api/system/capabilities")
async def system_capabilities():
    """Return feature flags visible to the frontend (no auth required)."""
    return {
        "external_search_enabled": settings.enable_external_search,
        "browser_enabled": getattr(settings, "enable_browser", False),
    }


@router.get("/api/system/models")
async def model_config():
    """Public model display config for the frontend.

    Mirrors the model selected in the admin console without exposing secrets.
    The backend currently routes all generation through the admin-configured
    standard model, with optional light/heavy defaults advertised for UI labels.
    """
    base_url = (llm_runtime.get("llm_base_url") or settings.default_llm_base_url or "").rstrip("/")
    standard_model = llm_runtime.get("llm_model") or settings.default_llm_model or ""
    light_model = settings.light_llm_model or standard_model
    heavy_model = settings.heavy_llm_model or standard_model

    raw_pool = llm_runtime.get("model_pool")
    if raw_pool:
        try:
            pool = json.loads(raw_pool)
        except Exception:
            pool = []
        models = []
        for idx, row in enumerate(pool if isinstance(pool, list) else []):
            if not isinstance(row, dict) or not row.get("enabled", True):
                continue
            model = str(row.get("model") or "").strip()
            base = str(row.get("base_url") or "").strip()
            if not model or not base:
                continue
            tier = str(row.get("tier") or "standard")
            active = bool(row.get("active")) or idx == 0
            models.append({
                "id": f"pool:{row.get('id') or model}",
                "model": model,
                "name": row.get("name") or model,
                "tier": tier,
                "description": row.get("description") or "后台模型池",
                "active": active,
            })
        if models:
            active_model = next((m["model"] for m in models if m.get("active")), models[0]["model"])
            return {
                "active_model": active_model,
                "base_url_host": base_url.replace("https://", "").replace("http://", "").split("/")[0],
                "models": models,
            }

    def item(model: str, tier: str, name: str, desc: str, active: bool = False):
        return {
            "id": f"{tier}:{model}",
            "model": model,
            "name": name if name.endswith(model) else f"{name} · {model}",
            "tier": tier,
            "description": desc,
            "active": active,
        }

    models = [
        item(standard_model, "standard", "DataAgent", "后台 Admin 当前生效模型", True),
    ]
    if light_model and light_model != standard_model:
        models.append(item(light_model, "light", "快速模型", "适合摘要、提取和轻量处理"))
    if heavy_model and heavy_model not in {standard_model, light_model}:
        models.append(item(heavy_model, "heavy", "深度模型", "适合复杂推理、核验和深度研究"))

    return {
        "active_model": standard_model,
        "base_url_host": base_url.replace("https://", "").replace("http://", "").split("/")[0],
        "models": models,
    }
