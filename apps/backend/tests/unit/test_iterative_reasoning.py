from __future__ import annotations

from app.domain.constraints.engine import ConstraintEngine
from app.models import Fact, ForensicAnchor
from tests.conftest import make_case


def spatial_fact(case_id: str, fact_id: str, person: str, location: str, time: str, status: str = "HARD", source: str = "VIDEO") -> Fact:
    return Fact(
        case_id=case_id,
        fact_id=fact_id,
        statement=f"{person} was at {location} at {time}.",
        status=status,
        source_type=source,
        source_evidence_ids=[f"E-{fact_id}"],
        extra={"spatial": {"person": person, "location": location, "time": time}},
    )


class TestTemporalSpatialConflicts:
    def test_conflicting_location_same_time_is_hard(self):
        engine = ConstraintEngine()
        facts = [spatial_fact("case-x", "F-001", "Person A", "Hallway", "20:10")]
        sc = {
            "participants": ["Person A"],
            "events": [
                {
                    "description": "Person A was in the Room at 20:10.",
                    "event_type": "KNOWN",
                    "linked_fact_ids": [],
                    "evidence_links": [],
                    "timing": {"start": "20:10"},
                    "location": "Room",
                }
            ],
        }
        violations = engine.check(sc, [], facts, [])
        temporal = [v for v in violations if v.type == "TEMPORAL"]
        assert temporal and temporal[0].severity == "HARD"
        assert "Hallway" in temporal[0].description and "Room" in temporal[0].description

    def test_consistent_location_same_time_passes(self):
        engine = ConstraintEngine()
        facts = [spatial_fact("case-x", "F-001", "Person A", "Hallway", "20:10")]
        sc = {
            "participants": ["Person A"],
            "events": [
                {
                    "description": "Person A was in the Hallway at 20:10.",
                    "event_type": "KNOWN",
                    "linked_fact_ids": ["F-001"],
                    "evidence_links": [],
                    "timing": {"start": "20:10"},
                    "location": "Hallway",
                }
            ],
        }
        violations = engine.check(sc, [], facts, [])
        assert [v for v in violations if v.type == "TEMPORAL"] == []

    def test_distant_times_do_not_conflict(self):
        engine = ConstraintEngine()
        facts = [spatial_fact("case-x", "F-001", "Person A", "Hallway", "20:10")]
        sc = {
            "participants": ["Person A"],
            "events": [
                {
                    "description": "Person A was in the Room at 21:30.",
                    "event_type": "KNOWN",
                    "linked_fact_ids": [],
                    "evidence_links": [],
                    "timing": {"start": "21:30"},
                    "location": "Room",
                }
            ],
        }
        violations = engine.check(sc, [], facts, [])
        assert [v for v in violations if v.type == "TEMPORAL"] == []

    def test_witness_statement_conflict_surfaces(self, db, dev_user):
        """A witness claim contradicted by verified footage must be flagged."""
        case = make_case(db, dev_user)
        db.add(ForensicAnchor(case_id=case.id, anchor_id="FA-001", type="INJURY_LOCATION", value={"location": "right hip"}, normalized="right hip", source_evidence_ids=["E-001"]))
        db.add(spatial_fact(case.id, "F-001", "Person A", "Hallway", "20:14"))
        db.commit()
        engine = ConstraintEngine()
        sc = {
            "participants": ["Person A"],
            "events": [
                {
                    "description": "Person A left the building at 20:10.",
                    "event_type": "INFERRED",
                    "linked_fact_ids": ["F-002"],
                    "evidence_links": ["E-004"],
                    "timing": {"start": "20:10"},
                    "location": "Building",
                }
            ],
        }
        facts = db.query(Fact).filter_by(case_id=case.id).all()
        violations = engine.check(sc, [], facts, [])
        assert [v for v in violations if v.type == "TEMPORAL"]
