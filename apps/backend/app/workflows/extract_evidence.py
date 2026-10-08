"""ExtractEvidence workflow: multimodal extraction + fusion into the graph."""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.features.evidence.extract import _extract_text_from_file, get_extractor_agent
from app.features.evidence.fusion import EvidenceFusionAgent
from app.models import Case, EvidenceItem
from app.ports import UnitOfWork
from app.workflows.context import AnalysisContext

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str], None]


class ExtractEvidenceWorkflow:
    """Runs extraction over every evidence item and fuses the results.

    Standing alone it is the ``ExtractEvidence`` workflow; AnalyzeCase
    reuses its two stages so extraction behaves identically in both.
    """

    name = "ExtractEvidence"

    def __init__(self, uow: UnitOfWork, ctx: AnalysisContext, progress: ProgressFn | None = None) -> None:
        self.uow = uow
        self.ctx = ctx
        self._progress = progress

    def _notify(self, label: str) -> None:
        if self._progress is not None:
            self._progress(label)

    def extract_all(self, case_id: str) -> list[tuple[EvidenceItem, Any]]:
        db = self.uow.session
        evidence_items = db.query(EvidenceItem).filter_by(case_id=case_id).all()
        extractions: list[tuple[EvidenceItem, Any]] = []
        for ev in evidence_items:
            self._notify(f"Extracting evidence {ev.evidence_id}")
            agent = get_extractor_agent(ev.item_type)
            text = ev.raw_text
            if not text and ev.file_path:
                text = _extract_text_from_file(ev.file_path, ev.mime_type)
            try:
                with self.ctx.stage(f"extract:{ev.evidence_id}"):
                    result = agent.extract(evidence=ev, text=text)
            except Exception as exc:
                self.uow.evidence_status.mark_failed(ev.id, str(exc))
                self.uow.audit.record(
                    case_id,
                    action="extraction_failed",
                    agent=agent.name,
                    provider=self.ctx.providers.get("text", ""),
                    summary=str(exc)[:400],
                    input_object_ids=[ev.evidence_id],
                    extra={"run_id": self.ctx.run_id},
                )
                logger.warning(
                    "run=%s case=%s evidence=%s extraction failed: %s",
                    self.ctx.run_id,
                    case_id,
                    ev.evidence_id,
                    exc,
                )
                continue
            self.uow.evidence_status.mark_processed(ev.id, getattr(agent, "provider_label", ""))
            extractions.append((ev, result))
        return extractions

    def fuse(self, case_id: str, extractions: list[tuple[EvidenceItem, Any]]) -> Any:
        self._notify("Fusing evidence into knowledge graph")
        with self.ctx.stage("fusion"):
            return EvidenceFusionAgent().run(self.uow.session, case_id, extractions)

    def run(self, case_id: str) -> dict[str, Any]:
        db = self.uow.session
        case = db.get(Case, case_id)
        if case is None:
            raise ValueError("case not found")
        with self.ctx.stage("extraction"):
            extractions = self.extract_all(case_id)
        context = self.fuse(case_id, extractions)
        return {
            "evidence_extracted": len(extractions),
            "facts": len(getattr(context, "facts", []) or []),
            "timeline_events": len(getattr(context, "timeline_events", []) or []),
        }
