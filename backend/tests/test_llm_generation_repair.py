from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, BadRequestError

from app.providers.base import MAX_HYPOTHESES_PER_CALL
from app.providers.llm import OpenAILLMProvider


def _bad_request(message: str = "Failed to validate JSON. Please adjust your prompt.") -> BadRequestError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return BadRequestError(message, response=response, body={"error": {"message": message, "code": "json_validate_failed"}})


def _connection_error() -> APIConnectionError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return APIConnectionError(request=request)


def _completion(content: str, finish_reason: str | None = "stop") -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason=finish_reason)]
    )


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

    def test_truncated_output_is_repaired_instead_of_accepted(self):
        """A completion cut at the token budget must not be accepted as-is.

        The partial JSON still validates because every list defaults to empty,
        so a budget cut silently drops the sections written after the cut
        (live: 5/5 items extracted, 0 timeline events).
        """
        seen: list[list] = []
        outputs = iter(
            [
                _completion('{"facts": [{"statement": "store locked at 18:05"}]}', finish_reason="length"),
                _completion(
                    '{"facts": [{"statement": "store locked at 18:05"}, {"statement": "door found open at 07:50"}],'
                    ' "findings": [], "entities": [], "timeline_events": ['
                    '{"title": "Store locked", "time_start": "18:05"},'
                    '{"title": "Door found open", "time_start": "07:50"}]}'
                ),
            ]
        )

        def create(**kwargs):
            seen.append(kwargs["messages"])
            return next(outputs)

        out = _provider_with(create).run_task("extract_evidence", {"text": "locked at 18:05, found open at 07:50"})

        assert len(seen) == 2, "a budget-cut completion must be re-called, not accepted"
        assert len(out["timeline_events"]) == 2, "the repair round must return the sections the cut removed"
        assert "budget" in str(seen[1]), "the repair round must tell the model it ran out of output budget"

    def test_truncated_output_that_carries_the_timeline_is_kept(self):
        """A cut completion that already holds the needed sections is used.

        The extractor now writes timeline_events first, so a completion cut at the
        budget usually still carries the section the old order lost. That partial
        is a truthful partial result (every entry source-linked), and fusion fills
        the rest from the facts, so re-calling it would only burn budget.
        """
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            return _completion(
                '{"timeline_events": [{"title": "Store locked", "time_start": "18:05"}],'
                ' "facts": [{"statement": "store locked at 18:05"}], "findings": [], "entities": [',
                finish_reason="length",
            )

        out = _provider_with(create).run_task("extract_evidence", {"text": "locked at 18:05"})

        assert calls["n"] == 1, "a usable partial must not be discarded for another call"
        assert out["facts"], "the partial facts must survive"
        assert len(out["timeline_events"]) == 1, "the partial timeline must survive"

    def test_truncated_partial_without_facts_is_repaired(self):
        """A cut that lost the fact list carries nothing the pipeline can use."""
        seen: list[list] = []
        outputs = iter(
            [
                _completion('{"timeline_events": [{"title": "Store locked", "time_start": "18:05"}], "facts": [', finish_reason="length"),
                _completion(
                    '{"facts": [{"statement": "store locked at 18:05"}],'
                    ' "timeline_events": [{"title": "Store locked", "time_start": "18:05"}]}'
                ),
            ]
        )

        def create(**kwargs):
            seen.append(kwargs["messages"])
            return next(outputs)

        out = _provider_with(create).run_task("extract_evidence", {"text": "locked at 18:05"})

        assert len(seen) == 2
        assert out["facts"], "the repaired reply must supply the facts"

    def test_truncation_repair_drops_the_oversized_reply(self):
        """The repair request must not re-send the reply that filled the budget.

        Keeping it in context leaves the follow-up no room, so every attempt ends
        on the same cut and the job fails (observed live: three attempts, all
        finish_reason=length).
        """
        seen: list[list] = []
        outputs = iter(
            [
                _completion('{"facts": [', finish_reason="length"),
                _completion(
                    '{"facts": [{"statement": "store locked at 18:05"}],'
                    ' "timeline_events": [{"title": "Store locked", "time_start": "18:05"}]}'
                ),
            ]
        )

        def create(**kwargs):
            seen.append(list(kwargs["messages"]))
            return next(outputs)

        _provider_with(create).run_task("extract_evidence", {"text": "locked at 18:05"})

        roles = [m["role"] for m in seen[1]]
        assert "assistant" not in roles, "the cut reply must not be replayed to the model"

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

    def test_connection_error_is_retried(self):
        """A dropped connection is transient, not a bad request.

        The SDK retries on its own budget first. Live, the route from the
        container to the provider still lost a whole analysis run: two
        extractions and the hypothesis call ended on "Connection error" while
        the same calls succeeded seconds later.
        """
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _connection_error()
            return _completion('{"summary": "ok"}')

        out = _provider_with(create).run_task("summarize_scenario", {"scenario": {}})

        assert out["summary"] == "ok"
        assert calls["n"] == 2

    def test_connection_errors_are_bounded(self):
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            raise _connection_error()

        p = _provider_with(create)
        with pytest.raises(ValueError, match="connection error"):
            p.run_task("summarize_scenario", {"scenario": {}})
        assert calls["n"] == 3


