from __future__ import annotations

import pytest

from app.config import CAPABILITIES, Settings, resolve_capability, validate_settings

RUNTIME_OFF = lambda _key: ""  # noqa: E731 - settings-only resolution for these tests

_ENV_KEYS: list[str] = []
for _spec in CAPABILITIES.values():
    _ENV_KEYS.extend(
        [*(_spec.generic_type_key, *_spec.type_keys), *(_spec.generic_api_key_key, *_spec.api_key_keys),
         *(_spec.generic_model_key, *_spec.model_keys), *(_spec.generic_base_url_key, *_spec.base_url_keys)]
    )
_ENV_KEYS = sorted(set(_ENV_KEYS))


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch):
    """These tests reason about Settings alone — no ambient env leakage."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def _settings(**fields: str) -> Settings:
    return Settings(_env_file=None, **fields)


def _resolve(name: str, **fields: str):
    return resolve_capability(name, _settings(**fields), runtime_lookup=RUNTIME_OFF)


def test_defaults_are_explicit_mock():
    for name in ("text", "embeddings", "speech", "vision", "video_understanding", "video_generation"):
        cfg = _resolve(name)
        assert cfg.provider_type == "mock"
        assert cfg.is_mock
        assert not cfg.configured


def test_legacy_openai_alias_resolves_to_http_chat():
    cfg = _resolve("text", LLM_PROVIDER="openai", OPENAI_API_KEY="sk-test-123", OPENAI_MODEL="m1")
    assert cfg.provider_type == "http_chat"
    assert cfg.api_key == "sk-test-123"
    assert cfg.model == "m1"
    assert cfg.api_base_url  # legacy default applied for the shared key
    assert not cfg.is_mock
    assert cfg.configured


def test_generic_settings_win_over_legacy():
    cfg = _resolve(
        "text",
        LLM_PROVIDER_TYPE="http_chat",
        LLM_API_BASE_URL="https://llm.internal/v1",
        LLM_API_KEY="generic-key",
        LLM_MODEL="internal-7b",
        LLM_PROVIDER="openai",
        OPENAI_API_KEY="legacy-key",
        OPENAI_MODEL="legacy-model",
    )
    assert cfg.provider_type == "http_chat"
    assert cfg.api_base_url == "https://llm.internal/v1"
    assert cfg.api_key == "generic-key"
    assert cfg.model == "internal-7b"


def test_runtime_override_wins_over_settings():
    cfg = resolve_capability(
        "text",
        _settings(LLM_PROVIDER_TYPE="mock"),
        runtime_lookup=lambda key: {"LLM_PROVIDER_TYPE": "http_chat"}.get(key, ""),
    )
    assert cfg.provider_type == "http_chat"
    assert cfg.source == "runtime"


def test_validation_passes_for_mock():
    assert validate_settings(_settings()) == []


def test_validation_requires_live_config():
    # OPENAI_MODEL (legacy) must be cleared too — its compat default would
    # otherwise satisfy the model requirement.
    errors = validate_settings(_settings(LLM_PROVIDER_TYPE="http_chat", OPENAI_MODEL=""))
    assert any("LLM_API_BASE_URL" in e for e in errors)
    assert any("LLM_API_KEY" in e for e in errors)
    assert any("LLM_MODEL" in e for e in errors)


def test_production_validation_is_strict():
    s = _settings(APP_ENV="production", CORS_ALLOW_ORIGINS="*")
    errors = validate_settings(s)
    assert any("SECRET_KEY" in e for e in errors)
    assert any("CORS_ALLOW_ORIGINS" in e for e in errors)
    assert any("authentication" in e for e in errors)


def test_production_validation_accepts_hardened_config():
    s = _settings(
        APP_ENV="production",
        SECRET_KEY="a" * 32,
        CORS_ALLOW_ORIGINS="https://app.example.com",
        FIREBASE_PROJECT_ID="p",
        FIREBASE_CLIENT_EMAIL="e@x.iam.gserviceaccount.com",
        FIREBASE_PRIVATE_KEY="key",
    )
    assert validate_settings(s) == []


def _production(**fields: str) -> Settings:
    base: dict[str, str] = {
        "APP_ENV": "production",
        "SECRET_KEY": "a" * 32,
        "CORS_ALLOW_ORIGINS": "https://app.example.com",
        "FIREBASE_PROJECT_ID": "p",
        "FIREBASE_CLIENT_EMAIL": "e@x.iam.gserviceaccount.com",
        "FIREBASE_PRIVATE_KEY": "key",
        "DATABASE_URL": "postgresql://bakke:pw@db:5432/bakke",
    }
    base.update(fields)
    return _settings(**base)


def test_base_url_rejects_non_http_schemes():
    for bad in ("file:///etc/bakke", "javascript:alert(1)", "llm.internal/v1", "//llm.internal/v1"):
        errors = validate_settings(
            _settings(LLM_PROVIDER_TYPE="http_chat", LLM_API_BASE_URL=bad, LLM_API_KEY="k", LLM_MODEL="m")
        )
        assert any("LLM_API_BASE_URL" in e and bad in e for e in errors), bad


def test_base_url_rejects_missing_netloc():
    errors = validate_settings(
        _settings(LLM_PROVIDER_TYPE="http_chat", LLM_API_BASE_URL="https:///v1", LLM_API_KEY="k", LLM_MODEL="m")
    )
    assert any("LLM_API_BASE_URL" in e and "has no host" in e for e in errors)


def test_base_url_accepts_http_and_https():
    for good in ("http://gateway.internal:8080/v1", "https://llm.example.com/v1"):
        errors = validate_settings(
            _settings(LLM_PROVIDER_TYPE="http_chat", LLM_API_BASE_URL=good, LLM_API_KEY="k", LLM_MODEL="m")
        )
        assert errors == [], good


def test_base_url_validation_applies_to_vendor_types():
    errors = validate_settings(
        _settings(
            VIDEO_GENERATION_PROVIDER_TYPE="kling",
            VIDEO_GENERATION_API_BASE_URL="file:///tmp/kling",
            VIDEO_GENERATION_API_KEY="k",
        )
    )
    assert any("VIDEO_GENERATION_API_BASE_URL" in e for e in errors)


def test_base_url_error_messages_do_not_leak_userinfo():
    errors = validate_settings(
        _settings(
            LLM_PROVIDER_TYPE="http_chat",
            LLM_API_BASE_URL="file://user:pass@llm.internal/v1",
            LLM_API_KEY="k",
            LLM_MODEL="m",
        )
    )
    joined = " ".join(errors)
    assert "LLM_API_BASE_URL" in joined
    assert "user:pass" not in joined


def test_sanitize_base_url_strips_userinfo():
    from app.config import sanitize_base_url

    assert sanitize_base_url("https://user:pass@host/v1") == "https://host/v1"
    assert sanitize_base_url("https://host:8443/v1") == "https://host:8443/v1"
    assert sanitize_base_url("https://user@host/v1") == "https://host/v1"
    assert sanitize_base_url("plain-value") == "plain-value"


def test_production_rejects_placeholder_secret_key():
    for weak in ("", "change-me", "changeme", "change-me-in-production", "shortkey1234"):
        errors = validate_settings(_production(SECRET_KEY=weak))
        assert any("set a strong SECRET_KEY" in e for e in errors), weak


def test_production_rejects_package_default_database_url():
    errors = validate_settings(_production(DATABASE_URL="sqlite:///./data/bakke.db"))
    assert any("DATABASE_URL" in e and "package default" in e for e in errors)


def test_production_accepts_explicit_database_urls():
    for url in ("sqlite:///./prod.db", "postgresql://db:5432/bakke"):
        assert validate_settings(_production(DATABASE_URL=url)) == [], url


def test_is_production_normalises_env_values():
    assert _settings(APP_ENV="production").is_production
    assert _settings(APP_ENV="prod").is_production
    assert _settings(APP_ENV=" production ").is_production
    assert _settings(APP_ENV="Production").is_production
    assert not _settings(APP_ENV="staging").is_production
    assert not _settings(APP_ENV="prod").is_development
    assert _settings(APP_ENV="development").is_development
