"""AnalyzeCase workflow: extraction -> fusion -> retrieval -> reasoning."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.adapters.providers import (
    get_embedding_provider,
    get_llm_provider,
    get_video_provider,
    get_video_understanding_provider,
    get_vision_provider,
)
from app.features.analysis.reasoning.engine import ReasoningEngine
from app.features.analysis.retrieval.similar_cases import retrieve_similar_cases
from app.models import (
    Case,
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
from app.ports import UnitOfWork
from app.workflows.context import AnalysisContext
from app.workflows.extract_evidence import ExtractEvidenceWorkflow
from app.workflows.manifest import write_manifest

logger = logging.getLogger(__name__)

# Rows that fusion derives from the extractions, in child-before-parent order.
# Purged before every fusion so re-running analysis does not duplicate the
# knowledge graph. Evidence items, hypotheses, scenarios, scores and audit
# entries are deliberately NOT touched.
FUSION_DERIVED_MODELS = (
    Person,
    Object,
    Location,
    Event,
    EntityRelationship,
    Entity,
    Fact,
    Finding,
    TimelineEvent,
    ForensicAnchor,
    Constraint,
    Conflict,
)


class AnalyzeCaseWorkflow:
    """The full evidence-constrained analysis run for one case.

    Never determines what happened: it extracts evidence, builds the
    knowledge graph, retrieves similar cases as references and runs the
    reasoning loop that scores candidate scenarios for evidence consistency.
    """

    name = "AnalyzeCase"

    def __init__(self, uow: UnitOfWork, job_id: str = "") -> None:
        self.uow = uow
        self.ctx = AnalysisContext(case_id="", job_id=job_id)

    def _note_providers(self) -> None:
        """Record the adapters actually obtained for this run.

        Derived from live factory calls (not the config file) so a run forced
        through mock_providers() reports the mock instances it really used.
        """
        for capability, provider in (
            ("text", get_llm_provider()),
            ("embeddings", get_embedding_provider()),
            ("vision", get_vision_provider()),
            ("video_understanding", get_video_understanding_provider()),
            ("video_generation", get_video_provider()),
        ):
            label = getattr(provider, "label", "") or provider.name
            self.ctx.note_provider(capability, label, bool(getattr(provider, "is_mock", False)))

    def _purge_fusion_outputs(self, db: Session, case_id: str) -> None:
        """Delete previously fused graph rows for this case (no-op on a first run)."""
        for model in FUSION_DERIVED_MODELS:
            for row in db.query(model).filter_by(case_id=case_id).all():
                db.delete(row)
        db.flush()

    def run(self, case_id: str) -> dict[str, Any]:
        uow = self.uow
        db = uow.session
        ctx = self.ctx
        ctx.case_id = case_id

        case = db.get(Case, case_id)
        if case is None:
            raise ValueError("case not found")
        self._note_providers()

        logger.info(
            "run=%s case=%s job=%s prompt_version=%s starting AnalyzeCase",
            ctx.run_id,
            case_id,
            ctx.job_id or "-",
            ctx.prompt_version,
        )

        uow.case_status.set_status(case_id, "ANALYZING")
        evidence_count = db.query(EvidenceItem).filter_by(case_id=case_id).count()
        uow.flush()

        total_steps = evidence_count + 3
        step = 0

        def next_step(label: str) -> None:
            nonlocal step
            step += 1
            uow.job.set_progress(int(step / max(total_steps, 1) * 100), label)

        extractor = ExtractEvidenceWorkflow(uow, ctx, progress=next_step)
        with ctx.stage("extraction"):
            extractions = extractor.extract_all(case_id)

        self._purge_fusion_outputs(db, case_id)
        extractor.fuse(case_id, extractions)

        with ctx.stage("similar_case_retrieval"):
            next_step("Retrieving similar documented cases")
            similar = retrieve_similar_cases(db, case_id)
            uow.audit.record(
                case_id,
                action="similar_case_retrieval",
                agent="SimilarCaseRetrieval",
                provider="deterministic",
                summary=f"Retrieved {len(similar)} similar cases as investigative reference material (not proof)",
                extra={"run_id": ctx.run_id, "prompt_version": ctx.prompt_version},
            )

        with ctx.stage("reasoning"):
            next_step("Running iterative reasoning")
            reasoning_result = ReasoningEngine().run(db, case_id)

        uow.case_status.set_status(case_id, "ANALYZED")

        counts = {
            "evidence_extracted": len(extractions),
            "hypotheses_generated": reasoning_result.total_generated,
            "surviving_scenarios": reasoning_result.surviving,
            "rejected_scenarios": reasoning_result.rejected,
            "merged_scenarios": reasoning_result.merged,
            "iterations": reasoning_result.iterations,
            "similar_cases_retrieved": len(similar),
            "stopped_reason": reasoning_result.stopped_reason,
        }

        uow.audit.record(
            case_id,
            action="case_analyzed",
            agent="AnalyzeCaseWorkflow",
            summary=(
                f"Generated {counts['hypotheses_generated']} hypotheses, "
                f"{counts['surviving_scenarios']} surviving, "
                f"{counts['rejected_scenarios']} rejected, {counts['merged_scenarios']} merged, "
                f"{counts['iterations']} iterations"
            ),
            extra={"run_id": ctx.run_id, "prompt_version": ctx.prompt_version, "providers": ctx.providers},
        )

        evidence_rows = db.query(EvidenceItem).filter_by(case_id=case_id).all()
        manifest_path = write_manifest(
            case_id,
            "analysis",
            {
                **ctx.snapshot(),
                "evidence": [
                    {
                        "evidence_id": ev.evidence_id,
                        "item_type": ev.item_type,
                        "content_hash": ev.content_hash,
                        "status": ev.status,
                    }
                    for ev in evidence_rows
                ],
                "counts": counts,
            },
        )

        logger.info(
            "run=%s case=%s finished: %s surviving, %s rejected (manifest=%s)",
            ctx.run_id,
            case_id,
            counts["surviving_scenarios"],
            counts["rejected_scenarios"],
            manifest_path,
        )

        uow.flush()
        return {"status": "ANALYZED", **counts, "run_id": ctx.run_id, "manifest": manifest_path}
