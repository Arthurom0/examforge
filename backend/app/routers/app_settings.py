"""Settings page: LLM provider, per-provider API keys and models, stored in the .env file (keys never returned in full)."""
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import ENV_FILE, settings, update_env
from ..services import providers
from ..services.extraction import ocr_available, tesseract_path

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    provider: Optional[str] = None  # makes it the active provider; api_key/model/base_url apply to it
    api_key: Optional[str] = None  # None = keep, "" = remove
    model: Optional[str] = None  # "" = back to the provider's default
    base_url: Optional[str] = None  # providers with a configurable URL (Ollama); "" = default
    effort: Optional[Literal["low", "medium", "high", "xhigh", "max"]] = None


def _hint(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 8 else ""


def provider_info(p: providers.Provider) -> dict:
    return {
        "id": p.id,
        "label": p.label,
        "needs_key": p.key_env is not None,
        "key_configured": p.configured,
        "key_hint": _hint(p.api_key),
        "key_url": p.key_url,
        "model": p.model,
        "default_model": p.default_model,
        "suggested_models": list(p.suggested_models),
        "base_url": p.url if p.base_url_env else None,
        "default_base_url": p.base_url if p.base_url_env else None,
        "vision": p.vision,
        "effort_supported": p.api == "anthropic",
    }


def _masked() -> dict:
    active = providers.active()
    return {
        "provider": active.id,
        "providers": [provider_info(p) for p in providers.PROVIDERS.values()],
        # Shortcuts for the active provider.
        "api_key_configured": active.configured,
        "api_key_hint": _hint(active.api_key),
        "model": active.model,
        "effort": settings.anthropic_effort,
        "env_file": str(ENV_FILE),
        "data_dir": str(settings.data_dir),
        "ocr_available": ocr_available(),
        "tesseract_path": tesseract_path(),
    }


@router.get("")
def get_settings():
    return _masked()


@router.put("")
def put_settings(body: SettingsIn):
    values = {}
    if body.provider is not None:
        if body.provider not in providers.PROVIDERS:
            raise HTTPException(422, f"Unknown provider '{body.provider}'")
        values["EXAMFORGE_PROVIDER"] = body.provider
    target = providers.PROVIDERS[body.provider] if body.provider else providers.active()
    if body.api_key is not None and target.key_env:
        values[target.key_env] = body.api_key.strip()
    if body.model is not None:
        values[target.model_env] = body.model.strip()
    if body.base_url is not None and target.base_url_env:
        values[target.base_url_env] = body.base_url.strip()
    if body.effort:
        values["ANTHROPIC_EFFORT"] = body.effort
    if values:
        update_env(values)
    return _masked()
