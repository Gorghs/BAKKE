from __future__ import annotations

from app.adapters.ai.rule_based import mock_compare


def _scenario(label: str, participants: list[str], sup: list[str], unknown: int = 0, cause: str = "") -> dict:
    return {
        "id": f"sc-{label}",
        "hypothesis_label": label,
        "participants": participants,
        "supporting_evidence": sup,
        "contradicting_evidence": [],
        "unknown_count": unknown,
        "cause_claim": cause,
    }


def test_compare_surfaces_shared_supporting_evidence():
    a = _scenario("H-001", ["person a"], ["E-001", "E-002"], cause="person a caused the injury")
    b = _scenario("H-002", ["person a"], ["E-001", "E-002"], cause="person a caused the injury")
    out = mock_compare({"scenarios": [a, b]})
    assert any("E-001" in s and "E-002" in s for s in out["shared"])
    assert not out["differences"]
    assert out["discriminating"][0]["note"].startswith("No single evidence item")


def test_compare_reports_uniquely_supporting_evidence_as_discriminating():
    a = _scenario("H-001", ["person a"], ["E-001", "E-002"])
    b = _scenario("H-002", ["person a"], ["E-001", "E-003"])
    out = mock_compare({"scenarios": [a, b]})
    assert any("E-001" in s for s in out["shared"])
    diffs = " ".join(out["differences"])
    assert "E-002" in diffs and "E-003" in diffs
    disc = out["discriminating"][0]
    assert disc["pair"] == ["H-001", "H-002"]
    assert "E-002" in disc["note"] and "E-003" in disc["note"]


def test_compare_reports_participant_and_cause_differences():
    a = _scenario("H-001", ["person a"], ["E-001"], cause="person a caused the injury")
    b = _scenario("H-002", ["victim"], ["E-001"], cause="victim caused the injury")
    out = mock_compare({"scenarios": [a, b]})
    assert any("E-001" in s for s in out["shared"])
    text = " ".join(out["differences"])
    assert "victim" in text and "person a" in text
    assert "causal claims differ" in text.lower()


def test_compare_never_emits_probability_language():
    a = _scenario("H-001", ["person a"], ["E-001"], unknown=2)
    b = _scenario("H-002", ["victim"], ["E-001"], unknown=1)
    out = mock_compare({"scenarios": [a, b]})
    joined = " ".join(out["shared"] + out["differences"])
    for bad in ("probability", "likely", "most likely", "verdict"):
        assert bad not in joined.lower()
    assert out["note"] == "Comparison is descriptive; no probability claim is made."


def test_compare_requires_two_scenarios():
    out = mock_compare({"scenarios": [_scenario("H-001", ["person a"], ["E-001"])]})
    assert out["shared"] == []
    assert out["differences"] == []
