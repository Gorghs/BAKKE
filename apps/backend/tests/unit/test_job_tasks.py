from __future__ import annotations

from app.infrastructure.jobs import tasks
from app.models import Case, Fact, Job
from tests.conftest import make_case


def _committed_job(db, case, job_type: str = "ANALYZE_CASE") -> Job:
    job = Job(case_id=case.id, job_type=job_type, status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_run_job_failure_rolls_back_partial_writes(db, dev_user, monkeypatch):
    case = make_case(db, dev_user)
    job = _committed_job(db, case)

    def _failing(uow, _job):
        uow.session.add(Fact(case_id=_job.case_id, fact_id="F-001", statement="partial row"))
        uow.session.flush()
        uow.case_status.set_status(_job.case_id, "ANALYZING")
        raise RuntimeError("workflow exploded")

    monkeypatch.setitem(tasks.HANDLERS, "ANALYZE_CASE", _failing)
    result = tasks.run_job(db, job)

    assert result.status == "FAILED"
    assert result.error == "workflow exploded"
    assert result.attempts == 1
    # The flushed partial row must not survive the rollback.
    assert db.query(Fact).filter_by(case_id=case.id).count() == 0
    # The case must not be left in ANALYZING.
    assert db.get(Case, case.id).status == "ERROR"


def test_run_job_truncates_long_error_to_2000_chars(db, dev_user, monkeypatch):
    case = make_case(db, dev_user)
    job = _committed_job(db, case)

    def _failing(uow, _job):
        raise RuntimeError("x" * 5000)

    monkeypatch.setitem(tasks.HANDLERS, "ANALYZE_CASE", _failing)
    result = tasks.run_job(db, job)

    assert result.status == "FAILED"
    assert len(result.error) == 2000


def test_run_job_failure_on_other_job_type_leaves_case_status(db, dev_user, monkeypatch):
    case = make_case(db, dev_user)
    job = _committed_job(db, case, job_type="GENERATE_VIDEO")

    def _failing(uow, _job):
        raise RuntimeError("render failed")

    monkeypatch.setitem(tasks.HANDLERS, "GENERATE_VIDEO", _failing)
    result = tasks.run_job(db, job)

    assert result.status == "FAILED"
    assert result.error == "render failed"
    assert db.get(Case, case.id).status == "DRAFT"


def test_run_job_unknown_job_type_fails(db, dev_user):
    case = make_case(db, dev_user)
    job = _committed_job(db, case, job_type="NOT_A_JOB")

    result = tasks.run_job(db, job)

    assert result.status == "FAILED"
    assert "unknown job type" in result.error
    assert db.get(Case, case.id).status == "DRAFT"


def test_run_job_success_contract_preserved(db, dev_user, monkeypatch):
    case = make_case(db, dev_user)
    job = _committed_job(db, case)

    monkeypatch.setitem(tasks.HANDLERS, "ANALYZE_CASE", lambda uow, _job: {"ok": True})
    result = tasks.run_job(db, job)

    assert result.status == "SUCCEEDED"
    assert result.progress == 100
    assert result.error == ""
    assert result.result == {"ok": True}
    assert result.attempts == 1
    assert db.get(Case, case.id).status == "DRAFT"


def test_run_job_failure_persists_after_commit(db, dev_user, monkeypatch):
    """The worker commits after run_job; the failure bookkeeping must survive."""
    case = make_case(db, dev_user)
    job = _committed_job(db, case)

    def _failing(uow, _job):
        raise RuntimeError("boom")

    monkeypatch.setitem(tasks.HANDLERS, "ANALYZE_CASE", _failing)
    tasks.run_job(db, job)
    db.commit()

    reloaded = db.get(Job, job.id)
    assert reloaded.status == "FAILED"
    assert reloaded.error == "boom"
    assert db.get(Case, case.id).status == "ERROR"
