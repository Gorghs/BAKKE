from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import app.prompts as prompts_pkg
from app.adapters import providers as providers_catalogue
from app.adapters.providers import known_provider_types, provider_report, validate_provider_types
from app.config import Settings
from app.prompts import LLM_TASKS, PROMPT_VERSION, TASK_SCHEMAS, system_prompt, validate_task_output
from app.workflows import manifest as manifest_mod
from app.workflows import replay as replay_mod
from app.workflows.context import AnalysisContext

BANNED_PHRASES = (
    "most likely",
    "probability",
    "likely cause",
    "what actually happened",
    "definitive cause",
)

_NEGATION_MARKERS = (
    "never",
    "not",
    "cannot",
    "do not",
    "don't",
    "no ",
    "without",
    "avoid",
    "refrain",
    "prohibit",
    "forbid",
    "nor",
)

PROMPT_DIR = Path(prompts_pkg.__file__).resolve().parent / PROMPT_VERSION


def _unnegated_banned_phrases(text: str) -> list[str]:
    offenders: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        low = sentence.lower()
        for phrase in BANNED_PHRASES:
            if phrase in low and not any(marker in low for marker in _NEGATION_MARKERS):
                offenders.append(f"{phrase!r} in sentence: {sentence.strip()}")
    return offenders


def _redirect_manifest_dir(monkeypatch, tmp_path: Path) -> None:
    settings = Settings(_env_file=None, DATA_DIR=str(tmp_path))
    monkeypatch.setattr(manifest_mod, "get_settings", lambda: settings)


def test_stage_records_success_on_normal_exit():
    ctx = AnalysisContext(case_id="case-1")
    with ctx.stage("extraction"):
        pass
    with ctx.stage("fusion"):
        pass
    assert [s["stage"] for s in ctx.stages] == ["extraction", "fusion"]
    for entry in ctx.stages:
        assert set(entry) == {"stage", "status", "seconds"}
        assert entry["status"] == "ok"
        assert isinstance(entry["seconds"], float)
        assert entry["seconds"] >= 0


def test_stage_records_error_status_and_reraises():
    ctx = AnalysisContext(case_id="case-1")
    with pytest.raises(RuntimeError, match="provider exploded"):
        with ctx.stage("reasoning"):
            raise RuntimeError("provider exploded")
    assert len(ctx.stages) == 1
    entry = ctx.stages[0]
    assert entry["stage"] == "reasoning"
    assert entry["status"] == "error"
    assert isinstance(entry["seconds"], float)
    assert entry["seconds"] >= 0


def test_stage_reraises_original_exception_type():
    ctx = AnalysisContext(case_id="case-1")
    with pytest.raises(ValueError):
        with ctx.stage("fusion"):
            raise ValueError("inner")


def test_snapshot_shape_and_prompt_version():
    ctx = AnalysisContext(case_id="case-9", job_id="job-3")
    snap = ctx.snapshot()
    assert set(snap) == {
        "run_id",
        "case_id",
        "job_id",
        "prompt_version",
        "providers",
        "stages",
        "elapsed_seconds",
    }
    assert snap["prompt_version"] == "v1" == PROMPT_VERSION
    assert snap["case_id"] == "case-9"
    assert snap["job_id"] == "job-3"
    assert isinstance(snap["run_id"], str) and snap["run_id"]
    assert isinstance(snap["elapsed_seconds"], float)


def test_snapshot_copies_stage_and_provider_collections():
    ctx = AnalysisContext(case_id="case-1")
    with ctx.stage("one"):
        pass
    snap = ctx.snapshot()
    with ctx.stage("two"):
        pass
    ctx.note_provider("text", "mock-llm", True)
    assert [s["stage"] for s in snap["stages"]] == ["one"]
    assert snap["providers"] == {}


