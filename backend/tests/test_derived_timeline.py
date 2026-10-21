from __future__ import annotations

from app.agents.contracts import FactDraft, ExtractionResult
from app.agents.fusion import EvidenceFusionAgent, _derived_timeline
from app.models import EvidenceItem, Fact, TimelineEvent
from tests.conftest import make_case


def _fact(case_id: str, fact_id: str, statement: str, evidence_id: str = "E-001") -> Fact:
    return Fact(
        case_id=case_id,
        fact_id=fact_id,
        statement=statement,
        status="SOFT",
        source_type="WITNESS_STATEMENT",
        source_evidence_ids=[evidence_id],
    )


class TestDerivedTimeline:
    """The extraction contract writes timeline_events last, so a provider that
    runs out of output budget loses exactly that section. Live run fad84815
    extracted 26 facts and 0 timeline events, which emptied both the timeline
    tab and the reasoning payload. Fusion orders the facts that state a clock
    time instead of leaving the timeline empty."""

    def test_facts_with_times_become_ordered_timeline_entries(self):
        facts = [
            _fact("case-x", "F-001", "The store door was found standing open at 07:50 on 6 March."),
            _fact("case-x", "F-002", "Ravi Menon locked the tool store at 18:05 on 5 March."),
            _fact("case-x", "F-003", "The padlock was hanging open on the hasp."),
        ]
        derived = _derived_timeline(facts)

        assert [d["time_start"] for d in derived] == ["18:05", "07:50"], "entries must be in clock order"
        assert all(d["linked_fact_ids"] for d in derived), "each entry must cite the fact it came from"
        assert all(d["source_evidence_ids"] for d in derived), "each entry must keep its evidence link"
        assert len(derived) == 2, "a fact without a clock time must not be dated"

    def test_approximate_wording_lowers_certainty(self):
        derived = _derived_timeline([_fact("case-x", "F-001", "The round happened at approximately 01:50.")])
        assert derived[0]["time_type"] == "APPROXIMATE"
        assert derived[0]["certainty"] == "BOUNDED"

    def test_fusion_falls_back_when_extraction_returns_no_timeline(self, db, dev_user):
        """The end-to-end seam: the model returns facts only, the run still gets a timeline."""
        case = make_case(db, dev_user)
        ev = EvidenceItem(
            case_id=case.id,
            evidence_id="E-001",
            item_type="WITNESS_STATEMENT",
            title="Depot supervisor statement, 6 March",
            raw_text="locked the store at 18:05 and found the door open at 07:50",
        )
        db.add(ev)
        db.commit()

        extraction = ExtractionResult(
            facts=[
                FactDraft(statement="Ravi Menon locked the tool store at 18:05 on 5 March."),
                FactDraft(statement="The store door was found standing open at 07:50 on 6 March."),
            ],
            findings=[],
            entities=[],
            timeline_events=[],
        )

        EvidenceFusionAgent().run(db, case.id, [(ev, extraction)])
        db.commit()

        rows = db.query(TimelineEvent).filter_by(case_id=case.id).order_by(TimelineEvent.ordering_index).all()
        assert len(rows) == 2, "a fact-only extraction must still produce a timeline"
        assert [r.time_start for r in rows] == ["18:05", "07:50"]
        assert all(r.certainty == "KNOWN" for r in rows)

    def test_model_timeline_is_not_overwritten_by_the_fallback(self, db, dev_user):
        """The fallback is a gap-filler, not a replacement."""
        case = make_case(db, dev_user)
        ev = EvidenceItem(
            case_id=case.id,
            evidence_id="E-001",
            item_type="WITNESS_STATEMENT",
            title="Depot supervisor statement, 6 March",
            raw_text="locked the store at 18:05",
        )
        db.add(ev)
        db.commit()

        extraction = ExtractionResult.model_validate(
            {
                "facts": [{"statement": "Ravi Menon locked the tool store at 18:05 on 5 March."}],
                "timeline_events": [{"title": "Locking of the store", "time_start": "18:05", "time_type": "EXACT"}],
            }
        )

        EvidenceFusionAgent().run(db, case.id, [(ev, extraction)])
        db.commit()

        rows = db.query(TimelineEvent).filter_by(case_id=case.id).all()
        assert len(rows) == 1, "the model's own timeline must win when it sends one"
        assert rows[0].title == "Locking of the store"
