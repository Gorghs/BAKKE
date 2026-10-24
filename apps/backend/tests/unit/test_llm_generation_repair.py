from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.adapters.ai import http_chat as http_chat_module
from app.adapters.ai.http_chat import HttpChatLLM
from app.config import ResolvedCapability
from app.domain.contracts import MAX_FACTS_PER_ITEM, MAX_HYPOTHESES_PER_CALL

CHAT_CFG = ResolvedCapability(
    name="text",
    provider_type="http_chat",
    api_base_url="https://api.example.com/v1",
    api_key="k",
    model="m",
    source="env",
)

# Saved before the autouse fixture swaps the module attribute out.
_REAL_PACE = http_chat_module._pace


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch):
    """Pacing is a wall-clock behaviour; the repair tests are not about it.

    ``LLM_CALL_MIN_INTERVAL`` is set in the demo .env, so leaving pacing on
    would make every generation test sleep between calls.
    """
    monkeypatch.setattr(http_chat_module, "_pace", lambda: None)


def _bad_request(message: str = "Failed to validate JSON. Please adjust your prompt.") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(400, request=request, text=message)
    return httpx.HTTPStatusError(message, request=request, response=response)


def _connection_error() -> httpx.ConnectError:
    return httpx.ConnectError("connection reset", request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"))


def _provider_with(complete) -> HttpChatLLM:
    """A provider whose upstream call is the given callable.

    ``complete`` receives the request body and returns ``(content,
    finish_reason)`` — the same tuple the HTTP adapter produces.
    """
    provider = HttpChatLLM(CHAT_CFG)
    provider._completion = complete  # type: ignore[method-assign]
    return provider


def _settings(**overrides) -> SimpleNamespace:
    base = dict(
        LLM_CALL_MIN_INTERVAL=0.0,
        LLM_MAX_RETRIES=0,
        LLM_MAX_OUTPUT_TOKENS=900,
        LLM_REASONING_EFFORT="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestGenerationRepair:
    """Real providers fail in three ways the mock never does: transient 400s
    (Groq `json_validate_failed`), unparseable output, and schema-invalid
    output. One bounded repair loop per failure keeps a single bad generation
    from failing a whole job attempt."""

    def test_transient_bad_request_is_retried(self):
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _bad_request()
            return '{"summary": "ok"}', "stop"

        out = _provider_with(complete).run_task("summarize_scenario", {"scenario": {}})
        assert out["summary"] == "ok"
        assert calls["n"] == 2

    def test_schema_invalid_output_is_repaired_with_the_error(self):
        seen_messages: list[list] = []
        outputs = iter(
            [
                ('{"facts": ["a string instead of an object"], "entities": []}', "stop"),
                ('{"facts": [{"statement": "the door was unlocked at 21:12"}], "entities": []}', "stop"),
            ]
        )

        def complete(request):
            seen_messages.append(request["messages"])
            return next(outputs)

        out = _provider_with(complete).run_task(
            "extract_evidence", {"text": "the door was unlocked", "evidence_type": "TEXT"}
        )
        assert out["facts"][0]["statement"] == "the door was unlocked at 21:12"
        # the repair round must carry the validation feedback back to the model
        repair_text = str(seen_messages[1])
        assert "facts.0" in repair_text or "valid dictionary" in repair_text

    def test_unparseable_output_is_repaired(self):
        outputs = iter(
            [
                ("definitely not json", "stop"),
                ('{"summary": "recovered"}', "stop"),
            ]
        )
        out = _provider_with(lambda request: next(outputs)).run_task("summarize_scenario", {"scenario": {}})
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
                ('{"facts": [{"statement": "store locked at 18:05"}]}', "length"),
                (
                    '{"facts": [{"statement": "store locked at 18:05"}, {"statement": "door found open at 07:50"}],'
                    ' "findings": [], "entities": [], "timeline_events": ['
                    '{"title": "Store locked", "time_start": "18:05"},'
                    '{"title": "Door found open", "time_start": "07:50"}]}',
                    "stop",
                ),
            ]
        )

        def complete(request):
            seen.append(request["messages"])
            return next(outputs)

        out = _provider_with(complete).run_task("extract_evidence", {"text": "locked at 18:05, found open at 07:50"})

        assert len(seen) == 2, "a budget-cut completion must be re-called, not accepted"
        assert len(out["timeline_events"]) == 2, "the repair round must return the sections the cut removed"
        assert "budget" in str(seen[1]), "the repair round must tell the model it ran out of output budget"

    def test_truncated_output_that_carries_the_timeline_is_kept(self):
        """A cut completion that already holds the needed sections is used.

        The extractor writes timeline_events first, so a completion cut at the
        budget usually still carries the section the old order lost. That
        partial is a truthful partial result (every entry source-linked), and
        fusion fills the rest from the facts, so re-calling only burns budget.
        """
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            return (
                '{"timeline_events": [{"title": "Store locked", "time_start": "18:05"}],'
                ' "facts": [{"statement": "store locked at 18:05"}], "findings": [], "entities": [',
                "length",
            )

        out = _provider_with(complete).run_task("extract_evidence", {"text": "locked at 18:05"})

        assert calls["n"] == 1, "a usable partial must not be discarded for another call"
        assert out["facts"], "the partial facts must survive"
        assert len(out["timeline_events"]) == 1, "the partial timeline must survive"

    def test_truncated_partial_without_facts_is_repaired(self):
        """A cut that lost the fact list carries nothing the pipeline can use."""
        seen: list[list] = []
        outputs = iter(
            [
                ('{"timeline_events": [{"title": "Store locked", "time_start": "18:05"}], "facts": [', "length"),
                (
                    '{"facts": [{"statement": "store locked at 18:05"}],'
                    ' "timeline_events": [{"title": "Store locked", "time_start": "18:05"}]}',
                    "stop",
                ),
            ]
        )

        def complete(request):
            seen.append(request["messages"])
            return next(outputs)

        out = _provider_with(complete).run_task("extract_evidence", {"text": "locked at 18:05"})

        assert len(seen) == 2
        assert out["facts"], "the repaired reply must supply the facts"

    def test_truncation_repair_drops_the_oversized_reply(self):
        """The repair request must not re-send the reply that filled the budget.

        Keeping it in context leaves the follow-up no room, so every attempt
        ends on the same cut (observed live: three attempts, all
        finish_reason=length).
        """
        seen: list[list] = []
        outputs = iter(
            [
                ('{"facts": [', "length"),
                (
                    '{"facts": [{"statement": "store locked at 18:05"}],'
                    ' "timeline_events": [{"title": "Store locked", "time_start": "18:05"}]}',
                    "stop",
                ),
            ]
        )

        def complete(request):
            seen.append(list(request["messages"]))
            return next(outputs)

        _provider_with(complete).run_task("extract_evidence", {"text": "locked at 18:05"})

        roles = [m["role"] for m in seen[1]]
        assert "assistant" not in roles, "the cut reply must not be replayed to the model"

    def test_exhausted_repairs_raise_and_surface(self):
        out = _provider_with(lambda request: ('{"facts": ["still wrong"]}', "stop"))
        with pytest.raises(ValueError, match="extract_evidence"):
            out.run_task("extract_evidence", {"text": "x"})

    def test_bad_repairs_are_bounded(self):
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            raise _bad_request()

        out = _provider_with(complete)
        with pytest.raises(ValueError, match="summarize_scenario"):
            out.run_task("summarize_scenario", {"scenario": {}})
        assert calls["n"] == 3

    def test_connection_error_is_retried(self):
        """A dropped connection is transient, not a bad request.

        Live, the route from the container to the provider lost a whole
        analysis run: two extractions and the hypothesis call ended on
        "Connection error" while the same calls succeeded seconds later.
        """
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _connection_error()
            return '{"summary": "ok"}', "stop"

        out = _provider_with(complete).run_task("summarize_scenario", {"scenario": {}})

        assert out["summary"] == "ok"
        assert calls["n"] == 2

    def test_connection_errors_are_bounded(self):
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            raise _connection_error()

        out = _provider_with(complete)
        with pytest.raises(ValueError, match="connection error"):
            out.run_task("summarize_scenario", {"scenario": {}})
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
        prompt = http_chat_module.system_prompt("generate_hypotheses")
        assert f"at most {MAX_HYPOTHESES_PER_CALL} hypotheses" in prompt

    def test_expansion_prompt_bounds_the_candidate_count(self):
        prompt = http_chat_module.system_prompt("expand_alternatives")
        assert f"at most {MAX_HYPOTHESES_PER_CALL} new candidates" in prompt

    def test_extraction_prompt_bounds_the_fact_count(self):
        prompt = http_chat_module.system_prompt("extract_evidence")
        assert f"at most {MAX_FACTS_PER_ITEM} facts" in prompt

    def test_truncated_hypothesis_set_that_carries_candidates_is_kept(self):
        calls = {"n": 0}

        def complete(request):
            calls["n"] += 1
            return (
                '{"hypotheses": [{"title": "Store opened with a second key",'
                ' "summary": "The padlock was cut and a copy used.",'
                ' "cause_claim": "A duplicate key was used.",'
                ' "events": [{"description": "Door opened between 04:00 and 07:50."}]}],'
                ' "extra": {"note": "cut here"',
                "length",
            )

        out = _provider_with(complete).run_task("generate_hypotheses", {"facts": []})

        assert calls["n"] == 1, "a usable partial must not be discarded for another call"
        assert len(out["hypotheses"]) == 1
        assert out["hypotheses"][0]["title"] == "Store opened with a second key"

    def test_truncated_hypothesis_set_without_a_candidate_is_repaired(self):
        seen: list[list] = []
        outputs = iter(
            [
                ('{"hypotheses": [{"title": "Store opened', "length"),
                ('{"hypotheses": [{"title": "Store opened with a second key", "summary": "s"}]}', "stop"),
            ]
        )

        def complete(request):
            seen.append(request["messages"])
            return next(outputs)

        out = _provider_with(complete).run_task("generate_hypotheses", {"facts": []})

        assert len(seen) == 2, "a cut with no complete candidate must be re-called"
        assert out["hypotheses"][0]["title"] == "Store opened with a second key"
        repair = seen[1][-1]["content"]
        assert "hypotheses" in repair, "the repair must ask for a shorter hypothesis set"
        assert "timeline_events" not in repair, "the repair must not talk about the extraction schema"

    def test_hypothesis_repair_drops_the_oversized_reply(self):
        seen: list[list] = []
        outputs = iter(
            [
                ('{"hypotheses": [{"title": "Store opened', "length"),
                ('{"hypotheses": [{"title": "Store opened with a second key"}]}', "stop"),
            ]
        )

        def complete(request):
            seen.append(list(request["messages"]))
            return next(outputs)

        _provider_with(complete).run_task("generate_hypotheses", {"facts": []})

        roles = [m["role"] for m in seen[1]]
        assert "assistant" not in roles, "the cut reply must not be replayed to the model"


