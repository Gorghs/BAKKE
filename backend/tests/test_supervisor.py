from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.jobs.supervisor import MAX_ATTEMPTS, STALE_PENDING_SECONDS, STALE_RUNNING_SECONDS, supervise
from app.models import AuditEvent, Job
from tests.conftest import make_case


def _ago(seconds: float) -> datetime:
    """Naive UTC timestamp, matching what SQLite's CURRENT_TIMESTAMP stores."""
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=seconds)


def _job(db, case, status: str, attempts: int = 0, age_seconds: float = 0.0) -> Job:
    job = Job(case_id=case.id, job_type="ANALYZE_CASE", status=status, attempts=attempts)
    db.add(job)
    db.flush()
    if age_seconds:
        job.updated_at = _ago(age_seconds)
    db.commit()
    db.refresh(job)
    return job


def _actions(db, case, action: str) -> list[AuditEvent]:
    return db.query(AuditEvent).filter_by(case_id=case.id, action=action).all()


class TestFailedJobRetry:
    def test_failed_job_with_attempts_left_is_requeued(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "FAILED", attempts=1)
        report = supervise(db)
        db.commit()
        assert job.status == "PENDING"
        assert job.error == ""
        assert job.id in report["requeued"]
        assert len(_actions(db, case, "job_requeued")) == 1

    def test_failed_job_at_max_attempts_stays_failed(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "FAILED", attempts=MAX_ATTEMPTS)
        report = supervise(db)
        db.commit()
        assert job.status == "FAILED"
        assert job.id not in report["requeued"]
        assert _actions(db, case, "job_requeued") == []


class TestStaleRunning:
    def test_stale_running_is_requeued(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "RUNNING", attempts=1, age_seconds=STALE_RUNNING_SECONDS + 60)
        report = supervise(db)
        db.commit()
        assert job.status == "PENDING"
        assert job.id in report["requeued"]

    def test_stale_running_at_max_attempts_fails(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "RUNNING", attempts=MAX_ATTEMPTS, age_seconds=STALE_RUNNING_SECONDS + 60)
        report = supervise(db)
        db.commit()
        assert job.status == "FAILED"
        assert "max attempts exceeded" in job.error
        assert job.id in report["failed"]
        assert len(_actions(db, case, "job_failed_stale")) == 1

    def test_fresh_running_is_untouched(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "RUNNING", attempts=1, age_seconds=10)
        report = supervise(db)
        db.commit()
        assert job.status == "RUNNING"
        assert report["requeued"] == []
        assert report["failed"] == []


class TestStalePendingReport:
    def test_stale_pending_is_reported_once(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "PENDING", age_seconds=STALE_PENDING_SECONDS + 60)
        first = supervise(db)
        db.commit()
        second = supervise(db)
        db.commit()
        assert job.id in first["stale_pending"]
        assert job.id not in second["stale_pending"]
        assert job.status == "PENDING"
        assert len(_actions(db, case, "job_queue_stalled")) == 1

    def test_fresh_pending_is_untouched(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "PENDING", age_seconds=10)
        report = supervise(db)
        db.commit()
        assert report["stale_pending"] == []
        assert _actions(db, case, "job_queue_stalled") == []

    def test_settled_job_clears_the_reported_marker(self, db, dev_user):
        case = make_case(db, dev_user)
        job = _job(db, case, "PENDING", age_seconds=STALE_PENDING_SECONDS + 60)
        supervise(db)
        db.commit()
        job.status = "RUNNING"
        db.commit()
        supervise(db)
        db.commit()
        job.status = "PENDING"
        job.updated_at = _ago(STALE_PENDING_SECONDS + 60)
        db.commit()
        report_again = supervise(db)
        db.commit()
        assert job.id in report_again["stale_pending"]


class TestReportShape:
    def test_report_counts_checked_jobs(self, db, dev_user):
        case = make_case(db, dev_user)
        _job(db, case, "PENDING", age_seconds=10)
        _job(db, case, "FAILED", attempts=1)
        report = supervise(db)
        db.commit()
        assert report["checked"] == 2
        assert set(report) == {"checked", "requeued", "failed", "stale_pending"}
