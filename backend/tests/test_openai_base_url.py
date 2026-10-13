from __future__ import annotations

from app.providers.llm import OpenAILLMProvider


class TestOpenAIBaseURL:
    def test_custom_endpoint_is_passed_to_the_client(self):
        p = OpenAILLMProvider(api_key="k", model="m", base_url="https://api.groq.com/openai/v1")
        assert "groq.com" in str(p.client.base_url)

    def test_default_endpoint_when_base_url_empty(self):
        p = OpenAILLMProvider(api_key="k", model="m", base_url="")
        assert "api.openai.com" in str(p.client.base_url)

    def test_client_retries_rate_limits(self):
        # Free-tier endpoints return 429 + retry-after; the default of 2
        # retries let one rate limit fail a whole job attempt live.
        p = OpenAILLMProvider(api_key="k", model="m", base_url="")
        assert p.client.max_retries == 6
