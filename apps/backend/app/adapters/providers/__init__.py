"""Provider catalogue and factories.

This package is the ONLY place that maps a configured ``provider_type`` to a
concrete adapter class. Core application code depends on the ports in
``app.ports``; adding support for a new provider means registering an adapter
here — never editing workflows, features or domain code.

Provider types:
    text / embeddings / speech / vision / video_understanding: "mock" | "http_chat"
    video_generation: "mock" | <vendor adapter id>
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterator

from app.adapters.ai.embeddings_mock import MockEmbeddingProvider
from app.adapters.ai.http_chat import HttpChatEmbeddings, HttpChatLLM
from app.adapters.ai.mock_llm import MockLLMProvider
from app.adapters.media.http_chat import HttpChatSpeechToText, HttpChatVideoUnderstanding, HttpChatVision
from app.adapters.media.mock import (
    MockSpeechToTextProvider,
    MockVisionProvider,
    MockVideoUnderstandingProvider,
)
from app.adapters.media.vendor_video import (
    HailuoProvider,
    KlingProvider,
    MockVideoGenerationProvider,
    RunwayProvider,
)
from app.config import CAPABILITIES, ResolvedCapability, get_settings, resolve_capability, sanitize_base_url

HTTP_CHAT = "http_chat"
MOCK = "mock"

_KNOWN_TYPES: dict[str, dict[str, Callable[[ResolvedCapability], Any]]] = {
    "text": {
        MOCK: lambda cfg: MockLLMProvider(),
        HTTP_CHAT: HttpChatLLM,
    },
    "embeddings": {
        MOCK: lambda cfg: MockEmbeddingProvider(),
        HTTP_CHAT: HttpChatEmbeddings,
    },
    "speech": {
        MOCK: lambda cfg: MockSpeechToTextProvider(),
        HTTP_CHAT: HttpChatSpeechToText,
    },
    "vision": {
        MOCK: lambda cfg: MockVisionProvider(),
        HTTP_CHAT: HttpChatVision,
    },
    "video_understanding": {
        MOCK: lambda cfg: MockVideoUnderstandingProvider(),
        HTTP_CHAT: HttpChatVideoUnderstanding,
    },
    "video_generation": {
        MOCK: lambda cfg: MockVideoGenerationProvider(),
        "kling": KlingProvider,
        "runway": RunwayProvider,
        "hailuo": HailuoProvider,
    },
}


class ProviderConfigurationError(RuntimeError):
    """Raised when a live provider is selected but cannot be constructed."""


# Offline replay: every factory returns an explicit mock while this flag is
# set. Nothing outside replay/ tests may set it — live runs must never fall
# back to mocks silently.
_FORCE_MOCK: ContextVar[bool] = ContextVar("bakke_force_mock", default=False)


@contextmanager
def mock_providers() -> Iterator[None]:
    """Force every provider factory to an explicit DEVELOPMENT MOCK adapter."""
    token = _FORCE_MOCK.set(True)
    try:
        yield
    finally:
        _FORCE_MOCK.reset(token)


def known_provider_types() -> dict[str, list[str]]:
    return {cap: sorted(builders) for cap, builders in _KNOWN_TYPES.items()}


def _resolved(capability: str) -> ResolvedCapability:
    return resolve_capability(capability, get_settings())


def _build(capability: str, cfg: ResolvedCapability, *, force_mock: bool = False) -> Any:
    if force_mock or _FORCE_MOCK.get():
        return _KNOWN_TYPES[capability][MOCK](cfg)
    builders = _KNOWN_TYPES[capability]
    builder = builders.get(cfg.provider_type or MOCK)
    if builder is None:
        raise ProviderConfigurationError(
            f"unknown provider type {cfg.provider_type!r} for capability '{capability}' "
            f"(known: {', '.join(sorted(builders))})"
        )
    if cfg.provider_type not in (MOCK, "") and not (cfg.api_key or cfg.api_base_url):
        raise ProviderConfigurationError(
            f"capability '{capability}' is set to {cfg.provider_type!r} but no API key or base URL is "
            f"configured. Set {CAPABILITIES[capability].generic_api_key_key} / "
            f"{CAPABILITIES[capability].generic_base_url_key}, or select '{MOCK}' explicitly."
        )
    if cfg.provider_type not in (MOCK, "") and not cfg.api_key:
        raise ProviderConfigurationError(
            f"capability '{capability}' uses '{cfg.provider_type}' but {CAPABILITIES[capability].generic_api_key_key} is empty."
        )
    if cfg.provider_type == HTTP_CHAT and not cfg.model:
        raise ProviderConfigurationError(
            f"capability '{capability}' uses '{HTTP_CHAT}' but {CAPABILITIES[capability].generic_model_key} is empty."
        )
    return builder(cfg)


def get_llm_provider(*, force_mock: bool = False) -> Any:
    return _build("text", _resolved("text"), force_mock=force_mock)


def get_embedding_provider(*, force_mock: bool = False) -> Any:
    return _build("embeddings", _resolved("embeddings"), force_mock=force_mock)


def get_stt_provider(*, force_mock: bool = False) -> Any:
    return _build("speech", _resolved("speech"), force_mock=force_mock)


def get_vision_provider(*, force_mock: bool = False) -> Any:
    return _build("vision", _resolved("vision"), force_mock=force_mock)


def get_video_understanding_provider(*, force_mock: bool = False) -> Any:
    return _build("video_understanding", _resolved("video_understanding"), force_mock=force_mock)


def get_video_provider(*, force_mock: bool = False) -> Any:
    return _build("video_generation", _resolved("video_generation"), force_mock=force_mock)


def _capability_detail(capability: str) -> dict[str, Any]:
    try:
        cfg = _resolved(capability)
    except Exception as exc:
        return {
            "provider": MOCK,
            "configured": False,
            "model": "",
            "base_url": "",
            "api_key_set": False,
            "source": "",
            "is_mock": True,
            "error": str(exc),
        }
    detail: dict[str, Any] = {
        "provider": cfg.provider_type or MOCK,
        "configured": cfg.configured,
        "model": "" if cfg.is_mock else cfg.model,
        "base_url": sanitize_base_url(cfg.api_base_url),
        "api_key_set": bool(cfg.api_key),
        "source": cfg.source,
        "is_mock": cfg.is_mock,
    }
    if not cfg.is_mock:
        try:
            _build(capability, cfg)
        except Exception as exc:
            detail["configured"] = False
            detail["error"] = str(exc)
    return detail


def _capability_provider(capability: str, getter: Callable[[], Any]) -> dict[str, Any]:
    """Construct one provider for the report; a broken capability becomes an
    ``error`` entry instead of failing the whole discovery response."""
    try:
        provider = getter()
        entry: dict[str, Any] = {"provider": provider.name, "is_mock": provider.is_mock}
        if capability == "text":
            entry["label"] = getattr(provider, "label", "")
        return entry
    except Exception as exc:
        try:
            cfg = _resolved(capability)
            entry = {"provider": cfg.provider_type or MOCK, "is_mock": cfg.is_mock}
        except Exception:
            entry = {"provider": MOCK, "is_mock": True}
        if capability == "text":
            entry["label"] = ""
        entry["error"] = str(exc)
        return entry


def provider_report() -> dict[str, Any]:
    """Expose which provider handles which capability (privacy requirement).

    Keys 1-6 are the original report contract; ``capabilities`` and
    ``providers`` add the generic provider-configuration discovery payload.
    One misconfigured capability yields a per-capability ``error`` entry —
    discovery itself never fails.
    """
    providers = {name: _capability_detail(name) for name in CAPABILITIES}
    return {
        "llm": _capability_provider("text", get_llm_provider),
        "embeddings": _capability_provider("embeddings", get_embedding_provider),
        "speech_to_text": _capability_provider("speech", get_stt_provider),
        "vision": _capability_provider("vision", get_vision_provider),
        "video_understanding": _capability_provider("video_understanding", get_video_understanding_provider),
        "video_generation": _capability_provider("video_generation", get_video_provider),
        "capabilities": {
            "text": providers["text"]["configured"],
            "vision": providers["vision"]["configured"],
            "embeddings": providers["embeddings"]["configured"],
            "video": providers["video_generation"]["configured"] or providers["video_understanding"]["configured"],
        },
        "providers": providers,
        "note": "Evidence is only sent to providers that are explicitly configured. Mock providers keep everything local.",
    }


def validate_provider_types() -> list[str]:
    """Configuration errors for provider types (empty when valid)."""
    errors: list[str] = []
    for capability in CAPABILITIES:
        cfg = _resolved(capability)
        if cfg.is_mock:
            continue
        if cfg.provider_type not in _KNOWN_TYPES[capability]:
            errors.append(
                f"{CAPABILITIES[capability].generic_type_key}: unknown provider type {cfg.provider_type!r} "
                f"(known: {', '.join(sorted(_KNOWN_TYPES[capability]))})"
            )
            continue
        if cfg.provider_type != HTTP_CHAT:
            if not cfg.api_key:
                errors.append(
                    f"{CAPABILITIES[capability].generic_api_key_key}: required for provider type {cfg.provider_type!r}"
                )
    return errors
