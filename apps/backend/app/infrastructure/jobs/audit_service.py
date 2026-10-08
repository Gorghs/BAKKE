from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, Job


def log_audit(db: Session, case_id: str, action: str, **kwargs: Any) -> AuditEvent:
    ev = AuditEvent(case_id=case_id, action=action, **kwargs)
    db.add(ev)
    return ev


def list_audit(db: Session, case_id: str, limit: int = 200) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter_by(case_id=case_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )


class JobService:
    def create(self, db: Session, case_id: str, job_type: str, payload: dict[str, Any] | None = None) -> Job:
        job = Job(case_id=case_id, job_type=job_type, payload=payload or {})
        db.add(job)
        db.flush()
        return job

    def latest(self, db: Session, case_id: str, job_type: str) -> Job | None:
        return (
            db.query(Job)
            .filter_by(case_id=case_id, job_type=job_type)
            .order_by(Job.created_at.desc())
            .first()
        )