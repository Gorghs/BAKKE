"""SQLAlchemy implementations of the workflow persistence ports."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent, Case, EvidenceItem, Job
from app.prompts import PROMPT_VERSION


class SqlAlchemyAudit:
    """Append-only audit writer over the ``audit_events`` table."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        case_id: str,
        *,
        action: str,
        agent: str,
        provider: str = "",
        summary: str = "",
        input_object_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._db.add(
            AuditEvent(
                case_id=case_id,
                action=action,
                agent=agent,
                provider=provider,
                summary=(summary or "")[:4000],
                input_object_ids=input_object_ids or [],
                prompt_version=PROMPT_VERSION,
                extra=extra or {},
            )
        )
        self._db.flush()


class SqlAlchemyJobProgress:
    """Progress reporting bound to the currently executing job row."""

    def __init__(self, db: Session, job: Job) -> None:
        self._db = db
        self._job = job

    def set_progress(self, progress: int, stage: str) -> None:
        self._job.progress = max(0, min(int(progress), 100))
        self._job.result = {"stage": stage}
        self._db.flush()

    def set_result(self, result: dict[str, Any]) -> None:
        self._job.result = result
        self._db.flush()


class NullJobProgress:
    """No-op progress reporter (interactive runs without a job row)."""

    def set_progress(self, progress: int, stage: str) -> None:
        return None

    def set_result(self, result: dict[str, Any]) -> None:
        return None


class SqlAlchemyCaseStatus:
    def __init__(self, db: Session) -> None:
        self._db = db

    def set_status(self, case_id: str, status: str) -> None:
        case = self._db.get(Case, case_id)
        if case is None:
            raise ValueError(f"case not found: {case_id}")
        case.status = status
        self._db.flush()


class SqlAlchemyEvidenceStatus:
    def __init__(self, db: Session) -> None:
        self._db = db

    def mark_processed(self, evidence_pk: str, provider_label: str = "") -> None:
        ev = self._db.get(EvidenceItem, evidence_pk)
        if ev is None:
            raise ValueError(f"evidence not found: {evidence_pk}")
        ev.status = "PROCESSED"
        ev.extracted = True
        ev.provider_label = provider_label
        self._db.flush()

    def mark_failed(self, evidence_pk: str, error: str) -> None:
        ev = self._db.get(EvidenceItem, evidence_pk)
        if ev is None:
            raise ValueError(f"evidence not found: {evidence_pk}")
        ev.status = "FAILED"
        ev.extra = {**ev.extra, "extraction_error": error[:500]}
        self._db.flush()


class SqlAlchemyUnitOfWork:
    """Unit of work handed to workflows; adapters own all persistence."""

    def __init__(self, session: Session, job: Job | None = None) -> None:
        self._session = session
        self._audit = SqlAlchemyAudit(session)
        self._job: Any = SqlAlchemyJobProgress(session, job) if job is not None else NullJobProgress()
        self._case_status = SqlAlchemyCaseStatus(session)
        self._evidence_status = SqlAlchemyEvidenceStatus(session)

    @property
    def session(self) -> Session:
        # Escape hatch for legacy sub-services that still take a session
        # directly (extraction, fusion, reasoning). Workflows themselves use
        # the typed ports.
        return self._session

    @property
    def audit(self) -> SqlAlchemyAudit:
        return self._audit

    @property
    def job(self) -> Any:
        return self._job

    @property
    def case_status(self) -> SqlAlchemyCaseStatus:
        return self._case_status

    @property
    def evidence_status(self) -> SqlAlchemyEvidenceStatus:
        return self._evidence_status

    def flush(self) -> None:
        self._session.flush()

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
