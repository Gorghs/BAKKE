from __future__ import annotations

from app.infrastructure.providers.rule_based import mock_generate_hypotheses

# Feature statements are spread across indices so that a small fact set produces
# fewer candidate hypotheses than a large one (entry/exit/knife/location only
# appear once enough evidence has been supplied).
FEATURES = {
    0: "A knife was found at the scene.",
    1: "The injury is located at the right hip.",
    2: "Person A entered the location at 20:05.",
    3: "Person A exited the location at 20:18.",
    4: "The covered hallway has no camera coverage.",
    5: "Person A is visible in the hallway at 20:14.",
    6: "Witness B reported hearing a disturbance at 20:12.",
}


def make_facts(n: int) -> list[dict]:
    facts = []
    for i in range(n):
        meta: dict = {"person": "Person A"}
        statement = FEATURES.get(i, f"Additional evidence record {i}.")
        if i == 1:
            meta["injury_location"] = "right hip"
        if i == 4:
            meta["camera_coverage"] = "NO_COVERAGE"
        if i == 5:
            meta["spatial"] = {"person": "Person A", "location": "Hallway", "time": "20:14"}
        facts.append(
            {
                "fact_id": f"F-{i + 1:03d}",
                "statement": statement,
                "status": "HARD",
                "source_evidence_ids": [f"E-{i + 1:03d}"],
                "metadata": meta,
            }
        )
    return facts


class TestDynamicHypothesisGeneration:
    def test_evidence_volume_drives_hypothesis_count(self):
        anchors = [{"type": "INJURY_LOCATION", "value": {"location": "right hip"}}]

        low = mock_generate_hypotheses({"facts": make_facts(2), "timeline": [], "anchors": anchors, "similar_cases": []})["hypotheses"]
        mid = mock_generate_hypotheses({"facts": make_facts(7), "timeline": [], "anchors": anchors, "similar_cases": []})["hypotheses"]
        high = mock_generate_hypotheses({"facts": make_facts(17), "timeline": [], "anchors": anchors, "similar_cases": []})["hypotheses"]

        assert len(low) > 0
        assert len(mid) > len(low), "more evidence must surface additional candidate hypotheses"
        assert len(high) >= len(mid)
        assert len(high) > len(low)

    def test_reference_cases_add_alternative_hypothesis(self):
        anchors = [{"type": "INJURY_LOCATION", "value": {"location": "right hip"}}]
        without = mock_generate_hypotheses({"facts": make_facts(7), "timeline": [], "anchors": anchors, "similar_cases": []})["hypotheses"]
        with_refs = mock_generate_hypotheses(
            {
                "facts": make_facts(7),
                "timeline": [],
                "anchors": anchors,
                "similar_cases": [{"reference_label": "REF-001", "title": "x", "relevant_patterns": ["knife present"]}],
            }
        )["hypotheses"]
        assert len(with_refs) > len(without)

    def test_impossible_injury_scenario_is_generated_for_rejection(self):
        anchors = [{"type": "INJURY_LOCATION", "value": {"location": "right hip"}}]
        hyps = mock_generate_hypotheses({"facts": make_facts(7), "timeline": [], "anchors": anchors, "similar_cases": []})["hypotheses"]
        impossible = [h for h in hyps if h.get("injury_location") and h["injury_location"] != "right hip"]
        assert impossible, "expected an impossible alternate-injury candidate for the constraint engine to reject"
        assert impossible[0]["injury_location"] == "chest"
