"""A run where no evidence could be extracted must not report success.

Regression guard for the silent-empty-success failure mode: when the LLM
provider is unconfigured, out of quota, or otherwise broken, every extraction
fails. The service used to swallow those failures, finish the (empty) pipeline,
stamp the case ANALYZED and mark the job SUCCEEDED. An operator saw a finished
analysis with no facts and no error.
"""

from __future__ import annotations

import pytest

from app.features.evidence.extract import get_extractor_agent as real_get_extractor_agent
from app.infrastructure.jobs.tasks import run_job
from app.models import AuditEvent, EvidenceItem, Job
from app.adapters.persistence import SqlAlchemyUnitOfWork
from app.workflows import AnalyzeCaseWorkflow
from tests.conftest import make_case

FAILURE_TEXT = "provider 'openai-llm' failed on task 'extract_evidence': no models available"


class BrokenExtractor:
    """Stands in for an extractor agent whose provider is unreachable."""

    name = "BrokenExtractorAgent"
    provider_label = "mock"

    def extract(self, evidence=None, text=""):
        raise RuntimeError(FAILURE_TEXT)


def add_evidence(db, case, evidence_id: str, item_type: str = "WITNESS_STATEMENT") -> EvidenceItem:
    item = EvidenceItem(
        case_id=case.id,
        evidence_id=evidence_id,
        item_type=item_type,
        title=f"Statement {evidence_id}",
        raw_text="The tool store door was standing open at 07:50.",
    )
    db.add(item)
    db.commit()
    return item


def test_all_extraction_failures_raise(monkeypatch, db, dev_user):
    case = make_case(db, dev_user, "Total extraction failure")
    add_evidence(db, case, "E-001")
    add_evidence(db, case, "E-002", item_type="PHYSICAL_EVIDENCE")

    monkeypatch.setattr("app.workflows.extract_evidence.get_extractor_agent", lambda item_type: BrokenExtractor())

    with pytest.raises(RuntimeError) as excinfo:
        AnalyzeCaseWorkflow(SqlAlchemyUnitOfWork(db)).run(case.id)

    message = str(excinfo.value)
    assert "extract" in message.lower()
    assert "E-001" in message, "the error should name the items that failed"
    assert "E-002" in message

    db.refresh(case)
    assert case.status != "ANALYZED"


def test_partial_extraction_failure_still_analyzes(monkeypatch, db, dev_user):
    case = make_case(db, dev_user, "Partial extraction failure")
    add_evidence(db, case, "E-001")
    broken = add_evidence(db, case, "E-002", item_type="PHYSICAL_EVIDENCE")

    def chooser(item_type: str):
        if item_type == "PHYSICAL_EVIDENCE":
            return BrokenExtractor()
        return real_get_extractor_agent(item_type)

    monkeypatch.setattr("app.workflows.extract_evidence.get_extractor_agent", chooser)

    result = AnalyzeCaseWorkflow(SqlAlchemyUnitOfWork(db)).run(case.id)

    assert result["status"] == "ANALYZED"
    db.refresh(broken)
    assert broken.status == "FAILED"
    assert FAILURE_TEXT[:80] in broken.extra["extraction_error"]
    actions = [event.action for event in db.query(AuditEvent).filter_by(case_id=case.id).all()]
    assert "extraction_failed" in actions


def test_failed_analysis_job_marks_case_error(monkeypatch, db, dev_user):
    case = make_case(db, dev_user, "Job level failure")
    add_evidence(db, case, "E-001")

    monkeypatch.setattr("app.workflows.extract_evidence.get_extractor_agent", lambda item_type: BrokenExtractor())

    job = Job(case_id=case.id, job_type="ANALYZE_CASE", status="PENDING", payload={})
    db.add(job)
    db.commit()

    run_job(db, job)

    assert job.status == "FAILED"
    assert "extract" in job.error.lower()
    db.refresh(case)
    assert case.status == "ERROR"


def test_failed_retry_keeps_the_previous_analysis(monkeypatch, db, dev_user):
    """A requeued run clears the old derived rows only once extraction produced
    something to put in their place.

    The clear used to run first, so a retry that died on the provider deleted the
    previous analysis and wrote nothing back. Observed live: attempt 3 of a
    requeued job wiped 13 timeline events and 15 scenarios, then hit a 429 on
    every extraction, leaving the case emptier than it found it.
    """
    from app.models import Fact

    case = make_case(db, dev_user, "Failed retry keeps prior analysis")
    add_evidence(db, case, "E-001")
    db.add(Fact(case_id=case.id, fact_id="F-001", statement="The store door was open at 07:50."))
    db.commit()

    monkeypatch.setattr("app.workflows.extract_evidence.get_extractor_agent", lambda item_type: BrokenExtractor())

    with pytest.raises(RuntimeError):
        AnalyzeCaseWorkflow(SqlAlchemyUnitOfWork(db)).run(case.id)

    db.expire_all()
    kept = [fact.fact_id for fact in db.query(Fact).filter_by(case_id=case.id).all()]
    assert kept == ["F-001"], "a failed retry must not delete the last good analysis"
