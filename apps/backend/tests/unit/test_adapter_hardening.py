from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.adapters.ai import mock_llm, rule_based
from app.adapters.ai.mock_llm import MockLLMProvider
from app.adapters.media import http_chat
from app.adapters.storage import LocalStorageProvider
from app.prompts import LLM_TASKS

# --- M14: explicit task -> rule-based implementation routing -----------------

_MINIMAL_PAYLOADS: dict[str, dict] = {
    "extract_evidence": {
        "text": "Person A entered the hallway at 10:00.",
        "evidence_type": "WITNESS_STATEMENT",
        "evidence_id": "E-001",
    },
    "generate_hypotheses": {"facts": [], "timeline": [], "anchors": [], "similar_cases": []},
    "critique": {"scenario": {"title": "s"}, "anchors": []},
    "revise": {"scenario": {"title": "s", "events": []}, "issues": []},
    "expand_alternatives": {"rejected_scenario": {}, "facts": [], "timeline": []},
    "summarize_scenario": {
        "scenario": {"title": "t", "participants": ["Person A"], "cause_claim": "c", "unknowns": ["u"]}
    },
    "similar_case_relevance": {"similar_cases": []},
    "compare_scenarios": {"scenarios": []},
}


def test_alias_map_covers_every_task_with_an_existing_function():
    assert set(mock_llm._TASK_IMPLEMENTATIONS) == set(LLM_TASKS)
    for task, fn_name in mock_llm._TASK_IMPLEMENTATIONS.items():
        assert callable(getattr(rule_based, fn_name, None)), task


def test_every_llm_task_runs_or_raises_explicit_value_error():
    provider = MockLLMProvider()
    for task in LLM_TASKS:
        try:
            out = provider.run_task(task, _MINIMAL_PAYLOADS[task])
        except ValueError as exc:
            assert str(exc) == f"no rule-based implementation for task {task}"
        else:
            assert isinstance(out, dict), task


def test_unmapped_task_raises_value_error_not_attribute_error(monkeypatch):
    monkeypatch.setattr(mock_llm, "_TASK_IMPLEMENTATIONS", {})
    with pytest.raises(ValueError, match="no rule-based implementation for task critique"):
        MockLLMProvider().run_task("critique", {"scenario": {}, "anchors": []})


def test_summarize_scenario_routes_to_rule_based_summarize():
    out = MockLLMProvider().run_task(
        "summarize_scenario",
        {"scenario": {"title": "t", "participants": ["Person A"], "cause_claim": "fell", "unknowns": []}},
    )
    assert isinstance(out, dict)
    assert "Participants: Person A." in out["summary"]


def test_extract_and_compare_keep_their_rule_based_routing():
    provider = MockLLMProvider()
    ext = provider.run_task(
        "extract_evidence",
        {"text": "Person A entered the hallway at 10:00.", "evidence_type": "WITNESS_STATEMENT", "evidence_id": "E-001"},
    )
    assert ext["facts"] and ext["facts"][0]["statement"].startswith("Person A entered")
    scenarios = [
        {"id": "sc-a", "hypothesis_label": "H-001", "participants": ["person a"], "supporting_evidence": ["E-001"]},
        {"id": "sc-b", "hypothesis_label": "H-002", "participants": ["person a"], "supporting_evidence": ["E-001"]},
    ]
    cmp_out = provider.run_task("compare_scenarios", {"scenarios": scenarios})
    assert cmp_out["note"] == "Comparison is descriptive; no probability claim is made."


def test_unknown_task_still_raises_unknown_task_error():
    with pytest.raises(ValueError, match="unknown task: nope"):
        MockLLMProvider().run_task("nope", {})


# --- M6: ffmpeg frame sampling ----------------------------------------------


class _FakeProc:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _fake_subprocess(created: list[Path], commands: list[list[str]], *, fail_ffmpeg: bool = False, stderr: str = ""):
    def run(cmd, capture_output: bool = False, text: bool = False, **kwargs):
        commands.append(list(cmd))
        if cmd[0] == "ffprobe":
            return _FakeProc(stdout="6.0\n")
        target = Path(cmd[-1])
        created.append(target)
        if fail_ffmpeg:
            return _FakeProc(returncode=1, stderr=stderr)
        target.write_bytes(b"jpeg-bytes")
        return _FakeProc()

    return SimpleNamespace(run=run)


