from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    evidence_id: str = ""
    page: Optional[int] = None
    section: str = ""
    paragraph_index: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    timestamp_seconds: Optional[float] = None
    frame: Optional[int] = None
    region: Optional[dict[str, Any]] = None
    speaker: str = ""
    note: str = ""


class FactDraft(BaseModel):
    statement: str
    status: str = "HARD"  # HARD/BOUNDED/INFERRED/SOFT/CONTESTED/UNKNOWN
    constraint_strength: str = "NONE"  # HARD/SOFT/NONE
    category: str = "GENERAL"
    qualifier: str = ""
    source_evidence_ids: list[str] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    is_authoritative: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class FindingDraft(BaseModel):
    category: str  # FORENSIC/POST_MORTEM/INVESTIGATOR/WITNESS
    title: str = ""
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)
    strength: str = "HARD"
    status: str = "SOURCE_REPORTED"
    source_evidence_ids: list[str] = Field(default_factory=list)


class EntityDraft(BaseModel):
    name: str
    entity_type: str  # PERSON/OBJECT/LOCATION/EVENT
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineDraft(BaseModel):
    title: str = ""
    description: str = ""
    time_type: str = "UNKNOWN"
    time_start: str = ""
    time_end: str = ""
    time_label: str = ""
    certainty: str = "KNOWN"
    ordering_index: int = 0
    linked_fact_ids: list[str] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    facts: list[FactDraft] = Field(default_factory=list)
    findings: list[FindingDraft] = Field(default_factory=list)
    entities: list[EntityDraft] = Field(default_factory=list)
    timeline_events: list[TimelineDraft] = Field(default_factory=list)
    provider: str = ""


class ScenarioEventDraft(BaseModel):
    description: str
    event_type: str = "HYPOTHESIZED"  # KNOWN/INFERRED/UNKNOWN/HYPOTHESIZED
    linked_fact_ids: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    timing: dict[str, Any] = Field(default_factory=dict)
    location: str = ""


class HypothesisDraft(BaseModel):
    title: str
    summary: str = ""
    cause_claim: str = ""
    participants: list[str] = Field(default_factory=list)
    events: list[ScenarioEventDraft] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    origin: str = "INITIAL"
    similar_case_patterns_used: list[str] = Field(default_factory=list)
    injury_location: str = ""


class HypothesisSet(BaseModel):
    hypotheses: list[HypothesisDraft] = Field(default_factory=list)
    provider: str = ""


class CritiqueIssue(BaseModel):
    type: str
    description: str
    severity: str = "SOFT"  # HARD/SOFT
    fixable: bool = False
    constraint: str = ""


class CritiqueResult(BaseModel):
    verdict: str  # PASS/FAIL
    issues: list[CritiqueIssue] = Field(default_factory=list)
    summary: str = ""
    provider: str = ""


class RevisionResult(BaseModel):
    reject: bool = False
    reason: str = ""
    revised: Optional[HypothesisDraft] = None
    provider: str = ""


class ExpansionResult(BaseModel):
    hypotheses: list[HypothesisDraft] = Field(default_factory=list)
    provider: str = ""