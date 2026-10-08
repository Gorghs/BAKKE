from __future__ import annotations

from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.infrastructure.hashing import sha256_bytes, sha256_file
from app.infrastructure.ids import Ids
from app.adapters.storage import get_storage_provider
from app.models import (
    AuditEvent,
    Case,
    Constraint,
    Conflict,
    EvidenceItem,
    Fact,
    ForensicAnchor,
    Scenario,
    ScenarioScore,
    TimelineEvent,
)
from app.domain.constants import EVIDENCE_TYPES


class CaseService:
    def create_case(self, db: Session, owner_id: str, name: str, description: str = "", tags: list[str] | None = None) -> Case:
        case = Case(owner_id=owner_id, name=name, description=description, tags=tags or [])
        db.add(case)
        db.flush()
        db.add(
            AuditEvent(
                case_id=case.id,
                action="case_created",
                actor_type="INVESTIGATOR",
                actor_id=owner_id,
                summary=f"Case created: {name}",
            )
        )
        db.flush()
        return case

    def get_case(self, db: Session, case_id: str) -> Case:
        case = db.get(Case, case_id)
        if not case:
            raise HTTPException(status_code=404, detail="case not found")
        return case

    def upload_evidence(
        self,
        db: Session,
        case_id: str,
        item_type: str,
        title: str,
        description: str,
        raw_text: str,
        file: UploadFile | None,
    ) -> EvidenceItem:
        if item_type not in EVIDENCE_TYPES:
            raise HTTPException(status_code=422, detail=f"invalid evidence type: {item_type}")
        if item_type in ("AUDIO", "IMAGE", "VIDEO", "PHYSICAL_EVIDENCE") and not file and not raw_text:
            raise HTTPException(status_code=422, detail=f"evidence type {item_type} requires a file upload")

        storage = get_storage_provider()
        file_path = ""
        content_hash = ""
        size = 0
        if file:
            data = file.file.read()
            size = len(data)
            if size == 0:
                raise HTTPException(status_code=422, detail="empty file")
            limit_mb = get_settings().UPLOAD_MAX_MB
            if size > limit_mb * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"file exceeds the {limit_mb} MB upload limit",
                )
            content_hash = sha256_bytes(data)
            evidence_id = Ids.next_evidence(db, case_id)
            file_path = storage.save(case_id, evidence_id, file.filename or "evidence", data)
        else:
            content_hash = sha256_bytes(raw_text.encode())

        evidence_id = Ids.next_evidence(db, case_id)
        ev = EvidenceItem(
            case_id=case_id,
            evidence_id=evidence_id,
            item_type=item_type,
            title=title,
            description=description,
            file_path=file_path,
            original_filename=file.filename if file else "",
            mime_type=file.content_type if file else "",
            size_bytes=size,
            content_hash=content_hash,
            status="UPLOADED",
            raw_text=raw_text,
            extra={"evidence_type": item_type},
        )
        db.add(ev)
        case = db.get(Case, case_id)
        if case:
            case.evidence_count = db.query(EvidenceItem).filter_by(case_id=case_id).count() + 1
        db.flush()
        db.add(
            AuditEvent(
                case_id=case_id,
                action="evidence_upload",
                actor_type="INVESTIGATOR",
                summary=f"Uploaded {item_type} evidence {evidence_id}: {title}",
                input_object_ids=[ev.id],
                extra={"content_hash": content_hash},
            )
        )
        db.flush()
        return ev

    def dashboard(self, db: Session, case_id: str) -> dict[str, Any]:
        case = self.get_case(db, case_id)
        evidence_count = db.query(EvidenceItem).filter_by(case_id=case_id).count()
        facts = db.query(Fact).filter_by(case_id=case_id).all()
        timeline = db.query(TimelineEvent).filter_by(case_id=case_id).order_by(TimelineEvent.ordering_index).all()
        constraints = db.query(Constraint).filter_by(case_id=case_id).all()
        anchors = db.query(ForensicAnchor).filter_by(case_id=case_id).all()
        conflicts = db.query(Conflict).filter_by(case_id=case_id).all()
        scenarios = db.query(Scenario).filter_by(case_id=case_id).all()
        survivors = [s for s in scenarios if s.is_survivor]

        top_scenarios = []
        for sc in survivors:
            score = 0
            sc_score = db.query(ScenarioScore).filter_by(scenario_id=sc.id).order_by(ScenarioScore.created_at.desc()).first()
            if sc_score:
                score = sc_score.total
            hyp_label = ""
            from app.models import Hypothesis

            hyp = db.get(Hypothesis, sc.hypothesis_id)
            if hyp:
                hyp_label = hyp.hypothesis_id
            top_scenarios.append({"id": sc.id, "hypothesis_label": hyp_label, "score": score, "summary": sc.summary[:200], "rank": sc.extra.get("rank", 0)})
        top_scenarios.sort(key=lambda x: x["rank"] or 999)

        from app.models import GeneratedVideo, SimilarCase

        return {
            "case": case,
            "evidence_count": evidence_count,
            "analysis_status": case.status,
            "fact_count": len(facts),
            "timeline_count": len(timeline),
            "constraint_count": len(constraints),
            "hard_constraint_count": sum(1 for c in constraints if c.strength == "HARD"),
            "conflict_count": len(conflicts),
            "unknown_area_count": sum(1 for f in facts if f.extra.get("camera_coverage") == "NO_COVERAGE"),
            "anchor_count": len(anchors),
            "scenario_survivor_count": len(survivors),
            "scenario_rejected_count": len(scenarios) - len(survivors),
            "top_scenarios": top_scenarios,
            "similar_case_count": db.query(SimilarCase).filter_by(case_id=case_id).count(),
            "video_count": db.query(GeneratedVideo).filter_by(case_id=case_id).count(),
        }