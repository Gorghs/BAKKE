"""Domain layer: pure business rules and contracts.

No imports from SQLAlchemy models, HTTP, SDKs, Redis, or any adapter may
appear in this package (type-only imports behind ``TYPE_CHECKING`` are the
sole exception).
"""
from __future__ import annotations

from app.domain.constants import EVIDENCE_TYPES
from app.domain.contracts import (
    CritiqueIssue,
    CritiqueResult,
    EntityDraft,
    ExpansionResult,
    ExtractionResult,
    FactDraft,
    FindingDraft,
    HypothesisDraft,
    HypothesisSet,
    RevisionResult,
    ScenarioEventDraft,
    SourceRef,
    TimelineDraft,
)

__all__ = [
    "CritiqueIssue",
    "CritiqueResult",
    "EVIDENCE_TYPES",
    "EntityDraft",
    "ExpansionResult",
    "ExtractionResult",
    "FactDraft",
    "FindingDraft",
    "HypothesisDraft",
    "HypothesisSet",
    "RevisionResult",
    "ScenarioEventDraft",
    "SourceRef",
    "TimelineDraft",
]
