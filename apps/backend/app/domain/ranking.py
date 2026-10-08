from __future__ import annotations

from typing import Any


def rank_scenarios(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic ranking: score desc, then fewer unknowns, then fewer
    unsupported assumptions, then hypothesis label."""
    def key(sc: dict[str, Any]) -> tuple:
        score = sc.get("score_total", 0)
        unknowns = sc.get("unknown_count", 0)
        unsupported = sc.get("unsupported_count", 0)
        label = sc.get("hypothesis_label", "")
        return (-score, unknowns, unsupported, label)

    return sorted(scenarios, key=key)