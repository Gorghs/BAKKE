from __future__ import annotations

from app.features.analysis.retrieval.similar_cases import retrieve_similar_cases
from app.models import Fact, ForensicAnchor
from tests.conftest import make_case


def seed_anchor_and_fact(db, case_id: str) -> None:
    db.add(ForensicAnchor(case_id=case_id, anchor_id="FA-001", type="INJURY_LOCATION", value={"location": "right hip"}, normalized="right hip", source_evidence_ids=["E-001"]))
    db.add(
        Fact(
            case_id=case_id,
            fact_id="F-001",
            statement="Person A was present in the hallway at 20:14.",
            status="HARD",
            source_type="VIDEO",
            source_evidence_ids=["E-002"],
            extra={"spatial": {"person": "Person A", "location": "Hallway", "time": "20:14"}},
        )
    )
    db.commit()


class TestSimilarCaseReferenceOnly:
    def test_retrieved_cases_are_reference_only(self, db, dev_user):
        case = make_case(db, dev_user)
        db.add(
            Fact(
                case_id=case.id,
                fact_id="F-001",
                statement="The injury is located at the right hip.",
                status="HARD",
                source_type="FORENSIC_REPORT",
                source_evidence_ids=["E-001"],
                extra={"injury_location": "right hip"},
            )
        )
        db.commit()
        similar = retrieve_similar_cases(db, case.id)
        # Retrieval may return 0 without a populated reference library, but must
        # never invent similarities or mutate facts.
        assert isinstance(similar, list)
        for s in similar:
            assert s.reference_label
            assert s.similarity > 0
        # Reference-case conclusions are not injected as facts.
        facts = db.query(Fact).filter_by(case_id=case.id).all()
        assert all(f.source_type != "REFERENCE_CASE" for f in facts)

    def test_similar_inspired_scenario_is_hypothesized_not_known(self, db, dev_user):
        """Scenarios inspired by reference cases may only be hypothesized."""
        from app.infrastructure.providers.rule_based import mock_generate_hypotheses

        payload = {
            "facts": [
                {"statement": "Person A entered the location at 20:05.", "metadata": {"person": "Person A"}},
                {"statement": "The injury is located at the right hip.", "metadata": {"injury_location": "right hip"}},
            ],
            "timeline": [],
            "anchors": [{"type": "INJURY_LOCATION", "value": {"location": "right hip"}}],
            "similar_cases": [
                {
                    "reference_label": "REF-001",
                    "title": "Reference: knife injury in blind corridor",
                    "relevant_patterns": ["unobserved window", "knife present"],
                }
            ],
        }
        result = mock_generate_hypotheses(payload)
        inspired = [h for h in result["hypotheses"] if h.get("origin") == "SIMILAR_CASE_INSPIRED"]
        assert inspired, "expected a similar-case-inspired hypothesis"
        h = inspired[0]
        assert h["similar_case_patterns_used"], "patterns should be recorded as analogical reference"
        # Reference patterns must never be transferred as KNOWN events or facts.
        assert all(e["event_type"] == "HYPOTHESIZED" for e in h["events"] if "analogous" in e["description"])
        assert all(e["linked_fact_ids"] == [] for e in h["events"])
