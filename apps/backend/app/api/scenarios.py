from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import ensure_owned_case, get_current_user, get_owned_case, get_owned_scenario, get_owned_video
from app.database import get_db
from app.infrastructure.jobs.tasks import enqueue
from app.models import Case, GeneratedVideo, Scenario, User, VideoScenarioSpec, VideoShot
from app.schemas.common import AnalysisStatus
from app.schemas.scenario import CompareRequest, CompareResult, ScenarioDetail, ScenarioOut
from app.schemas.video import VideoOut, VideoSpecOut
from app.features.scenarios.scenario_service import scenario_detail, scenario_out
from app.features.visualization.video_service import VideoService
from app.adapters.storage import get_storage_provider

router = APIRouter(prefix="/api", tags=["scenarios"])


def _get_scenario(db: Session, case: Case, scenario_id: str) -> Scenario:
    sc = db.get(Scenario, scenario_id)
    if not sc or sc.case_id != case.id:
        raise HTTPException(status_code=404, detail="scenario not found")
    return sc


@router.get("/cases/{case_id}/scenarios", response_model=list[ScenarioOut])
def list_scenarios(case: Case = Depends(get_owned_case), db: Session = Depends(get_db)):
    from app.models import Scenario

    scs = db.query(Scenario).filter_by(case_id=case.id).order_by(Scenario.created_at).all()
    out = []
    for sc in scs:
        d = scenario_out(db, sc)
        if d["is_survivor"]:
            out.append(d)
    # survivors first, then rejected
    rejected = [scenario_out(db, sc) for sc in scs if not sc.is_survivor]
    out.extend(sorted(rejected, key=lambda x: x["created_at"]))
    return out


@router.get("/cases/{case_id}/scenarios/{scenario_id}", response_model=ScenarioDetail)
def get_scenario(case: Case = Depends(get_owned_case), scenario_id: str = "", db: Session = Depends(get_db)):
    sc = _get_scenario(db, case, scenario_id)
    return scenario_detail(db, sc)


@router.post("/cases/{case_id}/scenarios/{scenario_id}/validate", response_model=ScenarioDetail)
def validate_scenario(case: Case = Depends(get_owned_case), scenario_id: str = "", db: Session = Depends(get_db)):
    sc = _get_scenario(db, case, scenario_id)
    if sc.status != "SURVIVING":
        raise HTTPException(status_code=422, detail="only surviving scenarios can be validated for visualization")
    return scenario_detail(db, sc)


@router.post("/cases/{case_id}/scenarios/{scenario_id}/visualize", response_model=AnalysisStatus)
def visualize_scenario(case: Case = Depends(get_owned_case), scenario_id: str = "", db: Session = Depends(get_db)):
    sc = _get_scenario(db, case, scenario_id)
    if not sc.is_survivor:
        raise HTTPException(status_code=422, detail="cannot visualize a rejected scenario")
    job = enqueue(db, case.id, "GENERATE_VIDEO", {"scenario_id": scenario_id})
    db.flush()
    return AnalysisStatus(case_id=case.id, status="PENDING", progress=0, job_id=job.id)


@router.get("/cases/{case_id}/scenarios/{scenario_id}/spec", response_model=VideoSpecOut)
def get_scenario_spec(case: Case = Depends(get_owned_case), scenario_id: str = "", db: Session = Depends(get_db)):
    sc = _get_scenario(db, case, scenario_id)
    spec = VideoService().build_spec(db, sc)
    shots = db.query(VideoShot).filter_by(spec_id=spec.id).order_by(VideoShot.shot_index).all()
    from app.schemas.video import VideoShotOut

    return VideoSpecOut(
        id=spec.id,
        scenario_id=spec.scenario_id,
        case_id=spec.case_id,
        status=spec.status,
        spec=spec.spec,
        visual_prompt=spec.visual_prompt,
        shots=[VideoShotOut.model_validate(s) for s in shots],
    )


@router.get("/scenarios/{scenario_id}/video", response_model=list[VideoOut])
def get_scenario_videos(scenario: Scenario = Depends(get_owned_scenario), db: Session = Depends(get_db)):
    videos = db.query(GeneratedVideo).filter_by(scenario_id=scenario.id).order_by(GeneratedVideo.created_at.desc()).all()
    out = []
    for v in videos:
        d = VideoOut.model_validate(v)
        d.stream_url = f"/api/videos/{v.id}/stream" if v.video_path else ""
        out.append(d)
    return out


@router.get("/videos/{video_id}/stream")
def stream_video(video: GeneratedVideo = Depends(get_owned_video)):
    if not video.video_path:
        raise HTTPException(status_code=404, detail="video not found")
    storage = get_storage_provider()
    from pathlib import Path

    p = Path(video.video_path)
    if p.exists():
        return FileResponse(video.video_path, media_type="video/mp4")
    data = storage.load(video.video_path)
    if data is None:
        raise HTTPException(status_code=404, detail="video file missing")
    import io

    from fastapi.responses import StreamingResponse

    return StreamingResponse(io.BytesIO(data), media_type="video/mp4")


@router.post("/scenarios/compare", response_model=CompareResult)
def compare_scenarios(
    body: CompareRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    from app.adapters.providers import get_llm_provider

    scs = []
    for sid in body.scenario_ids[:4]:
        sc = db.get(Scenario, sid)
        if sc:
            ensure_owned_case(db, sc.case_id, user)
            scs.append(scenario_out(db, sc))
    if len(scs) < 2:
        raise HTTPException(status_code=422, detail="select 2-4 scenarios to compare")
    try:
        llm = get_llm_provider()
        raw = llm.run_task("compare_scenarios", {"scenarios": scs})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"comparison provider failed: {exc}") from exc
    discriminating = raw.get("discriminating") or [
        {"pair": [scs[i]["hypothesis_label"], scs[j]["hypothesis_label"]], "note": "Compare evidence support and unknowns to identify discriminating evidence."}
        for i in range(len(scs))
        for j in range(i + 1, len(scs))
    ][:3]
    return CompareResult(
        case_id=scs[0]["case_id"],
        scenarios=scs,
        shared=raw.get("shared", []),
        differences=raw.get("differences", []),
        discriminating=discriminating,
    )