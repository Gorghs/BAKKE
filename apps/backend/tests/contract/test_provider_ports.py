from __future__ import annotations

import json

import httpx
import pytest

from app.adapters.ai.http_chat import HttpChatEmbeddings, HttpChatLLM
from app.adapters.providers import (
    ProviderConfigurationError,
    _build,
    known_provider_types,
    validate_provider_types,
)
from app.config import ResolvedCapability
from app.ports import EmbeddingsPort, LLMPort

CHAT_CFG = ResolvedCapability(
    name="text",
    provider_type="http_chat",
    api_base_url="http://provider.test/v1",
    api_key="test-key",
    model="test-model",
    source="env",
)

CAPTURED: dict = {"requests": []}


def _chat_llm(handler) -> HttpChatLLM:
    llm = HttpChatLLM(CHAT_CFG)
    llm._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url=f"{CHAT_CFG.api_base_url}/",
        headers={"Authorization": f"Bearer {CHAT_CFG.api_key}"},
    )
    return llm


def test_mock_llm_satisfies_port():
    from app.adapters.ai.mock_llm import MockLLMProvider

    llm = MockLLMProvider()
    assert isinstance(llm, LLMPort)
    assert llm.is_mock and llm.label == "DEVELOPMENT MOCK"
    out = llm.run_task("critique", {"scenario": {}, "anchors": [], "facts": [], "timeline": []})
    assert out["verdict"] in ("PASS", "FAIL")


def test_mock_embeddings_satisfies_port():
    from app.adapters.ai.embeddings_mock import MockEmbeddingProvider

    emb = MockEmbeddingProvider()
    assert isinstance(emb, EmbeddingsPort)
    vecs = emb.embed(["right hip fracture", "audio clip"])
    assert len(vecs) == 2 and len(vecs[0]) == 64


def test_http_chat_satisfies_port_and_contract():
    def handler(request: httpx.Request) -> httpx.Response:
        CAPTURED["requests"].append(request)
        body = json.loads(request.content)
        assert body["model"] == "test-model"
        assert "BAKKE" in body["messages"][0]["content"]
        content = json.dumps({"verdict": "PASS", "issues": [], "summary": "clean"})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    llm = _chat_llm(handler)
    assert isinstance(llm, LLMPort)
    assert llm.is_mock is False
    out = llm.run_task("critique", {"scenario": {"title": "x"}})
    assert out["verdict"] == "PASS"
    assert out["provider"] == ""
    req = CAPTURED["requests"][-1]
    assert req.url.path == "/v1/chat/completions"
    assert req.headers["Authorization"] == "Bearer test-key"


def test_http_chat_rejects_schema_violation():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"nope": 1})}}]})

    llm = _chat_llm(handler)
    with pytest.raises(ValueError, match="contract validation"):
        llm.run_task("critique", {"scenario": {}})


def test_http_chat_retries_without_response_format():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if "response_format" in body:
            return httpx.Response(400, text="response_format is not supported")
        content = json.dumps({"verdict": "FAIL", "issues": [{"type": "timing", "description": "t"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    llm = _chat_llm(handler)
    out = llm.run_task("critique", {"scenario": {}})
    assert out["verdict"] == "FAIL"
    assert "response_format" in seen[0]
    assert "response_format" not in seen[1]


def test_http_chat_embeddings_contract():
    emb = HttpChatEmbeddings(CHAT_CFG)
    emb._client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": [{"embedding": [0.5]}, {"embedding": [0.25]}]})
        ),
        base_url=f"{CHAT_CFG.api_base_url}/",
    )
    assert isinstance(emb, EmbeddingsPort)
    assert emb.embed(["a", "b"]) == [[0.5], [0.25]]


def test_unknown_provider_type_fails_clearly():
    cfg = ResolvedCapability(
        name="text", provider_type="vendorx", api_base_url="", api_key="k", model="m", source="env"
    )
    with pytest.raises(ProviderConfigurationError, match="unknown provider type"):
        _build("text", cfg)


def test_live_provider_without_key_fails_clearly():
    cfg = ResolvedCapability(
        name="text", provider_type="http_chat", api_base_url="", api_key="", model="m", source="env"
    )
    with pytest.raises(ProviderConfigurationError, match="no API key or base URL"):
        _build("text", cfg)
    cfg_missing_key = ResolvedCapability(
        name="text",
        provider_type="http_chat",
        api_base_url="http://x/v1",
        api_key="",
        model="m",
        source="env",
    )
    with pytest.raises(ProviderConfigurationError, match="API_KEY is empty"):
        _build("text", cfg_missing_key)


def test_catalogue_and_validation():
    known = known_provider_types()
    assert known["text"] == ["http_chat", "mock"]
    assert set(known["video_generation"]) == {"mock", "kling", "runway", "hailuo"}
    assert validate_provider_types() == []


def test_vendor_video_provider_without_key_fails_clearly():
    cfg = ResolvedCapability(
        name="video_generation",
        provider_type="kling",
        api_base_url="https://kling.example/v1",
        api_key="",
        model="",
        source="env",
    )
    with pytest.raises(ProviderConfigurationError, match="VIDEO_GENERATION_API_KEY is empty"):
        _build("video_generation", cfg)


def test_capability_detail_strips_userinfo(monkeypatch):
    from app.adapters import providers as providers_mod

    cfg = ResolvedCapability(
        name="text",
        provider_type="http_chat",
        api_base_url="https://user:pass@llm.internal/v1",
        api_key="super-secret-key",
        model="internal-7b",
        source="env",
    )
    monkeypatch.setattr(providers_mod, "_resolved", lambda _cap: cfg)
    detail = providers_mod._capability_detail("text")
    assert detail["base_url"] == "https://llm.internal/v1"
    assert "pass" not in str(detail)
    assert "super-secret-key" not in str(detail)


def test_provider_report_survives_broken_capability(monkeypatch):
    from app.adapters import providers as providers_mod

    def _boom():
        raise providers_mod.ProviderConfigurationError("LLM_API_KEY is empty")

    monkeypatch.setattr(providers_mod, "get_llm_provider", _boom)
    report = providers_mod.provider_report()

    legacy_keys = ("llm", "embeddings", "speech_to_text", "vision", "video_understanding", "video_generation")
    for key in legacy_keys:
        assert key in report, key
        assert report[key]["provider"], key
        assert isinstance(report[key]["is_mock"], bool), key
    assert "error" in report["llm"]
    assert "LLM_API_KEY is empty" in report["llm"]["error"]
    assert set(report["providers"]) == {
        "text",
        "embeddings",
        "speech",
        "vision",
        "video_understanding",
        "video_generation",
    }
    assert set(report["capabilities"]) == {"text", "vision", "embeddings", "video"}
    assert report["note"]