def test_note_provider_labels_mock_entries():
    ctx = AnalysisContext(case_id="case-1")
    ctx.note_provider("text", "mock-llm", True)
    ctx.note_provider("vision", "live-vision", False)
    assert ctx.providers == {"text": "mock-llm (mock)", "vision": "live-vision"}


def _live_llm_settings() -> Settings:
    return Settings(
        _env_file=None,
        LLM_PROVIDER_TYPE="http_chat",
        LLM_API_BASE_URL="https://llm.internal/v1",
        LLM_API_KEY="test-key",
        LLM_MODEL="internal-7b",
    )


def test_note_providers_reflects_forced_mock_instances(monkeypatch):
    """A run forced through mock_providers() must report the mock instances
    it actually used, not the live model name from configuration."""
    from app.workflows import AnalyzeCaseWorkflow

    monkeypatch.setattr(providers_catalogue, "get_settings", lambda: _live_llm_settings())
    wf = AnalyzeCaseWorkflow(uow=None)
    with providers_catalogue.mock_providers():
        wf._note_providers()
    assert wf.ctx.providers["text"] == "DEVELOPMENT MOCK (mock)"
    assert "internal-7b" not in str(wf.ctx.providers)
    assert all(label.endswith("(mock)") for label in wf.ctx.providers.values())


def test_note_providers_reports_live_instance_when_not_forced(monkeypatch):
    from app.workflows import AnalyzeCaseWorkflow

    monkeypatch.setattr(providers_catalogue, "get_settings", lambda: _live_llm_settings())
    wf = AnalyzeCaseWorkflow(uow=None)
    wf._note_providers()
    assert wf.ctx.providers["text"] == "live:internal-7b"
    assert wf.ctx.providers["vision"] == "DEVELOPMENT MOCK (mock)"


def test_note_providers_defaults_to_mock_instances_in_test_env():
    from app.workflows import AnalyzeCaseWorkflow

    wf = AnalyzeCaseWorkflow(uow=None)
    wf._note_providers()
    assert set(wf.ctx.providers) == {
        "text",
        "embeddings",
        "vision",
        "video_understanding",
        "video_generation",
    }
    assert all(label.endswith("(mock)") for label in wf.ctx.providers.values())


def test_manifest_round_trip(monkeypatch, tmp_path):
    _redirect_manifest_dir(monkeypatch, tmp_path)
    payload = {"run_id": "run-abc", "prompt_version": "v1", "counts": {"surviving_scenarios": 2}}
    written = manifest_mod.write_manifest("case-42", "analysis", payload)
    expected = tmp_path / "replay" / "case-42.analysis.json"
    assert Path(written) == expected
    assert manifest_mod.manifest_path("case-42", "analysis") == expected
    loaded = manifest_mod.load_manifest("case-42", "analysis")
    assert loaded is not None
    assert loaded["manifest_version"] == 1
    assert loaded["kind"] == "analysis"
    assert "written_at" in loaded
    for key, value in payload.items():
        assert loaded[key] == value


def test_manifest_overwrite_same_case_and_kind(monkeypatch, tmp_path):
    _redirect_manifest_dir(monkeypatch, tmp_path)
    manifest_mod.write_manifest("case-7", "analysis", {"run_id": "first"})
    manifest_mod.write_manifest("case-7", "analysis", {"run_id": "second"})
    files = list((tmp_path / "replay").glob("case-7.analysis.json"))
    assert len(files) == 1
    loaded = manifest_mod.load_manifest("case-7", "analysis")
    assert loaded["run_id"] == "second"


def test_manifest_missing_returns_none(monkeypatch, tmp_path):
    _redirect_manifest_dir(monkeypatch, tmp_path)
    assert manifest_mod.load_manifest("never-written", "analysis") is None


def test_manifest_corrupt_content_returns_none(monkeypatch, tmp_path):
    _redirect_manifest_dir(monkeypatch, tmp_path)
    path = manifest_mod.manifest_path("case-bad", "analysis")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert manifest_mod.load_manifest("case-bad", "analysis") is None


