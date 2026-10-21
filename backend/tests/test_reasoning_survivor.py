from __future__ import annotations

from app.agents.contracts import CritiqueIssue, CritiqueResult
from app.agents.reasoning import HypothesisCriticAgent
from app.models import Fact, Scenario
from app.reasoning.engine import ReasoningEngine
from tests.conftest import make_case


def _critique_pass_with_fixable(self, scenario, anchors, facts, timeline):
    """The live Groq critic: passes the candidate, still lists a nit."""
    return CritiqueResult(
        verdict="PASS",
        summary="no hard conflict remains; one link could be strengthened",
        issues=[
            CritiqueIssue(
                type="MISSING_LINK",
                description="one event could cite its supporting fact more precisely",
                severity="SOFT",
                fixable=True,
            )
        ],
    )


def test_pass_verdict_with_fixable_issue_leaves_a_survivor(db, dev_user, monkeypatch):
    """A critic PASS must survive even when it lists a fixable issue.

    Live run `fad84815` went red here: the critic passed a candidate, the
    engine revised it anyway, each revision burned one iteration, and the run
    ended on the cap with 0 surviving scenarios and a PENDING tail.
    """
    case = make_case(db, dev_user)
    db.add(
        Fact(
            case_id=case.id,
            fact_id="F-001",
            statement="The store door was found open at 07:50 on 6 March.",
            status="SOFT",
            source_type="WITNESS_STATEMENT",
            source_evidence_ids=["E-001"],
        )
    )
    db.commit()

    monkeypatch.setattr(HypothesisCriticAgent, "critique", _critique_pass_with_fixable)

    result = ReasoningEngine().run(db, case.id)

    survivors = (
        db.query(Scenario)
        .filter(Scenario.case_id == case.id, Scenario.is_survivor == True)  # noqa: E712
        .all()
    )
    assert survivors, "a critic PASS with only fixable issues must leave a surviving scenario"
    assert result.surviving >= 1
    assert result.stopped_reason != "max iterations safety limit reached"
    pending = db.query(Scenario).filter(Scenario.case_id == case.id, Scenario.status == "PENDING").count()
    assert pending == 0, "no candidate may be left unjudged when the critic keeps passing"
