from __future__ import annotations

from app.models import Hypothesis, Scenario, ScenarioEvent
from app.services.video_service import VideoService, expand_visual_prompt
from tests.conftest import make_case

RAW_PROMPT = """Create a high-quality 3D animated visualization.

ENVIRONMENT:
An interior scene comprising: Hallway.

SHOT LIST:
Shot 01 - 0.0s to 4.0s (4.0s): Establishing view of the hallway. Camera: wide static shot.
Shot 02 - 4.0s to 8.0s (4.0s): The hallway holds, empty. Camera: slow push-in.

CONSTRAINTS:
Do not add people. Do not add objects.

OUTPUT:
16:9 High-quality 3D animated video. Label overlay: "BAKKE | HYPOTHESIS H-001 | 3D ANIMATED SCENARIO VISUALIZATION | NOT RECORDED FOOTAGE"."""


class _FakeLLM:
    name = "fake-llm"
    is_mock = False
    label = "FAKE"

    def __init__(self, reply: dict | None = None, exc: Exception | None = None) -> None:
        self.reply = reply or {}
        self.exc = exc
        self.calls: list[tuple[str, dict]] = []

    def run_task(self, task: str, payload: dict) -> dict:
        self.calls.append((task, payload))
        if self.exc:
            raise self.exc
        return self.reply


def _use_llm(monkeypatch, llm: _FakeLLM) -> None:
    import app.providers.registry as registry

    monkeypatch.setattr(registry, "get_llm_provider", lambda: llm)


class TestExpandVisualPrompt:
    def test_mock_expansion_returns_prompt_unchanged(self):
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is True
        assert meta["is_mock"] is True
        assert meta["provider"] == "mock-llm"

    def test_empty_prompt_skips_expansion(self):
        out, meta = expand_visual_prompt("")
        assert out == ""
        assert meta["used"] is False

    def test_payload_carries_only_the_visual_prompt(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": RAW_PROMPT})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is True
        task, payload = llm.calls[0]
        assert task == "expand_video_prompt"
        assert payload == {"prompt": RAW_PROMPT}

    def test_forbidden_content_is_rejected(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": RAW_PROMPT + " The witness claimed the most likely suspect."})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False
        assert "isolation" in meta["reason"]

    def test_evidence_ids_are_rejected(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": "Based on E-001 and E-002. NOT RECORDED FOOTAGE"})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False

    def test_missing_label_is_rejected(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": "A short clip of the hallway."})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False

    def test_oversized_expansion_is_rejected(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": "x" * 6500 + " NOT RECORDED FOOTAGE"})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False

    def test_expansion_that_drops_the_constraints_is_rejected(self, monkeypatch):
        llm = _FakeLLM(reply={"prompt": RAW_PROMPT.replace("CONSTRAINTS:", "NOTES:")})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False
        assert "CONSTRAINTS" in meta["reason"]

    def test_expansion_that_drops_the_timestamps_is_rejected(self, monkeypatch):
        stripped = RAW_PROMPT.replace("0.0s to 4.0s", "the first shot").replace("4.0s to 8.0s", "the second shot")
        llm = _FakeLLM(reply={"prompt": stripped})
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False
        assert "timestamp" in meta["reason"]

    def test_provider_error_falls_back(self, monkeypatch):
        llm = _FakeLLM(exc=RuntimeError("boom"))
        _use_llm(monkeypatch, llm)
        out, meta = expand_visual_prompt(RAW_PROMPT)
        assert out == RAW_PROMPT
        assert meta["used"] is False
        assert meta["reason"].startswith("expansion failed")


class TestBuildSpecRunsExpansion:
    def _scenario(self, db, dev_user):
        case = make_case(db, dev_user)
        hyp = Hypothesis(case_id=case.id, hypothesis_id="H-001", title="A", origin="INITIAL", extra={})
        db.add(hyp)
        db.flush()
        sc = Scenario(
            case_id=case.id,
            hypothesis_id=hyp.id,
            status="SURVIVING",
            is_survivor=True,
            summary="Hallway scene",
            cause_claim="",
            participants=["Person A"],
            extra={},
        )
        db.add(sc)
        db.flush()
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case.id,
                event_order=0,
                description="Person A entered the hallway.",
                event_type="KNOWN",
                linked_fact_ids=[],
                evidence_links=[],
                timing={"start": "20:05"},
                location="Hallway",
            )
        )
        db.commit()
        return sc

    def test_expansion_is_off_by_default(self, db, dev_user):
        sc = self._scenario(db, dev_user)
        spec = VideoService().build_spec(db, sc).spec
        assert spec["visual_prompt"] == spec["visual_prompt_director"]
        assert spec["visual_prompt"].endswith('NOT RECORDED FOOTAGE".')
        meta = spec["prompt_expansion"]
        assert meta["used"] is False
        assert "disabled" in meta["reason"]

    def test_expansion_runs_when_enabled(self, db, dev_user, monkeypatch):
        from app.services import video_service

        monkeypatch.setattr(video_service.settings, "VIDEO_PROMPT_EXPANSION", True)
        sc = self._scenario(db, dev_user)
        spec = VideoService().build_spec(db, sc).spec
        assert spec["visual_prompt"] == spec["visual_prompt_director"]
        assert spec["visual_prompt"].endswith('NOT RECORDED FOOTAGE".')
        meta = spec["prompt_expansion"]
        assert meta["used"] is True
        assert meta["is_mock"] is True