class TestReasoningBudget:
    """Reasoning-model endpoints (Groq gpt-oss) bill hidden reasoning tokens to
    the same completion budget as the reply. At the default effort a 900-token
    call came back with empty content and finish_reason "length": the reasoning
    used the whole budget. reasoning_effort=low keeps the answer, and the
    parameter stays off the request for endpoints that reject it."""

    def _capture(self, monkeypatch, effort: str) -> dict:
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_REASONING_EFFORT=effort))
        seen: dict = {}

        def complete(request):
            seen.update(request)
            return '{"summary": "ok"}', "stop"

        _provider_with(complete).run_task("summarize_scenario", {"scenario": {}})
        return seen

    def test_reasoning_effort_is_sent_when_configured(self, monkeypatch):
        seen = self._capture(monkeypatch, "low")
        assert seen["reasoning_effort"] == "low"
        assert seen["max_tokens"] == 900

    def test_reasoning_effort_is_omitted_when_unset(self, monkeypatch):
        seen = self._capture(monkeypatch, "")
        assert "reasoning_effort" not in seen


class TestRetryBudget:
    """Free tiers answer 429 on bursts. One retry policy covers every capability
    that speaks the OpenAI-compatible dialect, so a rate limit costs a pause
    instead of a whole analysis attempt."""

    def _transport(self, responses: list[httpx.Response]) -> tuple[HttpChatLLM, list[httpx.Request]]:
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return responses[min(len(seen) - 1, len(responses) - 1)]

        provider = HttpChatLLM(CHAT_CFG)
        provider._client = httpx.Client(
            base_url="https://api.example.com/v1/",
            transport=httpx.MockTransport(handler),
            headers={"Authorization": "Bearer k"},
        )
        return provider, seen

    def test_rate_limit_is_retried_and_the_call_succeeds(self, monkeypatch):
        monkeypatch.setattr(http_chat_module.time, "sleep", lambda _s: None)
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_MAX_RETRIES=2))
        provider, seen = self._transport(
            [
                httpx.Response(429, json={"error": "rate limited"}, headers={"retry-after": "7"}),
                httpx.Response(
                    200, json={"choices": [{"message": {"content": '{"summary": "ok"}'}, "finish_reason": "stop"}]}
                ),
            ]
        )
        out = provider.run_task("summarize_scenario", {"scenario": {}})
        assert out["summary"] == "ok"
        assert len(seen) == 2

    def test_retry_waits_for_the_interval_the_server_asks_for(self, monkeypatch):
        slept: list[float] = []
        monkeypatch.setattr(http_chat_module.time, "sleep", lambda s: slept.append(s))
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_MAX_RETRIES=1))
        provider, _seen = self._transport(
            [
                httpx.Response(429, json={"error": "rate limited"}, headers={"retry-after": "7"}),
                httpx.Response(
                    200, json={"choices": [{"message": {"content": '{"summary": "ok"}'}, "finish_reason": "stop"}]}
                ),
            ]
        )
        provider.run_task("summarize_scenario", {"scenario": {}})
        assert slept == [7.0], "the server's retry-after must be honoured"

    def test_exhausted_rate_limit_surfaces_loudly(self, monkeypatch):
        monkeypatch.setattr(http_chat_module.time, "sleep", lambda _s: None)
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_MAX_RETRIES=1))
        provider, seen = self._transport([httpx.Response(429, json={"error": "rate limited"})])
        with pytest.raises(RuntimeError, match="429"):
            provider.run_task("summarize_scenario", {"scenario": {}})
        assert len(seen) == 2


