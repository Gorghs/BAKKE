from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers import llm


def _completion(content: str) -> SimpleNamespace:
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _settings(interval: float, retries: int = 6) -> SimpleNamespace:
    return SimpleNamespace(LLM_CALL_MIN_INTERVAL=interval, LLM_MAX_RETRIES=retries)


@pytest.fixture(autouse=True)
def _reset_pacing_state():
    llm._last_call_started_at = None
    yield
    llm._last_call_started_at = None


class TestUpstreamPacing:
    """The Gemini web bridge is rate limited at the account level: a burst of
    calls trips BardErrorInfo 13 1155 and the account goes dark for minutes.
    Pacing between upstream attempts keeps a run under the limit, which matters
    most inside the repair loop, where retries would otherwise fire instantly."""

    def test_repair_retries_are_spaced(self, monkeypatch):
        monkeypatch.setattr(llm, "get_settings", lambda: _settings(30.0))
        ticks = iter([1000.0, 1001.0, 1031.0])
        sleeps: list[float] = []
        monkeypatch.setattr(llm, "time", SimpleNamespace(monotonic=lambda: next(ticks), sleep=sleeps.append))

        outputs = iter([_completion("definitely not json"), _completion('{"summary": "ok"}')])
        p = llm.OpenAILLMProvider(api_key="k", model="m", base_url="")
        p.client.chat.completions.create = lambda **kw: next(outputs)

        out = p.run_task("summarize_scenario", {"scenario": {}})

        assert out["summary"] == "ok"
        assert sleeps == [29.0]

    def test_no_pacing_when_interval_disabled(self, monkeypatch):
        monkeypatch.setattr(llm, "get_settings", lambda: _settings(0.0))
        sleeps: list[float] = []
        monkeypatch.setattr(llm, "time", SimpleNamespace(monotonic=lambda: 5.0, sleep=sleeps.append))

        outputs = iter([_completion("nope"), _completion('{"summary": "ok"}')])
        p = llm.OpenAILLMProvider(api_key="k", model="m", base_url="")
        p.client.chat.completions.create = lambda **kw: next(outputs)

        p.run_task("summarize_scenario", {"scenario": {}})

        assert sleeps == []

    def test_max_retries_is_configurable(self, monkeypatch):
        monkeypatch.setattr(llm, "get_settings", lambda: _settings(0.0, retries=2))
        p = llm.OpenAILLMProvider(api_key="k", model="m", base_url="")
        assert p.client.max_retries == 2