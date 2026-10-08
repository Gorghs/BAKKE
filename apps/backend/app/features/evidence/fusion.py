from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.agents.base import BaseAgent
from app.domain.contracts import ExtractionResult
from app.infrastructure.ids import Ids
from app.models import (
    AuditEvent,
    Constraint,
    Conflict,
    Entity,
    EntityRelationship,
    EvidenceItem,
    Event,
    Fact,
    Finding,
    ForensicAnchor,
    Location,
    Object,
    Person,
    TimelineEvent,
)

# Relationship types per the knowledge graph spec.
ABSENT_VERBS = ("left", "exited", "departed", "went out", "walked out")
PRESENT_VERBS = ("entered", "arrived", "was seen", "was observed", "visible", "appeared", "stayed")
VERIFIED_SOURCES = ("VIDEO", "IMAGE", "CCTV", "LOCATION_RECORD", "DIGITAL_RECORD", "FORENSIC_REPORT")


def _parse_minutes(tok: str) -> int | None:
    try:
        if ":" in tok:
            h, m = tok.split(":")
            return int(h) * 60 + int(m)
        return None
    except (ValueError, TypeError):
        return None


def _sort_key(ev: dict[str, Any]) -> tuple[int, int]:
    start = _parse_minutes(str(ev.get("time_start", "")))
    return (start if start is not None else 100000, ev.get("ordering_index", 0))


