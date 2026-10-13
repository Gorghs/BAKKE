from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Protocol

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.progress import JobProgress

# The progress bar budget, in one place so re-banding the bar is one edit.
# Extraction fills the low end, fusion and similar-case retrieval sit in the
# middle, the reasoning loop owns the 38..90 band, then completion.
PCT_EXTRACTION_START = 5
PCT_EXTRACTION_END = 20
PCT_FUSION = 25
PCT_SIMILAR = 30
PCT_REASONING_START = 38
PCT_REASONING_END = 90
PCT_REASONING_SCORING = 93
PCT_COMPLETE = 100


class Progress(Protocol):
    """Sink for live job progress. See ProgressReporter and NullProgress."""

    def report(self, stage: str, percent: int) -> None: ...

    def clear(self) -> None: ...


@contextmanager
def _own_session() -> Iterator[Session]:
    """Yield a session of our own that commits on success.

    Progress must be visible to other processes while the worker's analysis
    transaction stays open, so each report commits immediately. Reporting is
    best-effort: a failure here must never fail the job, so the exception is
    swallowed after the rollback.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class ProgressReporter:
    """Write live progress for one job, on a session of its own."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def report(self, stage: str, percent: int) -> None:
        with _own_session() as db:
            row = db.get(JobProgress, self.job_id)
            if row is None:
                db.add(JobProgress(job_id=self.job_id, stage=stage[:200], percent=_clamp(percent)))
            else:
                row.stage = stage[:200]
                row.percent = _clamp(percent)

    def clear(self) -> None:
        with _own_session() as db:
            row = db.get(JobProgress, self.job_id)
            if row is not None:
                db.delete(row)


class NullProgress:
    """No-op reporter for call paths without a job (tests, seeds)."""

    def report(self, stage: str, percent: int) -> None:
        return

    def clear(self) -> None:
        return


def read_progress(db: Session, job_id: str) -> JobProgress | None:
    return db.get(JobProgress, job_id)


def _clamp(percent: int) -> int:
    return max(0, min(100, int(percent)))
