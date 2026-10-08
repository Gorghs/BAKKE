from __future__ import annotations

import json

import pytest

from app.workflows.manifest import manifest_path
from helpers import create_analyzed_case

RAW_TEXT = (
    "At approximately 14:05 the witness observed Person C near the east corridor. "
    "Door logs record the lab entrance at 14:11. The mechanism remains undetermined."
)


@pytest.fixture(autouse=True)
def _remove_replay_files_created_here():
    from app.config import get_settings

    replay_dir = get_settings().data_path / "replay"
    before = {p.name for p in replay_dir.glob("*")} if replay_dir.is_dir() else set()
    yield
    if replay_dir.is_dir():
        for p in replay_dir.glob("*"):
            if p.is_file() and p.name not in before:
                p.unlink(missing_ok=True)


def test_full_offline_replay_preserves_original_manifest(client, engine):
    case_id, _job_id = create_analyzed_case(client, engine, RAW_TEXT)

    r = client.get(f"/api/cases/{case_id}/replay/manifest")
    assert r.status_code == 200
    original_manifest = r.json()
    original_run_id = original_manifest["run_id"]
    assert original_run_id
    assert original_manifest["prompt_version"] == "v1"
    assert original_manifest["kind"] == "analysis"

    replay = client.post(f"/api/cases/{case_id}/replay", json={"job_type": "ANALYZE_CASE"})
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["status"] == "ANALYZED"
    assert body["replayed"] is True
    assert body["offline"] is True
    assert body["providers_forced"] == "mock"
    assert body["run_id"]
    assert body["run_id"] != original_run_id
    assert body["original_manifest"]["run_id"] == original_run_id

    again = client.get(f"/api/cases/{case_id}/replay/manifest")
    assert again.status_code == 200
    assert again.json()["run_id"] == original_run_id

    sidecar = manifest_path(case_id, "analysis.replay")
    assert sidecar.is_file()
    sidecar_data = json.loads(sidecar.read_text(encoding="utf-8"))
    assert sidecar_data["run_id"] == body["run_id"]
    assert sidecar_data["prompt_version"] == "v1"
    assert sidecar_data["providers"]
    assert all(label.endswith("(mock)") for label in sidecar_data["providers"].values())


def test_replay_rejects_unknown_job_type(client):
    case = client.post("/api/cases", json={"name": "Bad Job Type"}).json()
    r = client.post(f"/api/cases/{case['id']}/replay", json={"job_type": "SOMETHING_ELSE"})
    assert r.status_code == 422
    assert "unknown job_type: SOMETHING_ELSE" in r.json()["detail"]


def test_replay_generate_video_requires_scenario_id(client):
    case = client.post("/api/cases", json={"name": "Video Without Scenario"}).json()
    r = client.post(f"/api/cases/{case['id']}/replay", json={"job_type": "GENERATE_VIDEO"})
    assert r.status_code == 422
    assert "scenario_id" in r.json()["detail"]


def test_replay_case_without_prior_manifest(client, engine):
    case = client.post("/api/cases", json={"name": "No Manifest"}).json()
    ev = client.post(
        f"/api/cases/{case['id']}/evidence",
        data={"item_type": "INVESTIGATOR_REPORT", "title": "Report 1", "raw_text": RAW_TEXT},
    )
    assert ev.status_code == 200, ev.text

    assert (
        client.get(f"/api/cases/{case['id']}/replay/manifest").status_code == 404
    )

    replay = client.post(f"/api/cases/{case['id']}/replay", json={"job_type": "ANALYZE_CASE"})
    assert replay.status_code == 200, replay.text
    body = replay.json()
    assert body["replayed"] is True
    assert body["run_id"]
    assert body["original_manifest"] is None

    after = client.get(f"/api/cases/{case['id']}/replay/manifest")
    assert after.status_code == 200
    assert after.json()["run_id"] == body["run_id"]
