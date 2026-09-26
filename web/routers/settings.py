from typing import Any, Dict
from fastapi import APIRouter, Body

from models.schemas import SettingsUpdatePayload, TestConnectionPayload
from services.ai.catalog import MODEL_CATALOG
from web.dependencies import gemini_service, settings_service

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/models")
async def get_available_models():
    """Returns the comprehensive curated model catalog across all supported AI providers."""
    return MODEL_CATALOG


@router.post("/test-connection")
async def test_ai_connection(payload: Dict[str, Any] = Body(...)):
    """Tests connection to the specified AI provider and measures latency."""
    provider = payload.get("provider", "gemini")
    api_key = payload.get("api_key")
    model = payload.get("model") or payload.get("model_name") or "gemini-2.5-flash"
    base_url = payload.get("base_url")

    # If api_key is empty or masked, fetch from saved settings
    if not api_key or api_key.startswith("AIzaSy...") or api_key.startswith("sk-...") or api_key == "***":
        settings = settings_service.load_settings()
        key_name = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"
        api_key = settings.get(key_name, "")

    result = gemini_service.test_connection(
        provider=provider,
        api_key=api_key,
        model_name=model,
        base_url=base_url,
    )
    return result


@router.get("")
async def get_app_settings():
    """Retrieves current application, theme, and AI model settings with masked keys."""
    return settings_service.get_masked_settings()


@router.put("")
async def update_app_settings(payload: Dict[str, Any] = Body(...)):
    """Updates AI provider, model, API keys, and default theme."""
    settings = settings_service.update_settings(payload)

    # Reconfigure the active AI service instance
    provider = settings.get("ai_provider", "gemini")
    key_field = f"{provider}_api_key" if f"{provider}_api_key" in settings else "gemini_api_key"
    active_key = settings.get(key_field, "")

    gemini_service.configure(
        api_key=active_key,
        model_name=settings.get("ai_model", "gemini-2.5-flash"),
        provider=provider,
        base_url=settings.get("custom_base_url"),
    )

    return {
        "success": True,
        "ai_provider": settings.get("ai_provider"),
        "ai_model": settings.get("ai_model"),
        "gemini_model": settings.get("ai_model"),
        "has_api_key": bool(active_key),
        "masked_api_key": settings_service.mask_key(settings.get("gemini_api_key", "")),
        "masked_openai_key": settings_service.mask_key(settings.get("openai_api_key", "")),
        "masked_anthropic_key": settings_service.mask_key(settings.get("anthropic_api_key", "")),
        "masked_custom_key": settings_service.mask_key(settings.get("custom_api_key", "")),
        "theme": settings.get("theme"),
    }
