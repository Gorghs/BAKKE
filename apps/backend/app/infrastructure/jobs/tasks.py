from __future__ import annotations

import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.adapters.persistence import SqlAlchemyUnitOfWork
from app.models import Case, Job
from app.ports import UnitOfWork
from app.workflows import AnalyzeCaseWorkflow, GenerateVideoWorkflow

logger = logging.getLogger(__name__)

# Thin dispatch table: jobs construct a unit of work and invoke exactly one
# workflow. All pipeline logic lives in app.workflows.
WorkflowHandler = Callable[[UnitOfWork, Job], dict[str, Any]]

HANDLERS: dict[str, WorkflowHandler] = {
    "ANALYZE_CASE": lambda uow, job: AnalyzeCaseWorkflow(uow, job_id=job.id).run(job.case_id),
    "GENERATE_VIDEO": lambda uow, job: GenerateVideoWorkflow(uow, job_id=job.id).run(
        job.payload.get("scenario_id", "")
    ),
}


def run_job(db: Session, job: Job) -> Job:
    """Execute one background job. Returns the updated job.

    On failure the partial workflow writes are discarded (rollback) and the
    job/case are re-marked in the same session so the worker's commit
    persists the failure instead of leaving the case in ANALYZING forever.
    """
    job.status = "RUNNING"
    job.attempts += 1
    db.flush()
    handler = HANDLERS.get(job.job_type)
    uow = SqlAlchemyUnitOfWork(db, job)
    try:
        if handler is None:
            raise ValueError(f"unknown job type: {job.job_type}")
        job.result = handler(uow, job)
        job.status = "SUCCEEDED"
        job.progress = 100
    except Exception as exc:
        logger.exception(
            "job=%s type=%s case=%s failed: %s", job.id, job.job_type, job.case_id, exc
        )
        db.rollback()
        job.status = "FAILED"
        job.error = str(exc)[:2000]
        job.attempts += 1
        if job.job_type == "ANALYZE_CASE":
            case = db.get(Case, job.case_id)
            if case is not None:
                case.status = "ERROR"
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
        logger.debug("redis publish unavailable; worker will poll", exc_info=True)


def enqueue(db: Session, case_id: str, job_type: str, payload: dict[str, Any] | None = None) -> Job:
    from app.infrastructure.jobs.audit_service import JobService

    job = JobService().create(db, case_id, job_type, payload)
    db.flush()
    notify(db)
    return job
