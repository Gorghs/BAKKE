from __future__ import annotations

from typing import Any

import numpy as np

from app.models import (
    Case,
    EvidenceItem,
    Fact,
    ForensicAnchor,
    ReferenceCase,
    SimilarCase,
)
from app.infrastructure.providers.embeddings import get_embedding_provider
from app.features.analysis.reasoning_agent import InvestigativeReasoningAgent

REFERENCE_ONLY = "investigative_reference_only"


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _case_profile(case_id: str, facts: list[Fact], anchors: list[ForensicAnchor]) -> str:
    parts = []
    for a in anchors:
        v = a.value or {}
        if a.type == "INJURY_LOCATION":
            parts.append(f"injury location {v.get('location', '')}")
    for f in facts:
        parts.append(f.statement)
    return " ".join(parts)


def retrieve_similar_cases(db, case_id: str, top_k: int = 5) -> list[SimilarCase]:
    """Multi-signal retrieval: semantic + forensic/timeline/object pattern overlap.

    Retrieved cases are analogical references ONLY, never proof.
    """
    provider = get_embedding_provider()
    facts = db.query(Fact).filter_by(case_id=case_id).all()
    anchors = db.query(ForensicAnchor).filter_by(case_id=case_id).all()
    evidence = db.query(EvidenceItem).filter_by(case_id=case_id).all()

    profile = _case_profile(case_id, facts, anchors)
    if not profile.strip():
        return []
    query_emb = provider.embed([profile])[0]

    case_injury = {(a.value or {}).get("location", "").lower() for a in anchors if a.type == "INJURY_LOCATION"}
    case_objects = set()
    for e in evidence:
        case_objects.add(e.item_type.lower())
    case_blind = any(
        f.extra.get("camera_coverage") == "NO_COVERAGE" for f in facts
    )

    references = db.query(ReferenceCase).all()
    if not references:
        return []

    candidates: list[tuple[float, ReferenceCase, list[str]]] = []
    for ref in references:
        score = _cosine(query_emb, ref.embedding or [])
        patterns: list[str] = []
        if ref.injury_pattern and case_injury:
            overlap = case_injury.intersection({p.lower() for p in ref.injury_pattern})
            if overlap:
                score += 0.2
                patterns.append("similar injury pattern")
        if case_blind and ref.evidence_gap_pattern:
            score += 0.15
            patterns.append("blind camera area")
        if ref.timeline_pattern:
            score += 0.1
            patterns.append("similar timeline")
        if ref.weapon_pattern:
            score += 0.1
            patterns.append("similar weapon/object pattern")
        candidates.append((score, ref, patterns))

    candidates.sort(key=lambda c: c[0], reverse=True)
    results: list[SimilarCase] = []
    for score, ref, patterns in candidates[:top_k]:
        sim = SimilarCase(
            case_id=case_id,
            reference_id=ref.id,
            reference_label=ref.reference_id,
            title=ref.title,
            similarity=round(max(0.0, min(1.0, score)), 3),
            relevant_patterns=patterns,
            relevance=REFERENCE_ONLY,
            extra={
                "conclusion": ref.conclusion,
                "description": ref.description,
                "summary": ref.summary,
                "event_sequence": ref.event_sequence,
            },
        )
        db.add(sim)
        results.append(sim)
    return results