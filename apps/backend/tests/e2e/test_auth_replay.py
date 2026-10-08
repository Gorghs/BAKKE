from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

import app.api.deps as deps
from app.api.deps import get_current_user
from app.config import get_settings
from app.main import app as fastapi_app
from app.models import Case, GeneratedVideo, Hypothesis, Scenario, User
from app.workflows.manifest import manifest_path, write_manifest
from app.workflows.replay import replay_case
from helpers import create_analyzed_case

RAW_TEXT = (
    "At approximately 14:05 the witness observed Person C near the east corridor. "
    "Door logs record the lab entrance at 14:11. The mechanism remains undetermined."
)


def _factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def _as_user(user: User) -> None:
    fastapi_app.dependency_overrides[get_current_user] = lambda: user


def _clear_user_override() -> None:
    fastapi_app.dependency_overrides.pop(get_current_user, None)


def _foreign_user(engine) -> User:
    with _factory(engine)() as s:
        user = User(email="foreign@test.local", display_name="Foreign User")
        s.add(user)
        s.commit()
        s.refresh(user)
    return user


def _seed_case_with_scenarios(client, engine, count: int = 2) -> tuple[str, list[str]]:
    case = client.post("/api/cases", json={"name": "Ownership"}).json()
    scenario_ids: list[str] = []
    with _factory(engine)() as s:
        for i in range(count):
            hypothesis = Hypothesis(
                case_id=case["id"], hypothesis_id=f"H-00{i + 1}", title=f"hypothesis {i}"
            )
            s.add(hypothesis)
            s.flush()
            scenario = Scenario(
                case_id=case["id"],
                hypothesis_id=hypothesis.id,
                status="SURVIVING",
                is_survivor=True,
                summary=f"scenario {i}",
            )
            s.add(scenario)
            s.flush()
            scenario_ids.append(scenario.id)
        s.commit()
    return case["id"], scenario_ids


def _seed_video(engine, case_id: str, scenario_id: str, payload: bytes, directory) -> str:
    clip = directory / "clip.mp4"
    clip.write_bytes(payload)
    with _factory(engine)() as s:
        video = GeneratedVideo(
            case_id=case_id,
            scenario_id=scenario_id,
            status="READY",
            video_path=str(clip),
        )
        s.add(video)
        s.commit()
        s.refresh(video)
    return video.id


def test_scenario_video_requires_ownership(client, engine, tmp_path):
    case_id, scenario_ids = _seed_case_with_scenarios(client, engine)
    payload = b"fake-mp4-bytes-for-listing"
    video_id = _seed_video(engine, case_id, scenario_ids[0], payload, tmp_path)

    _as_user(_foreign_user(engine))
    foreign = client.get(f"/api/scenarios/{scenario_ids[0]}/video")
    assert foreign.status_code in (403, 404)

    _clear_user_override()
    owner = client.get(f"/api/scenarios/{scenario_ids[0]}/video")
    assert owner.status_code == 200, owner.text
    assert [v["id"] for v in owner.json()] == [video_id]


def test_video_stream_requires_ownership(client, engine, tmp_path):
    case_id, scenario_ids = _seed_case_with_scenarios(client, engine)
    payload = b"\x00\x00\x00\x18ftypmp42 fake video bytes"
    video_id = _seed_video(engine, case_id, scenario_ids[0], payload, tmp_path)

    _as_user(_foreign_user(engine))
    foreign = client.get(f"/api/videos/{video_id}/stream")
    assert foreign.status_code in (403, 404)

    _clear_user_override()
    owner = client.get(f"/api/videos/{video_id}/stream")
    assert owner.status_code == 200, owner.text
    assert owner.headers["content-type"].startswith("video/mp4")
    assert owner.content == payload


def test_compare_requires_ownership(client, engine):
    case_id, scenario_ids = _seed_case_with_scenarios(client, engine)

    _as_user(_foreign_user(engine))
    foreign = client.post("/api/scenarios/compare", json={"scenario_ids": scenario_ids})
    assert foreign.status_code in (403, 404)

    _clear_user_override()
    owner = client.post("/api/scenarios/compare", json={"scenario_ids": scenario_ids})
    assert owner.status_code == 200, owner.text
    body = owner.json()
    assert body["case_id"] == case_id
    assert len(body["scenarios"]) == 2


