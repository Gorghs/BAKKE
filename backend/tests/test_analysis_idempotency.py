from __future__ import annotations

from app.models import (
    Entity,
    EvidenceItem,
    Fact,
    Hypothesis,
    Scenario,
    SimilarCase,
    TimelineEvent,
)
from app.services.analysis_service import AnalysisService
from tests.conftest import make_case


def _counts(db, case_id: str) -> dict[str, int]:
    return {
        "facts": db.query(Fact).filter_by(case_id=case_id).count(),
        "timeline": db.query(TimelineEvent).filter_by(case_id=case_id).count(),
        "entities": db.query(Entity).filter_by(case_id=case_id).count(),
        "hypotheses": db.query(Hypothesis).filter_by(case_id=case_id).count(),
        "scenarios": db.query(Scenario).filter_by(case_id=case_id).count(),
        "similar": db.query(SimilarCase).filter_by(case_id=case_id).count(),
    }


class TestAnalysisRerunReplacesDerivedState:
    """A second analysis run must rebuild derived state, not append to it.

    Supervisor retries re-run the whole pipeline; live, three attempts
    triple-fused the same evidence (13 -> 38 facts), which pushed one request
    past the free-tier TPM and made every further attempt fail harder.
    """

    def _case_with_evidence(self, db, dev_user):
        case = make_case(db, dev_user)
        db.add(
            EvidenceItem(
                case_id=case.id,
                evidence_id="E-001",
                item_type="TEXT",
                title="Entry log",
                status="UPLOADED",
                raw_text="The door was unlocked at 21:12 and locked at 21:31 on 14 March.",
            )
        )
        db.add(
            EvidenceItem(
                case_id=case.id,
                evidence_id="E-002",
                item_type="WITNESS_STATEMENT",
                title="Witness",
                status="UPLOADED",
                raw_text="A neighbour heard a door slam at approximately 21:40 on 14 March.",
            )
        )
        case.evidence_count = 2
        db.commit()
        return case

    def test_second_run_does_not_duplicate_derived_state(self, db, dev_user):
        case = self._case_with_evidence(db, dev_user)

        AnalysisService().analyze_case(db, case.id)
        db.commit()
        first = _counts(db, case.id)
        assert first["facts"] > 0

        AnalysisService().analyze_case(db, case.id)
        db.commit()
        second = _counts(db, case.id)
        assert second == first, f"re-analysis appended instead of replacing: {first} -> {second}"

    def test_second_run_still_produces_a_full_result(self, db, dev_user):
        case = self._case_with_evidence(db, dev_user)

        AnalysisService().analyze_case(db, case.id)
        db.commit()
        result = AnalysisService().analyze_case(db, case.id)
        db.commit()

        assert result["status"] == "ANALYZED"
        assert result["evidence_extracted"] == 2
        assert result["hypotheses_generated"] > 0
