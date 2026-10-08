"""GenerateVideo workflow: visual spec -> visual-only prompt -> render."""
from __future__ import annotations

import logging
from typing import Any

from app.adapters.providers import get_video_provider
from app.features.visualization.video_service import VideoService
from app.models import GeneratedVideo, Scenario
from app.ports import UnitOfWork
from app.workflows.context import AnalysisContext
from app.workflows.manifest import write_manifest

logger = logging.getLogger(__name__)


class GenerateVideoWorkflow:
    """Renders a schematic reconstruction clip for one scenario.

    The director receives visual-only input (locations, objects, actors,
    timing, camera) — never case reports, evidence IDs or forensic
    reasoning.
    """

    name = "GenerateVideo"

    def __init__(self, uow: UnitOfWork, job_id: str = "") -> None:
        self.uow = uow
        self.ctx = AnalysisContext(case_id="", job_id=job_id)

    def run(self, scenario_id: str) -> dict[str, Any]:
        uow = self.uow
        db = uow.session
        ctx = self.ctx

        scenario = db.get(Scenario, scenario_id)
        if scenario is None:
            raise ValueError("scenario not found")
        ctx.case_id = scenario.case_id

        provider = get_video_provider()
        ctx.note_provider(
            "video_generation",
            getattr(provider, "label", "") or provider.name,
            bool(getattr(provider, "is_mock", False)),
        )

        logger.info(
            "run=%s case=%s scenario=%s starting GenerateVideo",
            ctx.run_id,
            scenario.case_id,
            scenario_id,
        )

        video = GeneratedVideo(
            case_id=scenario.case_id,
            scenario_id=scenario_id,
            status="PENDING",
        )
        db.add(video)
        db.flush()

        svc = VideoService()
        uow.job.set_progress(10, "Building visual specification")
        with ctx.stage("visual_spec"):
            spec = svc.build_spec(db, scenario)
            video.spec_id = spec.id
        db.flush()

        uow.job.set_progress(40, "Rendering video")
        with ctx.stage("render"):
            svc.generate_video(db, scenario, video)

        manifest_path = write_manifest(
            scenario.case_id,
            f"video_{scenario_id}",
            {**ctx.snapshot(), "scenario_id": scenario_id, "video_id": video.id, "status": video.status},
        )
        logger.info("run=%s video=%s status=%s manifest=%s", ctx.run_id, video.id, video.status, manifest_path)
        uow.flush()
        return {"video_id": video.id, "status": video.status, "run_id": ctx.run_id, "manifest": manifest_path}