class TestPacing:
    """Token-per-minute limits are per account, not per call, so consecutive
    chat calls are spaced by LLM_CALL_MIN_INTERVAL."""

    def test_consecutive_calls_are_spaced(self, monkeypatch):
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_CALL_MIN_INTERVAL=5.0))
        monkeypatch.setattr(http_chat_module, "_last_call_started_at", None)
        slept: list[float] = []
        clock = iter([100.0, 102.0, 102.1])
        monkeypatch.setattr(http_chat_module.time, "monotonic", lambda: next(clock))
        monkeypatch.setattr(http_chat_module.time, "sleep", lambda s: slept.append(s))

        http_chat_module._pace = _REAL_PACE
        try:
            _REAL_PACE()
            _REAL_PACE()
        finally:
            http_chat_module._pace = lambda: None

        assert slept == [3.0], "the second call waits out the remainder of the interval"

    def test_pacing_is_off_when_the_interval_is_unset(self, monkeypatch):
        monkeypatch.setattr(http_chat_module, "get_settings", lambda: _settings(LLM_CALL_MIN_INTERVAL=0.0))
        monkeypatch.setattr(http_chat_module, "_last_call_started_at", 0.0)

        def _boom(_s):
            raise AssertionError("pacing slept with the interval unset")

        monkeypatch.setattr(http_chat_module.time, "sleep", _boom)
        http_chat_module._pace = _REAL_PACE
        try:
            _REAL_PACE()
        finally:
            http_chat_module._pace = lambda: None
