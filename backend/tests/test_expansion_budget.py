"""Expansion has to stay bounded, and has to know why the candidate failed.

Live run on the five-item "Missing tools" case: three initial candidates produced
52 scenario rows, 26 of them never validated because the iteration cap stopped
the loop first, and the rest mostly reworded the same "the key was misplaced"
idea. The dashboard then read 52 rejections while half the pool carried no
verdict at all, and no candidate ever addressed the window the critic kept
pointing at (the door was seen shut at 00:00 and 04:00, so the access had to
fall between 04:00 and 07:50).
"""

from __future__ import annotations

from app.agents.contracts import ExpansionResult, HypothesisDraft
from app.agents.reasoning import InvestigativeReasoningAgent
from app.models import ForensicAnchor, Hypothesis, Scenario, ScenarioEvent
from app.reasoning import engine as engine_module
from app.reasoning.engine import MAX_EXPANSIONS_PER_ROUND, ReasoningEngine
from tests.conftest import make_case


def _draft(title: str) -> HypothesisDraft:
    return HypothesisDraft(title=title, summary="summary", cause_claim="cause")


def _seed_rejected_candidate(db, case) -> None:
    """One PENDING candidate that an authoritative anchor rules out."""
    hyp = Hypothesis(case_id=case.id, hypothesis_id="H-001", title="Impossible chest injury", extra={})
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
        ForensicAnchor(
            case_id=case.id,
            anchor_id="FA-001",
            type="INJURY_LOCATION",
            value={"location": "right hip"},
            normalized="right hip",
            source_evidence_ids=["E-001"],
        )
    )
    db.commit()


class TestExpansionBudget:
    def test_rewordings_are_dropped_and_the_round_is_capped(self, db, dev_user):
        case = make_case(db, dev_user, "Expansion budget")
        db.add(Hypothesis(case_id=case.id, hypothesis_id="H-001", title="Key misplaced by night guard"))
        db.flush()

        candidates = [("EXPANSION", _draft("Night guard misplaced the key"))]
        candidates += [("EXPANSION", _draft(f"Distinct theory {i}")) for i in range(10)]

        fresh = ReasoningEngine()._novel_candidates(db, case.id, candidates)

        assert len(fresh) == MAX_EXPANSIONS_PER_ROUND
        titles = [hd.title for _, hd in fresh]
        assert "Night guard misplaced the key" not in titles, "a reworded duplicate is not a new candidate"

    def test_expand_payload_carries_the_rejection_reason(self, db, dev_user):
        case = make_case(db, dev_user, "Expansion reason")
        agent = InvestigativeReasoningAgent()
        seen: dict = {}

        def fake_run_task(task, payload):
            seen["task"] = task
            seen["payload"] = payload
            return {"hypotheses": []}

        agent.run_task = fake_run_task  # type: ignore[method-assign]

        agent.expand(db, case.id, {"id": "sc-1"}, "the door was shut at 00:00 and 04:00")

        assert seen["task"] == "expand_alternatives"
        assert seen["payload"]["rejection_reason"] == "the door was shut at 00:00 and 04:00"


class TestLeftoverValidation:
    def test_no_candidate_is_left_without_a_verdict(self, monkeypatch, db, dev_user):
        case = make_case(db, dev_user, "Leftover validation")
        _seed_rejected_candidate(db, case)

        engine = ReasoningEngine()
        expanded = ExpansionResult(
            hypotheses=[_draft("Expanded theory created in the last round")],
        )
        engine.generator.expand = lambda *args, **kwargs: expanded  # type: ignore[method-assign]
        # One iteration is enough to leave the expansion unvalidated: the cap
        # stops the loop before the new candidate is reached.
        monkeypatch.setattr(engine_module.settings, "MAX_REASONING_ITERATIONS", 1)

        engine.run(db, case.id)

        rows = db.query(Scenario).filter_by(case_id=case.id).all()
        origins = {row.hypothesis_id for row in rows}
        assert len(origins) > 1, "the expansion should have been persisted"
        assert [row.status for row in rows if row.status == "PENDING"] == []
        assert all(row.status in ("SURVIVING", "REJECTED") for row in rows)
