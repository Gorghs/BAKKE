from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import BadRequestError

from app.providers.llm import OpenAILLMProvider


def _bad_request(message: str = "Failed to validate JSON. Please adjust your prompt.") -> BadRequestError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return BadRequestError(message, response=response, body={"error": {"message": message, "code": "json_validate_failed"}})


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _provider_with(create) -> OpenAILLMProvider:
    p = OpenAILLMProvider(api_key="k", model="m", base_url="")
    p.client.chat.completions.create = create
    return p


class TestGenerationRepair:
    """Real providers fail in three ways the mock never does: transient 400s
    (Groq `json_validate_failed`, which the SDK does not retry), unparseable
    output, and schema-invalid output. One bounded repair loop per failure
    keeps a single bad generation from failing a whole job attempt."""

    def test_transient_bad_request_is_retried(self):
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _bad_request()
            return _completion('{"summary": "ok"}')

        out = _provider_with(create).run_task("summarize_scenario", {"scenario": {}})
        assert out["summary"] == "ok"
        assert calls["n"] == 2

    def test_schema_invalid_output_is_repaired_with_the_error(self):
        seen_messages: list[list] = []
        outputs = iter(
            [
                _completion('{"facts": ["a string instead of an object"], "entities": []}'),
                _completion('{"facts": [{"statement": "the door was unlocked at 21:12"}], "entities": []}'),
            ]
        )

        def create(**kwargs):
            seen_messages.append(kwargs["messages"])
            return next(outputs)

        out = _provider_with(create).run_task("extract_evidence", {"text": "the door was unlocked", "evidence_type": "TEXT"})
        assert out["facts"][0]["statement"] == "the door was unlocked at 21:12"
        # the repair round must carry the validation feedback back to the model
        repair_text = str(seen_messages[1])
        assert "facts.0" in repair_text or "valid dictionary" in repair_text

    def test_unparseable_output_is_repaired(self):
        outputs = iter(
            [
                _completion("definitely not json"),
                _completion('{"summary": "recovered"}'),
            ]
        )
        out = _provider_with(lambda **kwargs: next(outputs)).run_task("summarize_scenario", {"scenario": {}})
        assert out["summary"] == "recovered"

    def test_exhausted_repairs_raise_and_surface(self):
        def create(**kwargs):
            return _completion('{"facts": ["still wrong"]}')

        p = _provider_with(create)
        with pytest.raises(ValueError, match="extract_evidence"):
            p.run_task("extract_evidence", {"text": "x"})

    def test_bad_repairs_are_bounded(self):
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            raise _bad_request()

        p = _provider_with(create)
        with pytest.raises(ValueError, match="summarize_scenario"):
            p.run_task("summarize_scenario", {"scenario": {}})
        assert calls["n"] == 3
