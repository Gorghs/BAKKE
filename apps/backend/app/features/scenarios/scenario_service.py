from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    Conflict,
    Constraint,
    DiscriminatingEvidence,
    EvidenceItem,
    Fact,
    ForensicAnchor,
    GeneratedVideo,
    Hypothesis,
    Scenario,
    ScenarioEvent,
    ScenarioEvidenceLink,
    ScenarioScore,
    SimilarCase,
    TimelineEvent,
    VideoScenarioSpec,
)


def scenario_out(db: Session, sc: Scenario) -> dict[str, Any]:
    hyp = db.get(Hypothesis, sc.hypothesis_id)
    score = db.query(ScenarioScore).filter_by(scenario_id=sc.id).order_by(ScenarioScore.created_at.desc()).first()
    links = db.query(ScenarioEvidenceLink).filter_by(scenario_id=sc.id).all()
    events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by(ScenarioEvent.event_order).all()
    supporting = [l.evidence_item_id for l in links if l.link_type == "SUPPORTING"]
    contradicting = [l.evidence_item_id for l in links if l.link_type == "CONTRADICTING"]
    unknown_count = sum(1 for e in events if e.event_type == "UNKNOWN")
    return {
        "id": sc.id,
        "case_id": sc.case_id,
        "hypothesis_id": sc.hypothesis_id,
        "hypothesis_label": hyp.hypothesis_id if hyp else "H-000",
        "status": sc.status,
        "summary": sc.summary,
        "cause_claim": sc.cause_claim,
        "participants": sc.participants,
        "rejection_reason": sc.rejection_reason,
        "final_verdict": sc.final_verdict,
        "iteration_count": sc.iteration_count,
        "is_survivor": sc.is_survivor,
        "score_total": score.total if score else 0,
        "score_breakdown": score.breakdown if score else {},
        "supporting_evidence": supporting,
        "contradicting_evidence": contradicting,
        "unknown_count": unknown_count,
        "created_at": sc.created_at,
    }


def scenario_detail(db: Session, sc: Scenario) -> dict[str, Any]:
    base = scenario_out(db, sc)
    events = db.query(ScenarioEvent).filter_by(scenario_id=sc.id).order_by(ScenarioEvent.event_order).all()
    known = [e.description for e in events if e.event_type == "KNOWN"]
    inferred = [e.description for e in events if e.event_type == "INFERRED"]
    unknown = [e.description for e in events if e.event_type in ("UNKNOWN", "HYPOTHESIZED")] + (sc.extra.get("unknowns") or [])
    similar = [
        {"reference_label": s.reference_label, "title": s.title, "similarity": s.similarity, "relevant_patterns": s.relevant_patterns}
        for s in db.query(SimilarCase).filter_by(case_id=sc.case_id).all()
    ]
    disc = []
    for d in db.query(DiscriminatingEvidence).filter_by(case_id=sc.case_id).all():
        if sc.hypothesis_id and any(sc.hypothesis_id == p for p in d.scenario_pair):
            disc.append(
                {
                    "pair": d.scenario_pair,
                    "shared": d.shared_evidence,
                    "differing": d.differing_evidence,
                    "needed": d.needed_evidence,
                    "note": d.note,
                }
            )
    video = None
    vid = db.query(GeneratedVideo).filter_by(scenario_id=sc.id).order_by(GeneratedVideo.created_at.desc()).first()
    if vid:
        video = {
            "id": vid.id,
            "status": vid.status,
            "provider": vid.provider,
            "is_mock": vid.is_mock,
            "duration_seconds": vid.duration_seconds,
            "width": vid.width,
            "height": vid.height,
            "label_text": vid.label_text,
            "validation": vid.validation,
            "error": vid.error,
        }
    audit = [
        {"action": a.action, "summary": a.summary, "provider": a.provider, "timestamp": a.timestamp}
        for a in db.query(AuditEvent).filter_by(case_id=sc.case_id).order_by(AuditEvent.created_at.desc()).limit(50).all()
        if sc.id in (a.input_object_ids or []) or a.output_object_id == sc.id
    ]
    anchors_satisfied = []
    scenario_injury = (sc.extra or {}).get("injury_location")
    for a in db.query(ForensicAnchor).filter_by(case_id=sc.case_id).all():
        if a.type == "INJURY_LOCATION":
            if not scenario_injury or (a.value or {}).get("location") == scenario_injury:
                anchors_satisfied.append(a.anchor_id)
    base.update(
        {
            "events": [
                {
                    "id": e.id,
                    "scenario_id": e.scenario_id,
                    "event_order": e.event_order,
                    "description": e.description,
                    "event_type": e.event_type,
                    "linked_fact_ids": e.linked_fact_ids,
                    "evidence_links": e.evidence_links,
                    "timing": e.timing,
                    "location": e.location,
                }
                for e in events
            ],
            "known": known,
            "inferred": inferred,
            "unknown": unknown,
            "anchors_satisfied": anchors_satisfied,
            "similar_cases": similar,
            "discriminating": disc,
            "video": video,
            "audit": audit,
        }
    )
    return base