class EvidenceFusionAgent(BaseAgent):
    """Merges all extracted source-linked observations into the case knowledge
    graph, generates constraints/anchors from authoritative findings, detects
    conflicts and unknown areas. Does not decide which hypothesis is correct.
    """

    name = "EvidenceFusionAgent"

    def run(self, db: Session, case_id: str, extractions: list[tuple[EvidenceItem, ExtractionResult]]) -> dict[str, Any]:
        entity_by_key: dict[tuple[str, str], Entity] = {}
        facts: list[Fact] = []
        findings: list[Finding] = []
        timeline_events: list[TimelineEvent] = []

        # ---- 1. Entities ----
        for evidence, result in extractions:
            for ed in result.entities:
                key = (ed.name.lower().strip(), ed.entity_type)
                if key not in entity_by_key:
                    ent = Entity(
                        case_id=case_id,
                        entity_id=Ids.next_entity(db, case_id),
                        name=ed.name,
                        entity_type=ed.entity_type,
                        canonical_name=ed.name.lower().strip(),
                        description=ed.description,
                        extra=ed.metadata,
                    )
                    db.add(ent)
                    db.flush()
                    if ed.entity_type == "PERSON":
                        db.add(Person(case_id=case_id, entity_id=ent.id, description=ed.description))
                    elif ed.entity_type == "OBJECT":
                        db.add(Object(case_id=case_id, entity_id=ent.id, category=ed.metadata.get("category", ""), description=ed.description))
                    elif ed.entity_type == "LOCATION":
                        coverage = ed.metadata.get("camera_coverage", "UNKNOWN")
                        db.add(Location(case_id=case_id, entity_id=ent.id, camera_coverage=coverage, description=ed.description))
                    elif ed.entity_type == "EVENT":
                        db.add(Event(case_id=case_id, entity_id=ent.id, summary=ed.description))
                    entity_by_key[key] = ent

        # ---- 2. Facts ----
        for evidence, result in extractions:
            for fd in result.facts:
                refs = [r.model_dump() for r in fd.source_refs]
                fact = Fact(
                    case_id=case_id,
                    fact_id=Ids.next_fact(db, case_id),
                    statement=fd.statement,
                    status=fd.status,
                    constraint_strength=fd.constraint_strength,
                    source_type=evidence.item_type,
                    category=fd.category,
                    qualifier=fd.qualifier,
                    source_evidence_ids=fd.source_evidence_ids or [evidence.evidence_id],
                    source_refs=refs,
                    is_authoritative=fd.is_authoritative,
                    extra=fd.metadata,
                )
                db.add(fact)
                db.flush()
                facts.append(fact)
        db.flush()

        # ---- 3. Findings -> anchors + constraints ----
        for evidence, result in extractions:
            for fnd in result.findings:
                finding = Finding(
                    case_id=case_id,
                    finding_id=Ids.next_finding(db, case_id),
                    category=fnd.category,
                    title=fnd.title,
                    summary=fnd.summary,
                    details=fnd.details,
                    status=fnd.status,
                    strength=fnd.strength,
                    source_evidence_ids=fnd.source_evidence_ids or [evidence.evidence_id],
                )
                db.add(finding)
                db.flush()
                findings.append(finding)
                if fnd.category in ("FORENSIC", "POST_MORTEM") and fnd.strength == "HARD":
                    self._make_anchor(db, case_id, finding, evidence)

        # ---- 4. Timeline ----
        drafts: list[dict[str, Any]] = []
        for evidence, result in extractions:
            for td in result.timeline_events:
                drafts.append(
                    {
                        "title": td.title,
                        "description": td.description,
                        "time_type": td.time_type,
                        "time_start": td.time_start,
                        "time_end": td.time_end,
                        "time_label": td.time_label,
                        "certainty": td.certainty,
                        "ordering_index": td.ordering_index,
                        "linked_fact_ids": td.linked_fact_ids,
                        "source_evidence_ids": td.source_evidence_ids or [evidence.evidence_id],
                        "_order": len(drafts),
                    }
                )
        drafts.sort(key=_sort_key)
        for i, d in enumerate(drafts):
            te = TimelineEvent(
                case_id=case_id,
                event_id=Ids.next_timeline(db, case_id),
                title=d["title"],
                description=d["description"],
                time_type=d["time_type"],
                time_start=d["time_start"],
                time_end=d["time_end"],
                time_label=d["time_label"],
                certainty=d["certainty"],
                ordering_index=i,
                linked_fact_ids=d["linked_fact_ids"],
                source_evidence_ids=d["source_evidence_ids"],
            )
            db.add(te)
            db.flush()
            timeline_events.append(te)

        # ---- 5. Conflicts ----
        conflicts = self._detect_conflicts(db, case_id, facts)

        # ---- 6. Relationships (lightweight knowledge-graph edges) ----
        self._build_relationships(db, case_id, facts, entity_by_key)

        db.flush()

        # ---- 7. Unknown areas ----
        unknown_areas = self._unknown_areas(facts)

        db.add(
            AuditEvent(
                case_id=case_id,
                action="evidence_fusion",
                category="ANALYSIS",
                agent=self.name,
                provider=self.llm.name,
                summary=f"Fused {len(facts)} facts, {len(findings)} findings, {len(timeline_events)} timeline events, {len(conflicts)} conflicts",
                input_object_ids=[e.id for e, _ in extractions],
            )
        )
        db.flush()

        context = {
            "facts": facts,
            "fact_by_id": {f.fact_id: f for f in facts},
            "entities": list(entity_by_key.values()),
            "timeline": timeline_events,
            "anchors": db.query(ForensicAnchor).filter_by(case_id=case_id).all(),
            "constraints": db.query(Constraint).filter_by(case_id=case_id).all(),
            "conflicts": conflicts,
            "unknown_areas": unknown_areas,
            "evidence_by_id": {e.evidence_id: e for e, _ in extractions},
        }
        return context

    def _make_anchor(self, db: Session, case_id: str, finding: Finding, evidence: EvidenceItem) -> None:
        details = finding.details or {}
        anchor_type = "OTHER"
        value: dict[str, Any] = {}
        if details.get("injury_location"):
            anchor_type = "INJURY_LOCATION"
            value = {"location": details["injury_location"]}
        elif details.get("cause_of_death"):
            anchor_type = "CAUSE_OF_DEATH"
            value = {"cause": details["cause_of_death"]}
        if not value:
            return
        anchor = ForensicAnchor(
            case_id=case_id,
            anchor_id=Ids.next_anchor(db, case_id),
            type=anchor_type,
            value=value,
            normalized=str(value.get("location", value.get("cause", ""))).lower().strip(),
            source_evidence_ids=[evidence.evidence_id],
        )
        db.add(anchor)
        db.flush()
        constraint = Constraint(
            case_id=case_id,
            constraint_id=Ids.next_constraint(db, case_id),
            constraint_type="FORENSIC",
            strength="HARD",
            description=f"Authoritative finding {finding.title}: every compatible scenario must preserve this value exactly.",
            expression={"anchor": anchor_type, "value": value},
            anchor_id=anchor.id,
            source_evidence_ids=[evidence.evidence_id],
        )
        db.add(constraint)

    def _detect_conflicts(self, db: Session, case_id: str, facts: list[Fact]) -> list[Conflict]:
        conflicts: list[Conflict] = []
        spatial_by_person: dict[str, list[Fact]] = {}
        for f in facts:
            sp = f.extra.get("spatial") or {}
            if sp.get("person"):
                spatial_by_person.setdefault(sp["person"].lower(), []).append(f)

        for person, flist in spatial_by_person.items():
            for a in flist:
                for b in flist:
                    if a.id == b.id:
                        continue
                    spa, spb = a.extra.get("spatial", {}), b.extra.get("spatial", {})
                    ta, tb = _parse_minutes(str(spa.get("time", ""))), _parse_minutes(str(spb.get("time", "")))
                    if ta is None or tb is None:
                        continue
                    if abs(ta - tb) > 10:
                        continue
                    if spa.get("location") == spb.get("location"):
                        continue
                    if a.source_type == b.source_type:
                        continue
                    is_absent = any(v in str(a.statement).lower() for v in ABSENT_VERBS)
                    is_present = any(v in str(b.statement).lower() for v in PRESENT_VERBS)
                    if not (is_absent or is_present):
                        continue
                    conflict = Conflict(
                        case_id=case_id,
                        conflict_id=Ids.next_conflict(db, case_id),
                        subject=f"{spa.get('person')} presence at ~{spa.get('time')}",
                        description=(
                            f"{spa.get('person')}: source {a.source_evidence_ids} states '{a.statement[:120]}' "
                            f"while source {b.source_evidence_ids} states '{b.statement[:120]}'."
                        ),
                        sides=[
                            {"claim": a.statement, "evidence_ids": a.source_evidence_ids},
                            {"claim": b.statement, "evidence_ids": b.source_evidence_ids},
                        ],
                    )
                    db.add(conflict)
                    conflicts.append(conflict)
                    break
        return conflicts

    def _build_relationships(self, db: Session, case_id: str, facts: list[Fact], entity_by_key: dict) -> None:
        for f in facts:
            sp = f.extra.get("spatial") or {}
            if not sp:
                continue
            person_ent = entity_by_key.get((sp["person"].lower(), "PERSON"))
            loc_ent = entity_by_key.get((sp["location"].lower(), "LOCATION"))
            if person_ent and loc_ent:
                rel = EntityRelationship(
                    case_id=case_id,
                    source_entity_id=person_ent.id,
                    target_entity_id=loc_ent.id,
                    relation_type="SEEN_AT",
                    evidence_links=f.source_evidence_ids,
                    extra={"time": sp.get("time")},
                )
                db.add(rel)

    def _unknown_areas(self, facts: list[Fact]) -> list[str]:
        areas: list[str] = []
        seen: set[str] = set()
        for f in facts:
            cov = f.extra.get("camera_coverage")
            if cov == "NO_COVERAGE":
                key = "no_observation"
                if key not in seen:
                    seen.add(key)
                    areas.append("Location without camera coverage (no observation available).")
        if not areas:
            areas.append("The causal sequence inside the observed boundaries is not fully established.")
        return areas