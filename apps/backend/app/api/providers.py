from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models import User
from app.infrastructure.providers import runtime as runtime_config
from app.infrastructure.providers.registry import provider_report

router = APIRouter(prefix="/api", tags=["providers"])

_MASKED_KEYS = {
    "OPENAI_API_KEY",
    "VIDEO_GENERATION_API_KEY",
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "••••"
    return f"{value[:4]}••••{value[-4:]}"


class ProviderConfigIn(BaseModel):
    LLM_PROVIDER: str = Field(default="", description="mock | openai")
    OPENAI_API_KEY: str = Field(default="", description="Shared key for LLM, embeddings, STT, vision, video understanding")
    OPENAI_MODEL: str = Field(default="", description="Model for LLM / vision / video understanding")
    STT_MODEL: str = Field(default="", description="Speech-to-text model (e.g. whisper-1)")
    EMBEDDING_PROVIDER: str = Field(default="", description="mock | openai")
    EMBEDDING_MODEL: str = Field(default="", description="Embedding model (e.g. text-embedding-3-small)")
    STT_PROVIDER: str = Field(default="", description="mock | openai")
    VISION_PROVIDER: str = Field(default="", description="mock | openai")
    VIDEO_UNDERSTANDING_PROVIDER: str = Field(default="", description="mock | openai")
    VIDEO_GENERATION_PROVIDER: str = Field(default="", description="mock | kling | runway | hailuo")
    VIDEO_GENERATION_API_KEY: str = Field(default="", description="Video generation API key")
    VIDEO_GENERATION_MODEL: str = Field(default="", description="Video generation model")


@router.get("/providers")
def get_providers(user: User = Depends(get_current_user)) -> dict[str, Any]:
    report = provider_report()
    configured = {key: bool(runtime_config.get_value(key)) for key in runtime_config.RUNTIME_KEYS}
    masked = {
        key: _mask(runtime_config.get_value(key))
        for key in _MASKED_KEYS
        if runtime_config.get_value(key)
    }
    report["configured_keys"] = configured
    report["masked_keys"] = masked
    report["note"] = (
        "Runtime overrides are stored in the database and take effect without a restart. "
        "Anything not set here falls back to environment / .env. Keys are never returned unmasked."
    )
    return report


@router.put("/providers")
def update_providers(
    body: ProviderConfigIn, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    stored = runtime_config.set_values(body.model_dump())
    report = provider_report()
    report["stored_keys"] = list(stored.keys())
    report["configured_keys"] = {key: bool(runtime_config.get_value(key)) for key in runtime_config.RUNTIME_KEYS}
    report["masked_keys"] = {
        key: _mask(runtime_config.get_value(key)) for key in _MASKED_KEYS if runtime_config.get_value(key)
    }
    return report
