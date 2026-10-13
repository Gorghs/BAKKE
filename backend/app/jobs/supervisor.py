from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AuditEvent, Job

# Bounds mirroring claim_next_job in app/jobs/tasks.py (attempts > 2 fails).
MAX_ATTEMPTS = 3
# A PENDING job older than this with no worker picking it up means the worker
# is down or busy past its polling interval. Report only; nothing to repair.
STALE_PENDING_SECONDS = 300
# A RUNNING job this old is an orphan from a crashed worker session. The
# worker commits only after a job finishes, so an orphan carries no partial
# writes to clean up; it just needs requeueing. Configurable because pacing
# makes real runs last longer than the old 15-minute default.
STALE_RUNNING_SECONDS = get_settings().STALE_RUNNING_SECONDS
SUPERVISOR_INTERVAL_SECONDS = 60

# Job ids already reported as stale-pending, so one stall produces one
# AuditEvent instead of one per tick. Cleared when the job leaves PENDING.
_reported_stale: set[str] = set()


def _utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _age_seconds(job: Job, now: datetime) -> float:
    return (_utc(now) - _utc(job.updated_at)).total_seconds()


def _audit(db: Session, job: Job, action: str, summary: str) -> None:
    db.add(
        AuditEvent(
            case_id=job.case_id,
            action=action,
            category="SYSTEM",
            agent="JobSupervisor",
            output_object_id=job.id,
            summary=summary[:4000],
        )
    )


def supervise(db: Session, now: datetime | None = None) -> dict[str, Any]:
    """Inspect the job table between worker runs and repair what is repairable.

    Three rules, all bounded:

    - FAILED with attempts left: back to PENDING (same 3-attempt cap that
      claim_next_job applies to stale RUNNING rows).
    - RUNNING older than STALE_RUNNING_SECONDS: orphan from a crash, requeue
      unless attempts are exhausted, then fail it.
    - PENDING older than STALE_PENDING_SECONDS: report once per stall, change
      nothing (a stalled queue means the worker itself has a problem).

    Runs inside the worker loop between jobs, so the active job is never
    examined here. With more than one worker process the age thresholds and
    the attempt cap keep a foreign worker's in-flight job from being touched
    before it is genuinely stale. Every change writes an AuditEvent, which is
    how the report reaches the API (GET /api/cases/{id}/audit).
    """
    now = now or datetime.now(timezone.utc)
    report: dict[str, Any] = {"checked": 0, "requeued": [], "failed": [], "stale_pending": []}
    jobs = (
        db.query(Job)
        .filter(Job.status.in_(["PENDING", "RUNNING", "FAILED"]))
        .all()
    )
    report["checked"] = len(jobs)

    for job in jobs:
        if job.status != "PENDING":
            _reported_stale.discard(job.id)
        if job.status == "FAILED":
            if job.attempts >= MAX_ATTEMPTS:
                continue
            previous_error = job.error
            job.status = "PENDING"
            job.error = ""
            report["requeued"].append(job.id)
            note = f"previous error: {previous_error}" if previous_error else "no error recorded"
            _audit(
                db,
                job,
                "job_requeued",
                f"supervisor requeued {job.job_type} after failure "
                f"(attempt {job.attempts + 1} of {MAX_ATTEMPTS}); {note}",
            )
        elif job.status == "RUNNING":
            age = _age_seconds(job, now)
            if age <= STALE_RUNNING_SECONDS:
                continue
            if job.attempts >= MAX_ATTEMPTS:
                job.status = "FAILED"
                job.error = "max attempts exceeded (stale job)"
                report["failed"].append(job.id)
                _audit(
                    db,
                    job,
                    "job_failed_stale",
                    f"supervisor failed stale {job.job_type} after {int(age)}s "
                    f"with {job.attempts} attempts",
                )
            else:
                job.status = "PENDING"
                job.error = ""
                report["requeued"].append(job.id)
                _audit(
                    db,
                    job,
                    "job_requeued",
                    f"supervisor requeued stale RUNNING {job.job_type} "
                    f"after {int(age)}s (attempt {job.attempts + 1} of {MAX_ATTEMPTS})",
                )
        elif job.status == "PENDING":
            if job.id in _reported_stale:
                continue
            age = _age_seconds(job, now)
            if age <= STALE_PENDING_SECONDS:
                continue
            _reported_stale.add(job.id)
            report["stale_pending"].append(job.id)
            _audit(
                db,
                job,
                "job_queue_stalled",
                f"{job.job_type} pending for {int(age)}s; worker is down or behind",
            )

    db.flush()
    return report
