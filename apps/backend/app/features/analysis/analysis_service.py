from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.features.evidence.extract import get_extractor_agent
from app.features.evidence.fusion import EvidenceFusionAgent
from app.models import AuditEvent, Case, EvidenceItem, Job
from app.features.analysis.reasoning.engine import ReasoningEngine
from app.features.analysis.retrieval.similar_cases import retrieve_similar_cases


class AnalysisService:
    def __init__(self) -> None:
        self.fusion = EvidenceFusionAgent()
        self.reasoning = ReasoningEngine()

    def analyze_case(self, db: Session, case_id: str, job: Job | None = None) -> dict[str, Any]:
        case = db.get(Case, case_id)
        if not case:
            raise ValueError("case not found")
        case.status = "ANALYZING"
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
                from app.features.evidence.extract import _extract_text_from_file

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