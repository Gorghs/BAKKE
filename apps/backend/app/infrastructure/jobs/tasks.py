from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.models import GeneratedVideo, Job, Scenario, VideoScenarioSpec
from app.features.analysis.analysis_service import AnalysisService
from app.features.visualization.video_service import VideoService


def run_job(db: Session, job: Job) -> Job:
    """Execute one background job. Returns the updated job."""
    job.status = "RUNNING"
    job.attempts += 1
    db.flush()
    try:
        if job.job_type == "ANALYZE_CASE":
            service = AnalysisService()
            result = service.analyze_case(db, job.case_id, job=job)
            job.result = result
            job.status = "SUCCEEDED"
            job.progress = 100
        elif job.job_type == "GENERATE_VIDEO":
            scenario_id = job.payload.get("scenario_id")
            scenario = db.get(Scenario, scenario_id)
            if not scenario:
                raise ValueError("scenario not found")
            video = GeneratedVideo(
                case_id=job.case_id,
                scenario_id=scenario_id,
                status="PENDING",
            )
            db.add(video)
            db.flush()
            svc = VideoService()
            spec = svc.build_spec(db, scenario)
            video.spec_id = spec.id
            svc.generate_video(db, scenario, video)
            job.result = {"video_id": video.id, "status": video.status}
            job.status = "SUCCEEDED"
            job.progress = 100
        else:
            raise ValueError(f"unknown job type: {job.job_type}")
    except Exception as exc:
        job.status = "FAILED"
        job.error = str(exc)[:2000]
    db.flush()
    return job


def claim_next_job(db: Session) -> Job | None:
    job = (
        db.query(Job)
        .filter(Job.status.in_(["PENDING", "RUNNING"]))
        .order_by(Job.created_at.asc())
        .first()
    )
    if job and job.status == "RUNNING" and job.attempts > 2:
        job.status = "FAILED"
        job.error = "max attempts exceeded (stale job)"
        db.flush()
        return None
    return job


def notify(db: Session) -> None:
    """Best-effort Redis pub/sub wake-up. Worker falls back to polling."""
    from app.config import get_settings

    settings = get_settings()
    if not settings.REDIS_URL:
        return
    try:
        import redis

        r = redis.from_url(settings.REDIS_URL)
        r.publish("bakke:jobs", "new")
    except Exception:
        pass


def enqueue(db: Session, case_id: str, job_type: str, payload: dict[str, Any] | None = None) -> Job:
    from app.infrastructure.jobs.audit_service import JobService

    job = JobService().create(db, case_id, job_type, payload)
    db.flush()
    notify(db)
    return job