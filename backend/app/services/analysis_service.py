from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.extract import get_extractor_agent
from app.agents.fusion import EvidenceFusionAgent
from app.models import (
    AuditEvent,
    Case,
    Conflict,
    Constraint,
    DiscriminatingEvidence,
    Entity,
    EntityRelationship,
    Event,
    EvidenceItem,
    EvidenceSource,
    Fact,
    Finding,
    ForensicAnchor,
    GeneratedVideo,
    Hypothesis,
    Job,
    Location,
    Object,
    Person,
    Scenario,
    ScenarioComparison,
    ScenarioEvent,
    ScenarioEvidenceLink,
    ScenarioScore,
    SimilarCase,
    TimelineEvent,
    VideoScenarioSpec,
    VideoShot,
)
from app.reasoning.engine import ReasoningEngine
from app.retrieval.similar_cases import retrieve_similar_cases


class AnalysisService:
    def __init__(self) -> None:
        self.fusion = EvidenceFusionAgent()
        self.reasoning = ReasoningEngine()

    def _clear_derived_state(self, db: Session, case_id: str) -> dict[str, int]:
        """Drop every analysis-derived row for the case before a re-run.

        Analysis must be replace-not-append: supervisor retries re-run the
        whole pipeline, and appending triple-fused the same evidence live
        (13 -> 38 facts), which alone pushed one request past the free-tier
        token cap. Evidence items, assets, jobs and audit events are inputs
        or logs and stay. Children are deleted before their parents because
        no FK declares ON DELETE CASCADE.
        """
        spec_ids = [r[0] for r in db.query(VideoScenarioSpec.id).filter_by(case_id=case_id)]
        scenario_ids = [r[0] for r in db.query(Scenario.id).filter_by(case_id=case_id)]
        counts: dict[str, int] = {}

        def wipe(key: str, query) -> None:
            n = query.delete(synchronize_session=False)
            if n:
                counts[key] = n

        wipe("generated_videos", db.query(GeneratedVideo).filter_by(case_id=case_id))
        if spec_ids:
            wipe("video_shots", db.query(VideoShot).filter(VideoShot.spec_id.in_(spec_ids)))
        wipe("video_specs", db.query(VideoScenarioSpec).filter_by(case_id=case_id))
        if scenario_ids:
            wipe("scenario_scores", db.query(ScenarioScore).filter(ScenarioScore.scenario_id.in_(scenario_ids)))
        wipe("scenario_events", db.query(ScenarioEvent).filter_by(case_id=case_id))
        wipe("scenario_evidence_links", db.query(ScenarioEvidenceLink).filter_by(case_id=case_id))
        wipe("scenario_comparisons", db.query(ScenarioComparison).filter_by(case_id=case_id))
        wipe("discriminating_evidence", db.query(DiscriminatingEvidence).filter_by(case_id=case_id))
        wipe("scenarios", db.query(Scenario).filter_by(case_id=case_id))
        wipe("hypotheses", db.query(Hypothesis).filter_by(case_id=case_id))
        wipe("similar_cases", db.query(SimilarCase).filter_by(case_id=case_id))
        wipe("evidence_sources", db.query(EvidenceSource).filter_by(case_id=case_id))
        wipe("conflicts", db.query(Conflict).filter_by(case_id=case_id))
        wipe("constraints", db.query(Constraint).filter_by(case_id=case_id))
        wipe("anchors", db.query(ForensicAnchor).filter_by(case_id=case_id))
        wipe("timeline", db.query(TimelineEvent).filter_by(case_id=case_id))
        wipe("findings", db.query(Finding).filter_by(case_id=case_id))
        wipe("relationships", db.query(EntityRelationship).filter_by(case_id=case_id))
        wipe("persons", db.query(Person).filter_by(case_id=case_id))
        wipe("objects", db.query(Object).filter_by(case_id=case_id))
        wipe("locations", db.query(Location).filter_by(case_id=case_id))
        wipe("events", db.query(Event).filter_by(case_id=case_id))
        wipe("facts", db.query(Fact).filter_by(case_id=case_id))
        wipe("entities", db.query(Entity).filter_by(case_id=case_id))
        db.flush()
        if counts:
            db.add(
                AuditEvent(
                    case_id=case_id,
                    action="analysis_state_cleared",
                    category="ANALYSIS",
                    agent="AnalysisService",
                    summary=f"Cleared prior derived state before re-analysis: {counts}",
                )
            )
            db.flush()
        return counts

    def analyze_case(self, db: Session, case_id: str, job: Job | None = None) -> dict[str, Any]:
        case = db.get(Case, case_id)
        if not case:
            raise ValueError("case not found")
        case.status = "ANALYZING"
        self._clear_derived_state(db, case_id)
        evidence_items = db.query(EvidenceItem).filter_by(case_id=case_id).all()
        db.flush()

        def _progress(step: int, total: int, label: str) -> None:
            if job:
                job.progress = int(step / max(total, 1) * 100)
                job.result = {"stage": label}
                db.flush()

        total_steps = len(evidence_items) + 3
        step = 0

        # ---- 1. Multimodal extraction ----
        extractions = []
        for ev in evidence_items:
            step += 1
            _progress(step, total_steps, f"Extracting evidence {ev.evidence_id}")
            agent = get_extractor_agent(ev.item_type)
            text = ev.raw_text
            if not text and ev.file_path:
                from app.agents.extract import _extract_text_from_file

                text = _extract_text_from_file(ev.file_path, ev.mime_type)
            try:
                result = agent.extract(evidence=ev, text=text)
            except Exception as exc:
                ev.status = "FAILED"
                ev.extra = {**ev.extra, "extraction_error": str(exc)[:500]}
                db.add(
                    AuditEvent(
                        case_id=case_id,
                        action="extraction_failed",
                        agent=agent.name,
                        summary=str(exc)[:400],
                    )
                )
                db.flush()
                continue
            ev.status = "PROCESSED"
            ev.extracted = True
            ev.provider_label = getattr(agent, "provider_label", "")
            db.flush()
            extractions.append((ev, result))

        # ---- 2. Fusion ----
        step += 1
        _progress(step, total_steps, "Fusing evidence into knowledge graph")
        context = self.fusion.run(db, case_id, extractions)

        # ---- 3. Similar-case retrieval ----
        step += 1
        _progress(step, total_steps, "Retrieving similar documented cases")
        similar = retrieve_similar_cases(db, case_id)
        db.add(
            AuditEvent(
                case_id=case_id,
                action="similar_case_retrieval",
                agent="SimilarCaseRetrieval",
                provider="deterministic",
                summary=f"Retrieved {len(similar)} similar cases as investigative reference material (not proof)",
            )
        )
        db.flush()

        # ---- 4. Investigative reasoning loop ----
        step += 1
        _progress(step, total_steps, "Running iterative reasoning")
        reasoning_result = self.reasoning.run(db, case_id)

        case.status = "ANALYZED"
        db.add(
            AuditEvent(
                case_id=case_id,
                action="case_analyzed",
                agent="AnalysisService",
                summary=(
                    f"Generated {reasoning_result.total_generated} hypotheses, "
                    f"{reasoning_result.surviving} surviving, "
                    f"{reasoning_result.rejected} rejected, {reasoning_result.merged} merged, "
                    f"{reasoning_result.iterations} iterations"
                ),
            )
        )
        db.flush()
        return {
            "status": "ANALYZED",
            "evidence_extracted": len(extractions),
            "hypotheses_generated": reasoning_result.total_generated,
            "surviving_scenarios": reasoning_result.surviving,
            "rejected_scenarios": reasoning_result.rejected,
            "merged_scenarios": reasoning_result.merged,
            "iterations": reasoning_result.iterations,
            "similar_cases_retrieved": len(similar),
            "stopped_reason": reasoning_result.stopped_reason,
        }