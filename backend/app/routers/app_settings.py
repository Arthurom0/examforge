"""Settings page: API key, model and effort, stored in the .env file (never returned in full)."""
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import ENV_FILE, settings, update_env
from ..services.extraction import ocr_available, tesseract_path

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    api_key: Optional[str] = None  # None = keep, "" = remove
    model: Optional[str] = None
    effort: Optional[Literal["low", "medium", "high", "xhigh", "max"]] = None


def _masked() -> dict:
    import os

    key = os.getenv("ANTHROPIC_API_KEY", "")
    return {
        "api_key_configured": bool(key),
        "api_key_hint": f"…{key[-4:]}" if len(key) > 8 else "",
        "model": settings.anthropic_model,
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
    if body.api_key is not None:
        values["ANTHROPIC_API_KEY"] = body.api_key.strip()
    if body.model:
        values["ANTHROPIC_MODEL"] = body.model.strip()
    if body.effort:
        values["ANTHROPIC_EFFORT"] = body.effort
    if values:
        update_env(values)
    return _masked()
