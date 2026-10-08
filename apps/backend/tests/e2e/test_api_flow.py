from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from app.adapters.persistence import runtime_config


def test_health_reports_database(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "database": True}


def test_capabilities_discovery_shape(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    # original contract keys preserved
    for key in ("llm", "embeddings", "speech_to_text", "vision", "video_understanding", "video_generation"):
        assert key in body
    assert body["llm"]["is_mock"] is True
    # generic discovery payload from the brief
    assert set(body["capabilities"]) == {"text", "vision", "embeddings", "video"}
    assert body["capabilities"] == {"text": False, "vision": False, "embeddings": False, "video": False}
    text = body["providers"]["text"]
    assert text["provider"] == "mock"
    assert text["configured"] is False
    assert text["model"] == ""
    assert text["is_mock"] is True


def test_provider_put_rejects_unknown_types(client):
    r = client.put("/api/providers", json={"LLM_PROVIDER_TYPE": "bogus"})
    assert r.status_code == 422
    assert "bogus" in r.json()["detail"][0]


def test_provider_put_masks_keys_and_reports_configured(client):
    try:
        r = client.put(
            "/api/providers",
            json={
                "LLM_PROVIDER_TYPE": "http_chat",
                "LLM_API_BASE_URL": "https://llm.internal/v1",
                "LLM_API_KEY": "secret-key-123456",
                "LLM_MODEL": "internal-7b",
            },
        )
        assert r.status_code == 200
        r = client.get("/api/providers")
        body = r.json()
        assert body["capabilities"]["text"] is True
        assert body["providers"]["text"]["provider"] == "http_chat"
        assert body["providers"]["text"]["model"] == "internal-7b"
        assert body["providers"]["text"]["api_key_set"] is True
        assert "secret-key-123456" not in str(body)
        assert body["masked_keys"]["LLM_API_KEY"].startswith("secr")
        assert body["configured_keys"]["LLM_API_KEY"] is True
    finally:
        runtime_config.clear()


def test_provider_put_rejects_invalid_base_url_before_write(client):
    try:
        ok = client.put(
            "/api/providers",
            json={
                "LLM_PROVIDER_TYPE": "http_chat",
                "LLM_API_BASE_URL": "https://llm.internal/v1",
                "LLM_API_KEY": "secret-key-123456",
                "LLM_MODEL": "internal-7b",
            },
        )
        assert ok.status_code == 200

        bad = client.put(
            "/api/providers",
            json={
                "LLM_PROVIDER_TYPE": "http_chat",
                "LLM_API_BASE_URL": "file:///etc/llm",
                "LLM_API_KEY": "secret-key-123456",
                "LLM_MODEL": "internal-7b",
            },
        )
        assert bad.status_code == 422
        assert any("LLM_API_BASE_URL" in e for e in bad.json()["detail"])

        body = client.get("/api/providers").json()
        assert body["providers"]["text"]["base_url"] == "https://llm.internal/v1"
        assert body["capabilities"]["text"] is True
        assert "file:///etc/llm" not in str(body)
    finally:
        runtime_config.clear()


def test_provider_put_masks_short_keys_completely(client):
    try:
        r = client.put(
            "/api/providers",
            json={
                "LLM_PROVIDER_TYPE": "http_chat",
                "LLM_API_BASE_URL": "https://llm.internal/v1",
                "LLM_API_KEY": "shorty123456",
                "LLM_MODEL": "internal-7b",
            },
        )
        assert r.status_code == 200
        body = client.get("/api/providers").json()
        assert body["masked_keys"]["LLM_API_KEY"] == "••••"
        assert "shorty123456" not in str(body)
    finally:
        runtime_config.clear()


def test_replay_manifest_404_before_any_run(client):
    case = client.post("/api/cases", json={"name": "No Run"}).json()
    r = client.get(f"/api/cases/{case['id']}/replay/manifest")
    assert r.status_code == 404


def _create_analyzed_case(client, engine, raw_text: str) -> tuple[str, str]:
    """Create a case, upload evidence, run the analysis job synchronously."""
    from app.infrastructure.jobs.tasks import run_job
    from app.models import Job

    case = client.post("/api/cases", json={"name": "E2E Case", "description": "flow"}).json()
    ev = client.post(
        f"/api/cases/{case['id']}/evidence",
        data={"item_type": "INVESTIGATOR_REPORT", "title": "Report 1", "raw_text": raw_text},
    )
    assert ev.status_code == 200, ev.text

    job_resp = client.post(f"/api/cases/{case['id']}/analyze")
    assert job_resp.status_code == 200
    job_id = job_resp.json()["job_id"]

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        job = db.get(Job, job_id)
        assert job is not None
        run_job(db, job)
        db.commit()
        assert job.status == "SUCCEEDED", job.error
    return case["id"], job_id


def test_full_analysis_flow(client, engine):
    raw = (
        "At approximately 14:05 the witness observed Person C near the east corridor. "
        "Door logs record the lab entrance at 14:11. The mechanism remains undetermined."
    )
    case_id, _job_id = _create_analyzed_case(client, engine, raw)

    status = client.get(f"/api/cases/{case_id}/analysis/status").json()
    assert status["status"] == "SUCCEEDED"
    assert status["progress"] == 100
    assert status["result"]["hypotheses_generated"] >= 1
    assert status["result"]["run_id"]
    assert status["result"]["manifest"]

    facts = client.get(f"/api/cases/{case_id}/facts").json()
    assert facts, "extraction should produce facts from raw text"

    audit = client.get(f"/api/cases/{case_id}/audit").json()
    actions = [row["action"] for row in audit]
    assert "case_analyzed" in actions
    assert "similar_case_retrieval" in actions
    analyzed = next(row for row in audit if row["action"] == "case_analyzed")
    assert analyzed["prompt_version"] == "v1"
    assert analyzed["extra"]["run_id"] == status["result"]["run_id"]


def test_compare_endpoint_requires_two_scenarios(client, engine):
    case = client.post("/api/cases", json={"name": "Compare"}).json()
    r = client.post("/api/scenarios/compare", json={"scenario_ids": ["missing-1", "missing-2"]})
    assert r.status_code == 422


def test_compare_flow_returns_shared_and_differences(client, engine):
    from app.models import Hypothesis, Scenario

    case = client.post("/api/cases", json={"name": "Compare Flow"}).json()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    scenario_ids: list[str] = []
    with factory() as db:
        for i in range(2):
            hypothesis = Hypothesis(case_id=case["id"], hypothesis_id=f"H-10{i}", title=f"candidate {i}")
            db.add(hypothesis)
            db.flush()
            scenario = Scenario(
                case_id=case["id"],
                hypothesis_id=hypothesis.id,
                status="SURVIVING",
                is_survivor=True,
                summary=f"scenario {i}",
                participants=[f"Person {i}"],
            )
            db.add(scenario)
            db.flush()
            scenario_ids.append(scenario.id)
        db.commit()

    r = client.post("/api/scenarios/compare", json={"scenario_ids": scenario_ids})
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["shared"], list)
    assert isinstance(body["differences"], list)
    assert isinstance(body["discriminating"], list)
    assert body["differences"]
