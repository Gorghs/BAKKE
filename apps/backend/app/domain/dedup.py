from __future__ import annotations

import re
from typing import Any


def _signature(scenario: dict[str, Any]) -> str:
    """Normalized signature used to merge semantically equivalent scenarios."""
    participants = sorted(p.lower().strip() for p in scenario.get("participants", []))
    cause = re.sub(r"\s+", " ", (scenario.get("cause_claim") or "").lower().strip())
    claims = []
    for ev in scenario.get("events", []):
        if ev.get("event_type") in ("KNOWN", "INFERRED"):
            claims.append(re.sub(r"\s+", " ", (ev.get("description") or "").lower().strip()))
    return "|".join([";".join(participants), cause, ";".join(sorted(set(claims)))])


def deduplicate(scenarios: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Merge semantically equivalent candidates.

    Returns (unique_scenarios, merged_records) where merged_records describes
    which scenario was merged into which, for the audit trail.
    """
    by_signature: dict[str, list[dict[str, Any]]] = {}
    for sc in scenarios:
        by_signature.setdefault(_signature(sc), []).append(sc)

    unique: list[dict[str, Any]] = []
    merged: list[dict[str, Any]] = []
    for sig, group in by_signature.items():
        if len(group) == 1:
            unique.append(group[0])
            continue
        # keep the first (lowest hypothesis id, created earliest)
        keeper = sorted(group, key=lambda s: s.get("hypothesis_label", ""))[0]
        keeper["dedup_merged"] = []
        for other in group:
            if other is keeper:
                continue
            merged.append(
                {
                    "merged_into": keeper.get("hypothesis_label", ""),
                    "merged": other.get("hypothesis_label", ""),
                    "signature": sig,
                }
            )
            keeper["dedup_merged"].append(other.get("hypothesis_label", ""))
        unique.append(keeper)
    return unique, merged