def test_sample_frames_uses_unique_temp_dir_per_call(monkeypatch):
    created: list[Path] = []
    commands: list[list[str]] = []
    monkeypatch.setattr(http_chat, "subprocess", _fake_subprocess(created, commands))
    first = http_chat.sample_frames("video.mp4", n=3)
    second = http_chat.sample_frames("video.mp4", n=3)
    frame_dir = Path(first[0]).parent
    second_dir = Path(second[0]).parent
    try:
        assert len(first) == 3
        parents = {Path(p).parent for p in first}
        assert len(parents) == 1
        assert frame_dir.name.startswith("bakke_frames_")
        assert all(Path(p).is_file() for p in first)
        assert set(first).isdisjoint(second)
        assert second_dir != frame_dir
        assert not any(p.startswith("/tmp/bakke_frame_") for p in first + second)
        ss_values = {cmd[cmd.index("-ss") + 1] for cmd in commands if cmd[0] == "ffmpeg"}
        assert ss_values == {"0.0", "3.0", "6.0"}
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)
        shutil.rmtree(second_dir, ignore_errors=True)


def test_sample_frames_raises_on_ffmpeg_failure_with_stderr_tail(monkeypatch):
    created: list[Path] = []
    commands: list[list[str]] = []
    stderr = "HEAD_MARKER" + "y" * 500 + "TAIL_MARKER"
    monkeypatch.setattr(http_chat, "subprocess", _fake_subprocess(created, commands, fail_ffmpeg=True, stderr=stderr))
    with pytest.raises(RuntimeError) as excinfo:
        http_chat.sample_frames("bad.mp4", n=2)
    msg = str(excinfo.value)
    assert "ffmpeg frame extraction failed" in msg
    assert "exit 1" in msg
    assert "bad.mp4" in msg
    assert "TAIL_MARKER" in msg
    assert "HEAD_MARKER" not in msg
    assert created and not created[0].parent.exists()


# --- M10: storage path confinement ------------------------------------------


@pytest.fixture()
def storage() -> LocalStorageProvider:
    return LocalStorageProvider()


def test_storage_roundtrip_on_normal_nested_path(storage):
    rel = storage.save("case-1", "E-001", "note.txt", b"hello")
    assert not Path(rel).is_absolute()
    assert storage.exists(rel)
    assert storage.load(rel) == b"hello"
    storage.delete(rel)
    assert not storage.exists(rel)
    assert storage.load(rel) is None


def test_storage_rejects_absolute_path_outside_root(storage, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"secret")
    assert storage.load(str(outside)) is None
    assert storage.exists(str(outside)) is False
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.delete(str(outside))
    assert outside.exists()


def test_storage_accepts_absolute_path_inside_root(storage):
    rel = storage.save("case-1", "E-002", "inside.txt", b"in")
    assert storage.load(str(storage.root.resolve() / rel)) == b"in"


def test_storage_rejects_dotdot_traversal(storage, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")
    inner = storage.root.parent / "inner.txt"
    inner.write_bytes(b"inner")
    assert storage.load("../../outside.txt") is None
    assert storage.load("../inner.txt") is None
    assert storage.exists("../../outside.txt") is False
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.delete("../inner.txt")
    assert outside.exists() and inner.exists()


def test_storage_rejects_symlink_escape(storage, tmp_path):
    target_dir = tmp_path / "elsewhere"
    target_dir.mkdir()
    (target_dir / "linked.txt").write_bytes(b"linked")
    (storage.root / "linkdir").symlink_to(target_dir, target_is_directory=True)
    assert storage.load("linkdir/linked.txt") is None
    assert storage.exists("linkdir/linked.txt") is False
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.delete("linkdir/linked.txt")
    assert (target_dir / "linked.txt").exists()


def test_storage_save_rejects_escaping_case_id(storage, tmp_path):
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.save("../evil", "E-009", "f.txt", b"x")
    with pytest.raises(ValueError, match="escapes storage root"):
        storage.save(str(tmp_path), "E-010", "f.txt", b"x")
    assert not (storage.root.parent / "evil").exists()
    assert not list(tmp_path.glob("*__f.txt"))


def test_storage_save_sanitizes_filename_traversal(storage):
    rel = storage.save("case-1", "E-011", "../../evil.txt", b"y")
    assert rel == "case-1/E-011__evil.txt"
    assert storage.load(rel) == b"y"
    assert not (storage.root.parent / "evil.txt").exists()
