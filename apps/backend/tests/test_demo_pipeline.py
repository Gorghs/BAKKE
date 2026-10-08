from __future__ import annotations

from app.models import (
    Case,
    Conflict,
    EvidenceItem,
    Fact,
    ForensicAnchor,
    Hypothesis,
    ReferenceCase,
    Scenario,
    SimilarCase,
)
from app.features.analysis.analysis_service import AnalysisService
from tests.conftest import make_case

POST_MORTEM = """POST-MORTEM REPORT - CASE PM-2026-018
Injury location: right hip. Confirmed single penetrating wound.
The injury is located at the right hip region.
Estimated time of death: 20:00-21:00.
Exact mechanism of injury cannot be determined from the wound alone.
"""

FORENSIC = """FORENSIC REPORT - CASE FR-2026-018
The hallway is covered by CCTV camera. Camera coverage of the hallway is confirmed.
The critical room has no camera coverage. The room is not covered by any CCTV.
A knife was recovered at the scene. The knife was present at the location.
"""

INVESTIGATOR = """INVESTIGATOR REPORT - CASE IR-2026-018
Person A entered the location at approximately 20:05 carrying a knife.
Person A exited the location at approximately 20:18.
The hallway is covered by camera. The critical room is not covered by camera.
The victim was later found deceased in the critical room.
"""

WITNESS = """WITNESS STATEMENT - W-014
Witness B states that Person A left the building at 20:10.
The witness observed Person A departing at 20:10.
This statement conflicts with CCTV footage showing Person A visible at 20:14.
"""

AUDIO = """AUDIO TRANSCRIPT - CALL 9-1-1
Caller: There's been an incident. Someone is injured. There is a knife here.
Dispatcher: Where is the injured person?
Caller: In the back room. I don't know what happened. Please hurry.
"""

HALLWAY_IMAGE = """IMAGE DESCRIPTION - CCTV HALLWAY STILL
A hallway is visible. Person A is visible in the hallway at 20:14.
No other people are visible in the frame.
"""

CCTV_CLIP = """VIDEO DESCRIPTION - CCTV HALLWAY CLIP
Person A is visible in the hallway at 20:14 walking toward the exit.
The hallway is covered by camera; the critical room is not visible.
"""

EVIDENCE = [
    ("POST_MORTEM_REPORT", "Post-mortem", POST_MORTEM),
    ("FORENSIC_REPORT", "Forensic", FORENSIC),
    ("INVESTIGATOR_REPORT", "Investigator", INVESTIGATOR),
    ("WITNESS_STATEMENT", "Witness", WITNESS),
    ("AUDIO", "911 call", AUDIO),
    ("IMAGE", "Hallway still", HALLWAY_IMAGE),
    ("VIDEO", "Hallway clip", CCTV_CLIP),
]


def add_reference(db, ref_id: str) -> None:
    db.add(
        ReferenceCase(
            reference_id=ref_id,
            title=f"Reference {ref_id}",
            description="Documented solved case used as analogical reference only.",
            summary="Blind room, knife present, right hip injury, entry/exit observed.",
            injury_pattern=["right hip", "single wound"],
            weapon_pattern=["knife"],
            timeline_pattern=["entry observed", "exit observed", "uncertain event window"],
            spatial_pattern=["hallway covered", "room not covered"],
            witness_conflict_pattern=["witness claimed earlier departure"],
            evidence_gap_pattern=["blind camera area"],
            event_sequence=["person enters", "unknown events in room", "person exits"],
            conclusion="Sequence inside the room could not be determined from available evidence.",
        )
    )


class TestDemoPipelineEndToEnd:
    def test_full_analysis_pipeline(self, db, dev_user):
        case = make_case(db, dev_user)
        for i, (itype, title, text) in enumerate(EVIDENCE, start=1):
            db.add(
                EvidenceItem(
                    case_id=case.id,
                    evidence_id=f"E-{i:03d}",
                    item_type=itype,
                    title=title,
                    description=title,
                    status="UPLOADED",
                    raw_text=text,
                    extra={"evidence_type": itype},
                )
            )
        for rid in ("SC-001", "SC-002", "SC-003"):
            add_reference(db, rid)
        case.evidence_count = len(EVIDENCE)
        db.commit()

        result = AnalysisService().analyze_case(db, case.id)
        db.commit()

        assert result["status"] == "ANALYZED"
        assert result["evidence_extracted"] == 7
        assert result["hypotheses_generated"] > 0
        assert result["surviving_scenarios"] >= 2
        assert result["rejected_scenarios"] >= 1
        assert result["similar_cases_retrieved"] >= 1

        # A chest-injury candidate must exist and be rejected on forensic grounds.
        rejected = (
            db.query(Scenario)
            .join(Hypothesis, Scenario.hypothesis_id == Hypothesis.id)
            .filter(Scenario.case_id == case.id, Scenario.status == "REJECTED")
            .all()
        )
        chest = [s for s in rejected if "chest" in (s.rejection_reason or "").lower() or (s.extra or {}).get("injury_location") == "chest"]
        assert chest, "the impossible chest-injury scenario must be generated and rejected"

        # The forensic anchor is authoritative and satisfied by survivors.
        anchors = db.query(ForensicAnchor).filter_by(case_id=case.id).all()
        assert any(a.type == "INJURY_LOCATION" and (a.value or {}).get("location") == "right hip" for a in anchors)
        survivors = db.query(Scenario).filter(Scenario.case_id == case.id, Scenario.is_survivor == True).all()  # noqa: E712
        assert len(survivors) >= 2
        for s in survivors:
            if (s.extra or {}).get("injury_location"):
                assert s.extra["injury_location"] == "right hip"

        # Evidence is never treated as fact-inflating: facts extracted are bounded.
        facts = db.query(Fact).filter_by(case_id=case.id).all()
        assert 0 < len(facts) < 200

        # Witness conflict surfaced by the pipeline.
        conflicts = db.query(Conflict).filter_by(case_id=case.id).all()
        assert len(conflicts) >= 1

    def test_no_evidence_no_fabrication(self, db, dev_user):
        """An empty case yields no hypotheses and no hallucinated scenarios."""
        case = make_case(db, dev_user)
        db.commit()
        result = AnalysisService().analyze_case(db, case.id)
        db.commit()
        assert result["status"] == "ANALYZED"
        assert result["evidence_extracted"] == 0
        survivors = db.query(Scenario).filter(Scenario.case_id == case.id, Scenario.is_survivor == True).all()  # noqa: E712
        assert survivors == []
        assert db.query(Hypothesis).filter_by(case_id=case.id).count() == 0
