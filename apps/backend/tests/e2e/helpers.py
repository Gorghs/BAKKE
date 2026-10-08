from __future__ import annotations

from sqlalchemy.orm import sessionmaker


def create_analyzed_case(client, engine, raw_text: str, name: str = "Replay Case") -> tuple[str, str]:
    """Create a case, upload one evidence item, run the analysis job synchronously."""
    from app.infrastructure.jobs.tasks import run_job
    from app.models import Job

    case = client.post("/api/cases", json={"name": name, "description": "replay flow"}).json()
    ev = client.post(
        f"/api/cases/{case['id']}/evidence",
        data={"item_type": "INVESTIGATOR_REPORT", "title": "Report 1", "raw_text": raw_text},
    )
    assert ev.status_code == 200, ev.text

    job_resp = client.post(f"/api/cases/{case['id']}/analyze")
    assert job_resp.status_code == 200, job_resp.text
    job_id = job_resp.json()["job_id"]

    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        job = db.get(Job, job_id)
        assert job is not None
        run_job(db, job)
        db.commit()
        assert job.status == "SUCCEEDED", job.error
    return case["id"], job_id
