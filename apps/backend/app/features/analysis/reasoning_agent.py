from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.agents.base import BaseAgent
from app.infrastructure.agents.contracts import (
    CritiqueResult,
    ExpansionResult,
    HypothesisDraft,
    HypothesisSet,
    RevisionResult,
)
from app.models import Fact, ForensicAnchor, SimilarCase, TimelineEvent


def _fact_dict(f: Fact) -> dict[str, Any]:
    return {
        "fact_id": f.fact_id,
        "statement": f.statement,
        "status": f.status,
        "category": f.category,
        "constraint_strength": f.constraint_strength,
        "source_evidence_ids": f.source_evidence_ids,
        "metadata": f.extra,
    }


def _timeline_dict(t: TimelineEvent) -> dict[str, Any]:
    return {
        "event_id": t.event_id,
        "title": t.title,
        "description": t.description,
        "time_type": t.time_type,
        "time_start": t.time_start,
        "time_end": t.time_end,
        "certainty": t.certainty,
        "linked_fact_ids": t.linked_fact_ids,
        "source_evidence_ids": t.source_evidence_ids,
    }


def _anchor_dict(a: ForensicAnchor) -> dict[str, Any]:
    return {"anchor_id": a.anchor_id, "type": a.type, "value": a.value, "normalized": a.normalized, "source_evidence_ids": a.source_evidence_ids}


def _similar_dict(s: SimilarCase) -> dict[str, Any]:
    return {
        "reference_label": s.reference_label,
        "title": s.title,
        "similarity": s.similarity,
        "relevant_patterns": s.relevant_patterns,
        "conclusion": s.extra.get("conclusion", ""),
    }


class InvestigativeReasoningAgent(BaseAgent):
    """Generates candidate explanations and additional alternatives.

    Reasons broadly like an investigator but is NOT the final decision maker:
    it proposes; the validation loop, critic and constraints decide.
    """

    name = "InvestigativeReasoningAgent"

    def build_case_payload(self, db: Session, case_id: str) -> dict[str, Any]:
        facts = db.query(Fact).filter_by(case_id=case_id).all()
        timeline = db.query(TimelineEvent).filter_by(case_id=case_id).order_by(TimelineEvent.ordering_index).all()
        anchors = db.query(ForensicAnchor).filter_by(case_id=case_id).all()
        similar = db.query(SimilarCase).filter_by(case_id=case_id).order_by(SimilarCase.similarity.desc()).limit(5).all()
        return {
            "facts": [_fact_dict(f) for f in facts],
            "timeline": [_timeline_dict(t) for t in timeline],
            "anchors": [_anchor_dict(a) for a in anchors],
            "unknown_areas": [],
            "similar_cases": [_similar_dict(s) for s in similar],
        }

    def generate(self, payload: dict[str, Any], similar_case_patterns: list[str] | None = None) -> HypothesisSet:
        raw = self.run_task("generate_hypotheses", payload)
        return HypothesisSet.model_validate(raw)

    def expand(self, db: Session, case_id: str, rejected: dict[str, Any]) -> ExpansionResult:
        payload = {
            "rejected_scenario": rejected,
            "facts": [_fact_dict(f) for f in db.query(Fact).filter_by(case_id=case_id).all()],
            "timeline": [
                _timeline_dict(t)
                for t in db.query(TimelineEvent).filter_by(case_id=case_id).order_by(TimelineEvent.ordering_index).all()
            ],
        }
        raw = self.run_task("expand_alternatives", payload)
        return ExpansionResult.model_validate(raw)


class HypothesisCriticAgent(BaseAgent):
    """Adversarially attacks candidate scenarios. Does not rubber-stamp."""

    name = "HypothesisCriticAgent"

    def critique(self, scenario: dict[str, Any], anchors: list[dict[str, Any]], facts: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> CritiqueResult:
        payload = {
            "scenario": scenario,
            "anchors": anchors,
            "facts": facts,
            "timeline": timeline,
        }
        raw = self.run_task("critique", payload)
        return CritiqueResult.model_validate(raw)


class HypothesisRevisionAgent(BaseAgent):
    """Revises fixable scenarios; rejects when a hard fact would have to change."""

    name = "HypothesisRevisionAgent"

    def revise(self, scenario: dict[str, Any], issues: list[dict[str, Any]]) -> RevisionResult:
        payload = {"scenario": scenario, "issues": issues}
        raw = self.run_task("revise", payload)
        return RevisionResult.model_validate(raw)