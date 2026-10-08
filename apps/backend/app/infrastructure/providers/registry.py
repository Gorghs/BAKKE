from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.infrastructure.providers.base import LLMProvider, EmbeddingProvider, SpeechToTextProvider, VisionProvider, VideoUnderstandingProvider, VideoGenerationProvider
from app.infrastructure.providers import runtime as runtime_config
from app.infrastructure.providers.embeddings import get_embedding_provider
from app.infrastructure.providers.llm import MockLLMProvider, OpenAILLMProvider
from app.infrastructure.providers.media import (
    MockSpeechToTextProvider,
    OpenAISpeechToTextProvider,
    MockVisionProvider,
    OpenAIVisionProvider,
    MockVideoUnderstandingProvider,
    OpenAIVideoUnderstandingProvider,
)
from app.infrastructure.providers.video import get_video_provider

settings = get_settings()


def _rt(key: str, env: str = "") -> str:
    """Runtime DB override, else environment / .env, else ''."""
    return runtime_config.get_resolved(key, env or getattr(settings, key, ""))


def get_llm_provider() -> LLMProvider:
    provider = _rt("LLM_PROVIDER", settings.LLM_PROVIDER).lower()
    api_key = _rt("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    model = _rt("OPENAI_MODEL", settings.OPENAI_MODEL)
    if provider == "mock" or not api_key:
        return MockLLMProvider()
    return OpenAILLMProvider(api_key=api_key, model=model)


def get_stt_provider() -> SpeechToTextProvider:
    provider = _rt("STT_PROVIDER", settings.STT_PROVIDER).lower()
    api_key = _rt("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    model = _rt("STT_MODEL", settings.STT_MODEL)
    if provider == "openai" and api_key:
        return OpenAISpeechToTextProvider(api_key=api_key, model=model)
    return MockSpeechToTextProvider()


def get_vision_provider() -> VisionProvider:
    provider = _rt("VISION_PROVIDER", settings.VISION_PROVIDER).lower()
    api_key = _rt("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    model = _rt("OPENAI_MODEL", settings.OPENAI_MODEL)
    if provider == "openai" and api_key:
        return OpenAIVisionProvider(api_key=api_key, model=model)
    return MockVisionProvider()


def get_video_understanding_provider() -> VideoUnderstandingProvider:
    provider = _rt("VIDEO_UNDERSTANDING_PROVIDER", settings.VIDEO_UNDERSTANDING_PROVIDER).lower()
    api_key = _rt("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    model = _rt("OPENAI_MODEL", settings.OPENAI_MODEL)
    if provider == "openai" and api_key:
        return OpenAIVideoUnderstandingProvider(api_key=api_key, model=model)
    return MockVideoUnderstandingProvider()


def provider_report() -> dict[str, Any]:
    """Expose which provider handles which capability (privacy requirement)."""
    llm = get_llm_provider()
    emb = get_embedding_provider()
    stt = get_stt_provider()
    vision = get_vision_provider()
    vu = get_video_understanding_provider()
    vg = get_video_provider()
    return {
        "llm": {"provider": llm.name, "is_mock": llm.is_mock, "label": getattr(llm, "label", "")},
        "embeddings": {"provider": emb.name, "is_mock": emb.is_mock},
        "speech_to_text": {"provider": stt.name, "is_mock": stt.is_mock},
        "vision": {"provider": vision.name, "is_mock": vision.is_mock},
        "video_understanding": {"provider": vu.name, "is_mock": vu.is_mock},
        "video_generation": {"provider": vg.name, "is_mock": vg.is_mock},
        "note": "Evidence is only sent to providers that are explicitly configured. Mock providers keep everything local.",
    }
