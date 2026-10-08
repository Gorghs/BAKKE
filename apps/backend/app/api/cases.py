from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_case
from app.database import get_db
from app.models import Case, User
from app.schemas.case import CaseCreate, CaseDashboard, CaseOut, CaseUpdate
from app.schemas.common import AnalysisStatus
from app.schemas.evidence import (
    AnchorOut,
    ConflictOut,
    ConstraintOut,
    EvidenceOut,
    FactOut,
    FactWithSources,
    FindingOut,
    RelationshipOut,
    TimelineEventOut,
)
from app.features.cases.case_service import CaseService
from app.infrastructure.jobs.tasks import enqueue

router = APIRouter(prefix="/api", tags=["cases"])
svc = CaseService()


@router.post("/cases", response_model=CaseOut)
def create_case(body: CaseCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.create_case(db, user.id, body.name, body.description, body.tags)


@router.get("/cases", response_model=list[CaseOut])
def list_cases(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Case).filter_by(owner_id=user.id).order_by(Case.created_at.desc()).all()


@router.get("/cases/{case_id}", response_model=CaseOut)
def get_case(case: Case = Depends(get_owned_case)):
    return case


@router.patch("/cases/{case_id}", response_model=CaseOut)
def update_case(
    body: CaseUpdate,
    case: Case = Depends(get_owned_case),
    db: Session = Depends(get_db),
):
    if body.name is not None:
        case.name = body.name
    if body.description is not None:
        case.description = body.description
    if body.tags is not None:
        case.tags = body.tags
    db.flush()
    return case


@router.get("/cases/{case_id}/dashboard", response_model=CaseDashboard)
def case_dashboard(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    return svc.dashboard(db, case.id)


@router.post("/cases/{case_id}/evidence", response_model=EvidenceOut)
def upload_evidence(
    case: Case = Depends(get_owned_case),
    item_type: str = Form(...),
    title: str = Form(""),
    description: str = Form(""),
    raw_text: str = Form(""),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    return svc.upload_evidence(db, case.id, item_type, title, description, raw_text, file)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import EvidenceItem

    return db.query(EvidenceItem).filter_by(case_id=case.id).order_by(EvidenceItem.evidence_id).all()


@router.post("/cases/{case_id}/analyze", response_model=AnalysisStatus)
def analyze_case(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    job = enqueue(db, case.id, "ANALYZE_CASE")
    db.flush()
    return AnalysisStatus(case_id=case.id, status="PENDING", progress=0, job_id=job.id)


@router.get("/cases/{case_id}/analysis/status", response_model=AnalysisStatus)
def analysis_status(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.infrastructure.jobs.audit_service import JobService

    job = JobService().latest(db, case.id, "ANALYZE_CASE")
    if not job:
        return AnalysisStatus(case_id=case.id, status="NO_JOB", progress=0)
    return AnalysisStatus(
        case_id=case.id,
        status=job.status,
        progress=job.progress,
        job_id=job.id,
        error=job.error,
        result=job.result,
    )


@router.get("/cases/{case_id}/facts", response_model=list[FactOut])
def list_facts(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Fact

    return db.query(Fact).filter_by(case_id=case.id).order_by(Fact.fact_id).all()


@router.get("/cases/{case_id}/facts/{fact_id}", response_model=FactWithSources)
def get_fact(case: Case = Depends(get_owned_case), fact_id: str = "", db: Session = Depends(get_db)):
    from app.models import EvidenceItem, EvidenceSource, Fact

    fact = db.query(Fact).filter_by(case_id=case.id, fact_id=fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="fact not found")
    sources = []
    ev_map = {e.id: e for e in db.query(EvidenceItem).filter_by(case_id=case.id).all()}
    for ref in fact.source_refs:
        ev_id = ref.get("evidence_id")
        ev = next((e for e in ev_map.values() if e.evidence_id == ev_id), None)
        if ev:
            sources.append({**ref, "evidence_id": ev.evidence_id, "title": ev.title, "item_type": ev.item_type})
    out = FactWithSources.model_validate(fact)
    out.sources = sources
    return out


@router.get("/cases/{case_id}/findings", response_model=list[FindingOut])
def list_findings(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Finding

    return db.query(Finding).filter_by(case_id=case.id).order_by(Finding.finding_id).all()


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineEventOut])
def get_timeline(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import TimelineEvent

    return db.query(TimelineEvent).filter_by(case_id=case.id).order_by(TimelineEvent.ordering_index).all()


@router.get("/cases/{case_id}/constraints", response_model=list[ConstraintOut])
def list_constraints(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Constraint

    return db.query(Constraint).filter_by(case_id=case.id).all()


@router.get("/cases/{case_id}/anchors", response_model=list[AnchorOut])
def list_anchors(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import ForensicAnchor

    return db.query(ForensicAnchor).filter_by(case_id=case.id).all()


@router.get("/cases/{case_id}/conflicts", response_model=list[ConflictOut])
def list_conflicts(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Conflict

    return db.query(Conflict).filter_by(case_id=case.id).all()


@router.get("/cases/{case_id}/entities")
def list_entities(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Entity

    return db.query(Entity).filter_by(case_id=case.id).all()


@router.get("/cases/{case_id}/graph")
def case_graph(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Entity, EntityRelationship

    entities = db.query(Entity).filter_by(case_id=case.id).all()
    rels = db.query(EntityRelationship).filter_by(case_id=case.id).all()
    return {
        "nodes": [
            {"id": e.id, "label": e.name, "type": e.entity_type, "entity_id": e.entity_id} for e in entities
        ],
        "edges": [
            {
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "relation": r.relation_type,
                "evidence": r.evidence_links,
            }
            for r in rels
        ],
    }


@router.get("/cases/{case_id}/similar-cases")
def list_similar(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import SimilarCase

    return db.query(SimilarCase).filter_by(case_id=case.id).order_by(SimilarCase.similarity.desc()).all()


@router.get("/cases/{case_id}/audit")
def list_audit(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.infrastructure.jobs.audit_service import list_audit as _list

    return _list(db, case.id)