def test_manifest_path_keeps_filename_inside_replay_dir(monkeypatch, tmp_path):
    _redirect_manifest_dir(monkeypatch, tmp_path)
    path = manifest_mod.manifest_path("../escape", "analysis")
    assert path == tmp_path / "replay" / "escape.analysis.json"
    assert "/" not in path.name


def test_mock_providers_flag_defaults_false_and_restores():
    assert providers_catalogue._FORCE_MOCK.get() is False
    with providers_catalogue.mock_providers():
        assert providers_catalogue._FORCE_MOCK.get() is True
    assert providers_catalogue._FORCE_MOCK.get() is False


def test_mock_providers_flag_restored_when_block_raises():
    with pytest.raises(ValueError, match="stop"):
        with providers_catalogue.mock_providers():
            assert providers_catalogue._FORCE_MOCK.get() is True
            raise ValueError("stop")
    assert providers_catalogue._FORCE_MOCK.get() is False


def test_replay_exposes_the_mock_forcing_context_manager():
    assert replay_mod.mock_providers is providers_catalogue.mock_providers
    assert replay_mod.REPLAY_JOB_TYPES == ("ANALYZE_CASE", "GENERATE_VIDEO")


def test_provider_report_capability_and_provider_keys():
    report = provider_report()
    assert set(report["capabilities"]) == {"text", "vision", "embeddings", "video"}
    assert set(report["providers"]) == {
        "text",
        "embeddings",
        "speech",
        "vision",
        "video_understanding",
        "video_generation",
    }
    for name, detail in report["providers"].items():
        assert {"provider", "configured", "model", "is_mock"} <= set(detail), name
        assert isinstance(detail["provider"], str) and detail["provider"]
        assert isinstance(detail["configured"], bool)
        assert isinstance(detail["is_mock"], bool)


def test_provider_report_all_mock_under_test_env():
    report = provider_report()
    legacy_keys = (
        "llm",
        "embeddings",
        "speech_to_text",
        "vision",
        "video_understanding",
        "video_generation",
    )
    for key in legacy_keys:
        assert key in report, key
        entry = report[key]
        assert isinstance(entry["provider"], str) and entry["provider"]
        assert isinstance(entry["is_mock"], bool)
        assert entry["is_mock"] is True, key
    for name, detail in report["providers"].items():
        assert detail["is_mock"] is True, name
        assert detail["configured"] is False, name
    assert report["capabilities"] == dict.fromkeys(("text", "vision", "embeddings", "video"), False)


def test_provider_report_note_states_explicit_configuration():
    note = provider_report()["note"]
    assert "explicitly configured" in note


def test_known_provider_types_match_catalogue():
    assert known_provider_types() == {
        "text": ["http_chat", "mock"],
        "embeddings": ["http_chat", "mock"],
        "speech": ["http_chat", "mock"],
        "vision": ["http_chat", "mock"],
        "video_understanding": ["http_chat", "mock"],
        "video_generation": ["hailuo", "kling", "mock", "runway"],
    }
    assert validate_provider_types() == []


def test_every_task_prompt_is_nonempty_and_names_bakke():
    assert PROMPT_VERSION == "v1"
    assert LLM_TASKS
    for task in LLM_TASKS:
        text = system_prompt(task)
        assert text.strip(), task
        assert "BAKKE" in text, task


def test_task_schema_keys_are_registered_tasks():
    assert set(TASK_SCHEMAS) <= set(LLM_TASKS)


def test_validate_task_output_accepts_correct_shape():
    extraction = {
        "facts": [{"statement": "the hallway lamp was displaced"}],
        "findings": [],
        "entities": [],
        "timeline_events": [],
    }
    out = validate_task_output("extract_evidence", extraction)
    assert out["facts"][0]["statement"] == "the hallway lamp was displaced"
    assert out["provider"] == ""

    hypotheses = {"hypotheses": [{"title": "candidate-a"}]}
    out2 = validate_task_output("generate_hypotheses", hypotheses)
    assert [h["title"] for h in out2["hypotheses"]] == ["candidate-a"]