def test_compare_provider_misconfiguration_maps_to_503(client, engine, monkeypatch):
    _case_id, scenario_ids = _seed_case_with_scenarios(client, engine)

    def _boom():
        raise RuntimeError("provider not configured")

    monkeypatch.setattr("app.adapters.providers.get_llm_provider", _boom)
    r = client.post("/api/scenarios/compare", json={"scenario_ids": scenario_ids})
    assert r.status_code == 503
    assert "comparison provider failed" in r.json()["detail"]


def test_production_without_firebase_auth_returns_503(client):
    old_env = deps.settings.APP_ENV
    deps.settings.APP_ENV = "production"
    try:
        r = client.get("/api/me")
        assert r.status_code == 503
        assert r.json()["detail"] == "authentication not configured"
    finally:
        deps.settings.APP_ENV = old_env

    dev = client.get("/api/me")
    assert dev.status_code == 200
    assert dev.json()["is_dev"] is True


def test_replay_rejects_scenario_from_another_case(client, engine):
    case_id, _job_id = create_analyzed_case(client, engine, RAW_TEXT, name="Replay Target")
    other = client.post("/api/cases", json={"name": "Other Case"}).json()
    with _factory(engine)() as s:
        hypothesis = Hypothesis(case_id=other["id"], hypothesis_id="H-001", title="other")
        s.add(hypothesis)
        s.flush()
        scenario = Scenario(
            case_id=other["id"],
            hypothesis_id=hypothesis.id,
            status="SURVIVING",
            is_survivor=True,
        )
        s.add(scenario)
        s.commit()
        s.refresh(scenario)

    manifest = manifest_path(case_id, "analysis")
    original_bytes = manifest.read_bytes()

    r = client.post(
        f"/api/cases/{case_id}/replay",
        json={"job_type": "GENERATE_VIDEO", "scenario_id": scenario.id},
    )
    assert r.status_code == 404
    assert manifest.read_bytes() == original_bytes
    assert not manifest_path(case_id, f"video_{scenario.id}").exists()


def test_replay_case_refuses_foreign_scenario(engine):
    factory = _factory(engine)
    with factory() as s:
        owner = User(email="owner@replay.local", display_name="Owner")
        s.add(owner)
        s.commit()
        s.refresh(owner)
        case_a = Case(owner_id=owner.id, name="Case A", description="", status="DRAFT")
        case_b = Case(owner_id=owner.id, name="Case B", description="", status="DRAFT")
        s.add_all([case_a, case_b])
        s.commit()
        hypothesis = Hypothesis(case_id=case_b.id, hypothesis_id="H-001", title="b")
        s.add(hypothesis)
        s.flush()
        scenario = Scenario(
            case_id=case_b.id,
            hypothesis_id=hypothesis.id,
            status="SURVIVING",
            is_survivor=True,
        )
        s.add(scenario)
        s.commit()
        s.refresh(scenario)
        case_a_id, scenario_id = case_a.id, scenario.id

    with pytest.raises(ValueError):
        replay_case(case_a_id, "GENERATE_VIDEO", scenario_id, session_factory=factory)

    assert not manifest_path(case_a_id, f"video_{scenario_id}").exists()


def test_replay_manifest_kind_traversal_stays_inside_replay_dir(client, tmp_path):
    case = client.post("/api/cases", json={"name": "Traversal"}).json()

    r = client.get(f"/api/cases/{case['id']}/replay/manifest", params={"kind": "../../evil"})
    assert r.status_code == 404

    resolved = manifest_path(case["id"], "../../../evil")
    assert resolved.parent == get_settings().data_path / "replay"

    write_manifest(case["id"], "../../../evil", {"run_id": "probe"})
    escaped = [p for p in tmp_path.rglob("*evil*") if p.is_file() and "replay" not in p.parts]
    assert escaped == []


def test_replay_failure_restores_original_manifest(client, engine, monkeypatch):
    case_id, _job_id = create_analyzed_case(client, engine, RAW_TEXT)
    manifest = manifest_path(case_id, "analysis")
    original_bytes = manifest.read_bytes()
    assert original_bytes

    class _FailingWorkflow:
        def __init__(self, uow):
            self.uow = uow

        def run(self, cid):
            write_manifest(cid, "analysis", {"run_id": "clobbered-run"})
            raise RuntimeError("workflow failed mid-run")

    monkeypatch.setattr("app.workflows.replay.AnalyzeCaseWorkflow", _FailingWorkflow)

    with pytest.raises(RuntimeError):
        client.post(f"/api/cases/{case_id}/replay", json={"job_type": "ANALYZE_CASE"})

    assert manifest.read_bytes() == original_bytes
    assert not manifest_path(case_id, "analysis.replay").exists()
