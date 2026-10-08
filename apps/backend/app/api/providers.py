from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.adapters.providers import known_provider_types, provider_report
from app.adapters.persistence import runtime_config
from app.api.deps import get_current_user
from app.config import CAPABILITIES, _normalize_type, capability_config_errors, get_settings, resolve_capability
from app.models import User

router = APIRouter(prefix="/api", tags=["providers"])

_MASKED_KEYS = {
    "OPENAI_API_KEY",
    "LLM_API_KEY",
    "EMBEDDING_API_KEY",
    "STT_API_KEY",
    "VISION_API_KEY",
    "VIDEO_UNDERSTANDING_API_KEY",
    "VIDEO_GENERATION_API_KEY",
}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 16:
        return "••••"
    return f"{value[:4]}••••{value[-4:]}"


class ProviderConfigIn(BaseModel):
    # Generic provider configuration (preferred)
    LLM_PROVIDER_TYPE: str = Field(default="", description="text adapter id: mock | http_chat")
    LLM_API_BASE_URL: str = Field(default="", description="Base URL of the chat-completions API")
    LLM_API_KEY: str = Field(default="", description="API key for the text capability")
    LLM_MODEL: str = Field(default="", description="Model id for the text capability")

    EMBEDDING_PROVIDER_TYPE: str = Field(default="", description="embeddings adapter id: mock | http_chat")
    EMBEDDING_API_BASE_URL: str = Field(default="")
    EMBEDDING_API_KEY: str = Field(default="")
    EMBEDDING_MODEL: str = Field(default="")

    STT_PROVIDER_TYPE: str = Field(default="", description="speech adapter id: mock | http_chat")
    STT_API_BASE_URL: str = Field(default="")
    STT_API_KEY: str = Field(default="")
    STT_MODEL: str = Field(default="", description="Speech-to-text model id")

    VISION_PROVIDER_TYPE: str = Field(default="", description="vision adapter id: mock | http_chat")
    VISION_API_BASE_URL: str = Field(default="")
    VISION_API_KEY: str = Field(default="")
    VISION_MODEL: str = Field(default="")

    VIDEO_UNDERSTANDING_PROVIDER_TYPE: str = Field(default="", description="mock | http_chat")
    VIDEO_UNDERSTANDING_API_BASE_URL: str = Field(default="")
    VIDEO_UNDERSTANDING_API_KEY: str = Field(default="")
    VIDEO_UNDERSTANDING_MODEL: str = Field(default="")

    VIDEO_GENERATION_PROVIDER_TYPE: str = Field(default="", description="video adapter id: mock | vendor adapter")
    VIDEO_GENERATION_API_BASE_URL: str = Field(default="")
    VIDEO_GENERATION_API_KEY: str = Field(default="")
    VIDEO_GENERATION_MODEL: str = Field(default="")

    # Legacy names (kept so existing clients keep working; see app.config)
    LLM_PROVIDER: str = Field(default="", description="legacy: mock | openai")
    OPENAI_API_KEY: str = Field(default="", description="legacy shared key")
    OPENAI_MODEL: str = Field(default="", description="legacy shared model")
    EMBEDDING_PROVIDER: str = Field(default="", description="legacy: mock | openai")
    EMBEDDING_MODEL: str = Field(default="", description="legacy embedding model")
    STT_PROVIDER: str = Field(default="", description="legacy: mock | openai")
    VISION_PROVIDER: str = Field(default="", description="legacy: mock | openai")
    VIDEO_UNDERSTANDING_PROVIDER: str = Field(default="", description="legacy: mock | openai")
    VIDEO_GENERATION_PROVIDER: str = Field(default="", description="legacy: mock | vendor id")


def _validate_provider_types(body: ProviderConfigIn) -> None:
    """Reject unknown adapter ids on write — never store a type that would
    later fall back silently."""
    known = known_provider_types()
    data = body.model_dump()
    errors: list[str] = []
    for spec in CAPABILITIES.values():
        for key in spec.type_keys:
            raw = (data.get(key) or "").strip()
            if not raw:
                continue
            if _normalize_type(raw) not in known[spec.name]:
                errors.append(f"{key}: unknown provider type {raw!r} (known: {', '.join(known[spec.name])})")
    if errors:
        raise HTTPException(status_code=422, detail=errors)


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
    _validate_provider_types(body)
    data = body.model_dump()
    settings = get_settings()

    def effective_lookup(key: str) -> str:
        if key in data:
            return (data.get(key) or "").strip()
        return runtime_config.get_value(key)

    errors = capability_config_errors(
        lambda name: resolve_capability(name, settings, runtime_lookup=effective_lookup)
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    stored = runtime_config.set_values(data)
    report = provider_report()
    report["stored_keys"] = list(stored.keys())
    report["configured_keys"] = {key: bool(runtime_config.get_value(key)) for key in runtime_config.RUNTIME_KEYS}
    report["masked_keys"] = {
        key: _mask(runtime_config.get_value(key)) for key in _MASKED_KEYS if runtime_config.get_value(key)
    }
    return report
