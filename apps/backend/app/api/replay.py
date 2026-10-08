from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_case
from app.database import get_db
from app.models import Case, Scenario, User
from app.workflows.manifest import load_manifest
from app.workflows.replay import REPLAY_JOB_TYPES, replay_case

router = APIRouter(prefix="/api", tags=["replay"])


def get_session_factory() -> Callable[[], Session]:
    from app.database import SessionLocal

    return SessionLocal


class ReplayIn(BaseModel):
    job_type: str = Field(default="ANALYZE_CASE", description="ANALYZE_CASE | GENERATE_VIDEO")
    scenario_id: str = Field(default="", description="Required when job_type=GENERATE_VIDEO")


@router.post("/cases/{case_id}/replay")
def replay_workflow(
    body: ReplayIn,
    case: Case = Depends(get_owned_case),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_factory: Callable[[], Session] = Depends(get_session_factory),
) -> dict[str, Any]:
    """Re-run a recorded workflow offline (all providers forced to mock)."""
    if body.job_type not in REPLAY_JOB_TYPES:
        raise HTTPException(status_code=422, detail=f"unknown job_type: {body.job_type}")
    if body.scenario_id:
        scenario = db.get(Scenario, body.scenario_id)
        if scenario is None or scenario.case_id != case.id:
            raise HTTPException(status_code=404, detail="scenario not found")
    try:
        return replay_case(case.id, body.job_type, body.scenario_id, session_factory=session_factory)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/cases/{case_id}/replay/manifest")
def get_manifest(
    kind: str = "analysis",
    case: Case = Depends(get_owned_case),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    manifest = load_manifest(case.id, kind)
    if manifest is None:
        raise HTTPException(status_code=404, detail="no manifest recorded for this case")
    return manifest
