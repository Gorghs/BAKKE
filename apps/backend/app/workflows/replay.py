"""Offline replay: re-run a recorded workflow without external API calls.

A replay manifest is written at the end of every AnalyzeCase / GenerateVideo
run (provider labels, prompt version, stage timings, evidence hashes). Replay
forces every provider to an explicit DEVELOPMENT MOCK, re-executes the
workflow, stores the replay's own manifest under a separate key and restores
the original manifest so provenance of the recorded run is preserved.
"""
from __future__ import annotations

import logging
from typing import Any

from app.adapters.persistence import SqlAlchemyUnitOfWork
from app.adapters.providers import mock_providers
from app.workflows.analyze_case import AnalyzeCaseWorkflow
from app.workflows.generate_video import GenerateVideoWorkflow
from app.workflows.manifest import load_manifest, manifest_path, write_manifest

logger = logging.getLogger(__name__)

REPLAY_JOB_TYPES = ("ANALYZE_CASE", "GENERATE_VIDEO")


def replay_case(
    case_id: str,
    job_type: str = "ANALYZE_CASE",
    scenario_id: str = "",
    session_factory: Any | None = None,
) -> dict[str, Any]:
    """Re-execute a workflow for a case with all providers forced offline."""
    if job_type not in REPLAY_JOB_TYPES:
        raise ValueError(f"unknown replay job type: {job_type}")
    if job_type == "GENERATE_VIDEO" and not scenario_id:
        raise ValueError("scenario_id is required to replay GENERATE_VIDEO")

    if session_factory is None:
        from app.database import SessionLocal

        session_factory = SessionLocal
    from app.models import Case, Scenario

    kind = "analysis" if job_type == "ANALYZE_CASE" else f"video_{scenario_id}"
    original_bytes = (
        manifest_path(case_id, kind).read_bytes() if manifest_path(case_id, kind).is_file() else None
    )
    original = load_manifest(case_id, kind)

    try:
        with session_factory() as db:
            if db.get(Case, case_id) is None:
                raise ValueError("case not found")
            if scenario_id:
                scenario = db.get(Scenario, scenario_id)
                if scenario is None:
                    raise ValueError("scenario not found")
                if scenario.case_id != case_id:
                    raise ValueError("scenario does not belong to this case")
            uow = SqlAlchemyUnitOfWork(db)
            with mock_providers():
                if job_type == "ANALYZE_CASE":
                    result = AnalyzeCaseWorkflow(uow).run(case_id)
                else:
                    result = GenerateVideoWorkflow(uow).run(scenario_id)
            db.commit()

        # The workflow wrote its manifest under the canonical key; keep the
        # replay's provenance separately and restore the original recording.
        replayed = load_manifest(case_id, kind)
        if replayed is not None:
            write_manifest(case_id, f"{kind}.replay", replayed)
    finally:
        if original_bytes is not None:
            manifest_path(case_id, kind).write_bytes(original_bytes)

    logger.info("replay complete case=%s job_type=%s run=%s", case_id, job_type, result.get("run_id", ""))
    return {
        **result,
        "replayed": True,
        "offline": True,
        "providers_forced": "mock",
        "original_manifest": original,
    }
