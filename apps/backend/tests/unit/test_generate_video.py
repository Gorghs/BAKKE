from __future__ import annotations

from pathlib import Path

from app.adapters.persistence import SqlAlchemyUnitOfWork
from app.features.visualization import video_service as video_service_mod
from app.features.visualization.video_service import VideoService
from app.models import GeneratedVideo, Hypothesis, Scenario, VideoScenarioSpec
from app.workflows import GenerateVideoWorkflow
from tests.conftest import make_case


class _FakeVideoProvider:
    """Deterministic stand-in for a render provider (no ffmpeg needed)."""

    name = "fake-video"
    label = "fake-video-label"
    is_mock = True
    model = "fake-model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str, out_path: str, duration: float, scene=None) -> dict:
        self.calls.append(out_path)
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"\x00")
        return {"path": out_path, "duration": duration, "format": "mp4", "is_mock": True}


def _make_scenario(db, dev_user) -> Scenario:
    case = make_case(db, dev_user, name="Video Case")
    hyp = Hypothesis(
        case_id=case.id,
        hypothesis_id="H-001",
        title="Candidate",
        description="candidate summary",
        origin="INITIAL",
        extra={},
    )
    db.add(hyp)
    db.flush()
    sc = Scenario(
        case_id=case.id,
        hypothesis_id=hyp.id,
        status="SURVIVING",
        is_survivor=True,
        summary="candidate summary",
        participants=["Person A"],
        extra={"injury_location": "right hip"},
    )
    db.add(sc)
    db.flush()
    db.add(
        VideoScenarioSpec(
            scenario_id=sc.id,
            case_id=case.id,
            status="COMPLETE",
            spec={"total_duration": 6.0, "label": "1", "shots": [], "visual_only": True},
            visual_prompt="Establishing shot of the hallway. NOT RECORDED FOOTAGE",
        )
    )
    db.commit()
    return sc


def test_video_output_path_unique_per_video_row(db, dev_user, monkeypatch):
    fake = _FakeVideoProvider()
    monkeypatch.setattr(video_service_mod, "get_video_provider", lambda: fake)
    scenario = _make_scenario(db, dev_user)
    svc = VideoService()

    first = GeneratedVideo(case_id=scenario.case_id, scenario_id=scenario.id, status="PENDING")
    db.add(first)
    db.flush()
    svc.generate_video(db, scenario, first)

    second = GeneratedVideo(case_id=scenario.case_id, scenario_id=scenario.id, status="PENDING")
    db.add(second)
    db.flush()
    svc.generate_video(db, scenario, second)

    assert first.video_path != second.video_path
    assert first.video_path.endswith(f"{scenario.id}-{first.id}.mp4")
    assert second.video_path.endswith(f"{scenario.id}-{second.id}.mp4")
    assert Path(first.video_path).exists()
    assert Path(second.video_path).exists()


def test_generate_video_workflow_notes_actual_video_provider(db, dev_user, monkeypatch):
    fake = _FakeVideoProvider()
    monkeypatch.setattr(video_service_mod, "get_video_provider", lambda: fake)
    monkeypatch.setattr("app.workflows.generate_video.get_video_provider", lambda: fake)
    scenario = _make_scenario(db, dev_user)

    wf = GenerateVideoWorkflow(SqlAlchemyUnitOfWork(db))
    result = wf.run(scenario.id)
    db.commit()

    assert wf.ctx.providers["video_generation"] == "fake-video-label (mock)"
    assert wf.ctx.snapshot()["providers"]["video_generation"] == "fake-video-label (mock)"
    assert result["video_id"]
    assert fake.calls, "the fake provider must have rendered the clip"