class TestHypothesisBudget:
    """The hypothesis call runs on the same output budget as the extraction.

    A candidate carries far more than a fact, so an unbounded hypothesis reply
    runs past the budget and every attempt ends on the same cut (observed live:
    3038 chars written, finish_reason=length, job failed on task
    'generate_hypotheses'). The prompt bounds the candidate count and the
    repair asks for a shorter set, and a cut that still holds complete
    candidates is used as it stands.
    """

    def test_prompt_bounds_the_candidate_count(self):
        prompt = OpenAILLMProvider(api_key="k", model="m", base_url="")._system_prompt("generate_hypotheses")
        assert f"at most {MAX_HYPOTHESES_PER_CALL} hypotheses" in prompt

    def test_expansion_prompt_bounds_the_candidate_count(self):
        prompt = OpenAILLMProvider(api_key="k", model="m", base_url="")._system_prompt("expand_alternatives")
        assert f"at most {MAX_HYPOTHESES_PER_CALL} new candidate" in prompt

    def test_truncated_hypothesis_set_that_carries_candidates_is_kept(self):
        calls = {"n": 0}

        def create(**kwargs):
            calls["n"] += 1
            return _completion(
                '{"hypotheses": [{"title": "Store opened with a second key",'
                ' "summary": "The padlock was cut and a copy used.",'
                ' "cause_claim": "A duplicate key was used.",'
                ' "events": [{"description": "Door opened between 04:00 and 07:50."}]}],'
                ' "extra": {"note": "cut here"',
                finish_reason="length",
            )

        out = _provider_with(create).run_task("generate_hypotheses", {"facts": []})

        assert calls["n"] == 1, "a usable partial must not be discarded for another call"
        assert len(out["hypotheses"]) == 1
        assert out["hypotheses"][0]["title"] == "Store opened with a second key"

    def test_truncated_hypothesis_set_without_a_candidate_is_repaired(self):
        seen: list[list] = []
        outputs = iter(
            [
                _completion('{"hypotheses": [{"title": "Store opened', finish_reason="length"),
                _completion('{"hypotheses": [{"title": "Store opened with a second key", "summary": "s"}]}'),
            ]
        )

        def create(**kwargs):
            seen.append(kwargs["messages"])
            return next(outputs)

        out = _provider_with(create).run_task("generate_hypotheses", {"facts": []})

        assert len(seen) == 2, "a cut with no complete candidate must be re-called"
        assert out["hypotheses"][0]["title"] == "Store opened with a second key"
        repair = seen[1][-1]["content"]
        assert "hypotheses" in repair, "the repair must ask for a shorter hypothesis set"
        assert "timeline_events" not in repair, "the repair must not talk about the extraction schema"

    def test_hypothesis_repair_drops_the_oversized_reply(self):
        seen: list[list] = []
        outputs = iter(
            [
                _completion('{"hypotheses": [{"title": "Store opened', finish_reason="length"),
                _completion('{"hypotheses": [{"title": "Store opened with a second key"}]}'),
            ]
        )

        def create(**kwargs):
            seen.append(list(kwargs["messages"]))
            return next(outputs)

        _provider_with(create).run_task("generate_hypotheses", {"facts": []})

        roles = [m["role"] for m in seen[1]]
        assert "assistant" not in roles, "the cut reply must not be replayed to the model"


class TestReasoningBudget:
    """Reasoning-model endpoints (Groq gpt-oss) bill hidden reasoning tokens to
    the same completion budget as the reply. At the default effort a 900-token
    call came back with empty content and finish_reason "length": the reasoning
    used the whole budget. reasoning_effort=low keeps the answer, and the
    parameter stays off the request for endpoints that reject it."""

    @staticmethod
    def _settings(effort: str) -> SimpleNamespace:
        return SimpleNamespace(
            LLM_CALL_MIN_INTERVAL=0.0,
            LLM_MAX_RETRIES=0,
            LLM_MAX_OUTPUT_TOKENS=900,
            LLM_REASONING_EFFORT=effort,
        )

    def _capture(self, monkeypatch, effort: str) -> dict:
        from app.providers import llm as llm_module

        monkeypatch.setattr(llm_module, "get_settings", lambda: self._settings(effort))
        seen: dict = {}

        def create(**kwargs):
            seen.update(kwargs)
            return _completion('{"summary": "ok"}')

        provider = OpenAILLMProvider(api_key="k", model="m", base_url="")
        provider.client.chat.completions.create = create
        provider.run_task("summarize_scenario", {"scenario": {}})
        return seen

    def test_reasoning_effort_is_sent_when_configured(self, monkeypatch):
        seen = self._capture(monkeypatch, "low")
        assert seen["reasoning_effort"] == "low"
        assert seen["max_tokens"] == 900

    def test_reasoning_effort_is_omitted_when_unset(self, monkeypatch):
        seen = self._capture(monkeypatch, "")
        assert "reasoning_effort" not in seen