def test_validate_task_output_rejects_wrong_shape():
    with pytest.raises(ValueError, match="contract validation"):
        validate_task_output("extract_evidence", {"facts": [{"category": "GENERAL"}]})
    with pytest.raises(ValueError, match="contract validation"):
        validate_task_output("generate_hypotheses", {"hypotheses": [{"summary": "title missing"}]})
    with pytest.raises(ValueError, match="contract validation"):
        validate_task_output("critique", {"issues": []})


def test_validate_task_output_rejects_non_object():
    with pytest.raises(ValueError, match="expected a JSON object"):
        validate_task_output("extract_evidence", ["not", "an", "object"])


def test_unknown_task_prompt_rejected():
    with pytest.raises(ValueError, match="unknown task"):
        system_prompt("settle_the_case")


def test_prompt_files_contain_no_unnegated_banned_phrases():
    files = sorted(PROMPT_DIR.glob("*.md"))
    assert files, f"no prompt files found in {PROMPT_DIR}"
    for path in files:
        offenders = _unnegated_banned_phrases(path.read_text(encoding="utf-8"))
        assert not offenders, f"{path.name}: {offenders}"


def test_banned_phrase_tripwire_detects_affirmative_use():
    assert _unnegated_banned_phrases("The most likely explanation is a fall.")
    assert not _unnegated_banned_phrases("Never offer a most likely explanation.")
    assert not _unnegated_banned_phrases("Do not state a likely cause.")


def test_system_prompt_instructs_json_only_and_carries_no_determination_preamble():
    for task in LLM_TASKS:
        text = system_prompt(task)
        assert "Return ONLY valid JSON" in text, task
        assert "You do NOT determine what happened" in text, task


def test_analysis_prompt_files_exclude_visual_production_instructions():
    for path in sorted(PROMPT_DIR.glob("*.md")):
        low = path.read_text(encoding="utf-8").lower()
        for term in ("shot list", "camera", "3d animated", "animation"):
            assert term not in low, f"{path.name} contains {term!r}"


def test_visual_director_prompt_stays_visual_only():
    from app.features.visualization.director import VideoDirectorAgent

    spec = {
        "environment": {"description": "hallway", "time_of_day": "evening", "lighting": "neutral"},
        "characters": [],
        "objects": [],
        "shots": [
            {
                "index": 1,
                "duration_seconds": 4.0,
                "description": "Establishing view of hallway.",
                "camera": "wide static establishing shot",
            }
        ],
        "unknown_periods": ["period without established events"],
        "constraints": [],
        "total_duration": 4.0,
        "aspect_ratio": "16:9",
        "label": "1",
    }
    prompt = VideoDirectorAgent()._build_prompt(spec)
    low = prompt.lower()
    for term in ("evidence", "witness", "score", "report", "explanation"):
        assert term not in low, f"visual prompt contains {term!r}"
    for phrase in BANNED_PHRASES:
        assert phrase not in low, f"visual prompt contains banned phrase {phrase!r}"
    assert "not recorded footage" in low


def test_visual_spec_excludes_forensic_payload():
    from app.features.visualization.director import build_visual_spec
    from app.models import Scenario, ScenarioEvent

    scenario = Scenario(
        case_id="case-1",
        hypothesis_id="hyp-1",
        summary="candidate summary text",
        participants=["Alex"],
    )
    events = [ScenarioEvent(description="moved the chair", event_type="KNOWN", location="study")]
    anchors = [{"anchor_id": "FA-77", "value": "12cm"}]
    spec = build_visual_spec(scenario, events, anchors)
    assert spec["visual_only"] is True
    dump = json.dumps(spec, default=str)
    assert "FA-77" not in dump
    assert "12cm" not in dump
