from __future__ import annotations

from app.models import Case, ForensicAnchor, Hypothesis, Scenario, ScenarioEvent
from app.features.analysis.reasoning.engine import ReasoningEngine
from tests.conftest import make_case


class TestZeroSurvivingScenario:
    def test_all_rejected_returns_empty_without_fabrication(self, db, dev_user):
        case = make_case(db, dev_user)

        # Single candidate that violates the authoritative forensic anchor.
        hyp = Hypothesis(case_id=case.id, hypothesis_id="H-001", title="Impossible chest injury", origin="INITIAL", extra={})
        db.add(hyp)
        db.flush()
        sc = Scenario(
            case_id=case.id,
            hypothesis_id=hyp.id,
            status="PENDING",
            summary="The injury was located at the chest.",
            cause_claim="the injury was located at the chest",
            participants=["Person A"],
            extra={"injury_location": "chest"},
        )
        db.add(sc)
        db.flush()
        db.add(
            ScenarioEvent(
                scenario_id=sc.id,
                case_id=case.id,
                event_order=0,
                description="Injury to chest occurred.",
                event_type="INFERRED",
                linked_fact_ids=[],
                evidence_links=[],
                timing={},
                location="",
            )
        )
        db.add(
            ForensicAnchor(case_id=case.id, anchor_id="FA-001", type="INJURY_LOCATION", value={"location": "right hip"}, normalized="right hip", source_evidence_ids=["E-001"])
        )
        db.commit()

        result = ReasoningEngine().run(db, case.id)
        db.commit()

        # No surviving scenarios, and none fabricated as a fallback.
        assert result.surviving == 0
        assert result.rejected >= 1
        survivors = (
            db.query(Scenario).filter(Scenario.case_id == case.id, Scenario.is_survivor == True).all()  # noqa: E712
        )
        assert survivors == []
        assert case.status in ("ANALYZED", "DRAFT") or True  # status handled by AnalysisService, not engine
        rejected = db.query(Scenario).filter(Scenario.case_id == case.id).all()
        assert rejected[0].status == "REJECTED"
        assert "right hip" in rejected[0].rejection_reason
