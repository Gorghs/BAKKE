from __future__ import annotations

from app.domain.constraints.engine import ConstraintEngine
from app.models import ForensicAnchor


def make_anchor(location: str) -> list[ForensicAnchor]:
    return [
        ForensicAnchor(
            anchor_id="FA-001",
            type="INJURY_LOCATION",
            value={"location": location},
            normalized=location,
            source_evidence_ids=["E-001"],
            strength="HARD",
        )
    ]


def scenario(injury: str, with_event: bool = True) -> dict:
    return {
        "injury_location": injury,
        "participants": ["Person A"],
        "events": [
            {
                "description": f"Injury to {injury} occurred.",
                "event_type": "INFERRED",
                "linked_fact_ids": [],
                "evidence_links": ["E-001"],
                "timing": {},
                "location": "",
            }
        ]
        if with_event
        else [],
    }


class TestForensicInjuryAnchor:
    def test_hip_matches_anchor(self):
        engine = ConstraintEngine()
        violations = engine.check(scenario("right hip"), make_anchor("right hip"), [], [])
        assert violations == []

    def test_chest_conflicts_with_hip_anchor(self):
        engine = ConstraintEngine()
        violations = engine.check(scenario("chest"), make_anchor("right hip"), [], [])
        assert len(violations) == 1
        v = violations[0]
        assert v.type == "FORENSIC"
        assert v.severity == "HARD"
        assert "right hip" in v.description and "chest" in v.description
        assert v.constraint_ref == "FA-001"

    def test_empty_injury_never_conflicts(self):
        engine = ConstraintEngine()
        violations = engine.check(scenario(""), make_anchor("right hip"), [], [])
        assert violations == []

    def test_hip_without_anchor_is_allowed(self):
        engine = ConstraintEngine()
        violations = engine.check(scenario("right hip"), [], [], [])
        assert violations == []
