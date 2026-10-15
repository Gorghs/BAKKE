"""Provider settings updates must not clear keys the caller did not mention.

Every field on ProviderConfigIn defaults to "", and runtime.set_values treats
an empty value as "delete this override". A full model_dump therefore made a
request that names one setting silently wipe every other one, including the API
key. That happened live during a demo rehearsal.
"""

from __future__ import annotations

from app.api import providers as providers_api
from app.api.providers import ProviderConfigIn


def test_update_sends_only_the_keys_the_caller_supplied(monkeypatch):
    captured: dict[str, str] = {}
    monkeypatch.setattr(providers_api.runtime_config, "set_values", lambda mapping: captured.update(mapping) or {})
    monkeypatch.setattr(providers_api, "provider_report", lambda: {})
    monkeypatch.setattr(providers_api.runtime_config, "get_value", lambda key: "")

    providers_api.update_providers(body=ProviderConfigIn(OPENAI_MODEL="qwen/qwen3.8-27b"), user=None)

    assert captured == {"OPENAI_MODEL": "qwen/qwen3.8-27b"}


def test_explicit_empty_string_still_clears_a_key(monkeypatch):
    captured: dict[str, str] = {}
    monkeypatch.setattr(providers_api.runtime_config, "set_values", lambda mapping: captured.update(mapping) or {})
    monkeypatch.setattr(providers_api, "provider_report", lambda: {})
    monkeypatch.setattr(providers_api.runtime_config, "get_value", lambda key: "")

    providers_api.update_providers(body=ProviderConfigIn(OPENAI_BASE_URL=""), user=None)

    assert captured == {"OPENAI_BASE_URL": ""}
