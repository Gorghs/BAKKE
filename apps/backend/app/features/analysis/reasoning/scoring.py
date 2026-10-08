from __future__ import annotations

from typing import Any


def compute_evidence_consistency_score(
    scenario: dict[str, Any],
    supporting: list[str],
    contradicting: list[str],
    hard_violations: list[str],
    witness_conflicts: list[str],
    unsupported: list[str],
    unknowns: list[str],
    inferred: list[str],
    anchors_satisfied: bool,
) -> dict[str, Any]:
    """Deterministic Evidence Consistency Score.

    The score represents consistency with the currently available evidence.
    It does NOT represent the probability that the scenario actually occurred.

    Base 100. Adjustments:
      +min(20, 2 * #supporting)          evidence coverage
      +5 if all forensic anchors satisfied
      -30 per hard constraint violation  (survivors normally have 0)
      -5  per contradicting evidence
      -3  per witness conflict
      -5  per unsupported claim/assumption
      -4  per unknown event (cap 20)
      -2  per inferred event (cap 10)
    Clamped to [0, 100].
    """
    breakdown: dict[str, Any] = {}
    score = 100.0

    coverage = min(20, 2 * len(supporting))
    score += coverage
    breakdown["coverage_bonus"] = coverage

    if anchors_satisfied:
        score += 5
        breakdown["forensic_consistency_bonus"] = 5

    score -= 30 * len(hard_violations)
    score -= 5 * len(contradicting)
    score -= 3 * len(witness_conflicts)
    score -= 5 * len(unsupported)
    score -= min(20, 4 * len(unknowns))
    score -= min(10, 2 * len(inferred))

    total = max(0, min(100, round(score)))
    breakdown.update(
        {
            "supporting_evidence_count": len(supporting),
            "contradicting_evidence_count": len(contradicting),
            "hard_constraint_violations": len(hard_violations),
            "witness_conflict_count": len(witness_conflicts),
            "unsupported_assumption_count": len(unsupported),
            "unknown_event_count": len(unknowns),
            "inferred_event_count": len(inferred),
            "note": "Evidence Consistency Score - represents consistency with currently available evidence, NOT the probability this scenario occurred.",
        }
    )
    return {"total": total, "breakdown": breakdown}