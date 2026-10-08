from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # domain stays ORM-free: rows are duck-typed at runtime
    from app.models import Fact, ForensicAnchor, TimelineEvent


@dataclass
class ConstraintViolation:
    type: str  # TEMPORAL/SPATIAL/PHYSICAL/FORENSIC/OBJECT/PERSON/WITNESS/EVIDENTIARY
    severity: str  # HARD/SOFT
    description: str
    constraint_ref: str = ""
    source_evidence_ids: list[str] = field(default_factory=list)


def _minutes(tok: str) -> int | None:
    try:
        if ":" in tok:
            h, m = tok.split(":")
            return int(h) * 60 + int(m)
    except (ValueError, TypeError):
        pass
    return None


class ConstraintEngine:
    """Deterministic constraint checking. LLMs are never used here.

    Hard violations reject a scenario; soft violations only reduce its
    evidence-consistency score.
    """

    def check(
        self,
        scenario: dict[str, Any],
        anchors: list[ForensicAnchor],
        facts: list[Fact],
        timeline: list[TimelineEvent],
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        violations.extend(self._check_forensic(scenario, anchors))
        violations.extend(self._check_spatial_temporal(scenario, facts, timeline))
        violations.extend(self._check_evidentiary(scenario))
        return violations

    def _check_forensic(self, scenario: dict[str, Any], anchors: list[ForensicAnchor]) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        scenario_injury = scenario.get("injury_location")
        if not scenario_injury:
            return violations
        for a in anchors:
            if a.type != "INJURY_LOCATION":
                continue
            anchor_loc = (a.value or {}).get("location", "")
            if anchor_loc and scenario_injury != anchor_loc:
                violations.append(
                    ConstraintViolation(
                        type="FORENSIC",
                        severity="HARD",
                        description=(
                            f"Scenario asserts injury at '{scenario_injury}' but the authoritative "
                            f"finding ({a.anchor_id}) reports injury at '{anchor_loc}'."
                        ),
                        constraint_ref=a.anchor_id,
                        source_evidence_ids=a.source_evidence_ids,
                    )
                )
        return violations

    def _check_spatial_temporal(
        self, scenario: dict[str, Any], facts: list[Fact], timeline: list[TimelineEvent]
    ) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        # Map verified spatial facts: person -> list of (time, location)
        verified: dict[str, list[tuple[int, str]]] = {}
        for f in facts:
            if f.status == "HARD" or f.source_type in ("VIDEO", "IMAGE", "LOCATION_RECORD", "FORENSIC_REPORT"):
                sp = f.extra.get("spatial") or {}
                if sp.get("person") and sp.get("location"):
                    t = _minutes(str(sp.get("time", "")))
                    if t is not None:
                        verified.setdefault(sp["person"].lower(), []).append((t, sp["location"]))

        # A scenario may only place a person at an unsupported location if it is
        # marked as inferred/unknown. KNOWN claims at a verified-elsewhere time
        # create a HARD TEMPORAL/SPATIAL conflict.
        for ev in scenario.get("events", []):
            timing = ev.get("timing") or {}
            loc = (ev.get("location") or "").strip()
            if not loc or not timing.get("start"):
                continue
            t = _minutes(str(timing["start"]))
            if t is None:
                continue
            for person in scenario.get("participants", []):
                slots = verified.get(person.lower(), [])
                for vt, vloc in slots:
                    if vloc != loc and abs(vt - t) <= 10:
                        violations.append(
                            ConstraintViolation(
                                type="TEMPORAL",
                                severity="HARD",
                                description=(
                                    f"Scenario places {person} at {loc} at ~{timing['start']} but verified "
                                    f"evidence places {person} at {vloc} at ~{vt}."
                                ),
                                source_evidence_ids=[],
                            )
                        )
        return violations

    def _check_evidentiary(self, scenario: dict[str, Any]) -> list[ConstraintViolation]:
        violations: list[ConstraintViolation] = []
        for ev in scenario.get("events", []):
            if ev.get("event_type") == "KNOWN" and not ev.get("linked_fact_ids"):
                violations.append(
                    ConstraintViolation(
                        type="EVIDENTIARY",
                        severity="SOFT",
                        description=f"Scenario asserts known event without supporting facts: {ev.get('description', '')[:120]}",
                    )
                )
        return violations