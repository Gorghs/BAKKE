from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SimilarCaseOut(ORMModel):
    id: str
    case_id: str
    reference_id: str
    reference_label: str
    title: str
    similarity: float
    relevant_patterns: list[str] = []
    relevance: str
    extra: dict[str, Any] = {}


class ReferenceCaseOut(ORMModel):
    id: str
    reference_id: str
    title: str
    description: str
    summary: str
    injury_pattern: list[str] = []
    weapon_pattern: list[str] = []
    timeline_pattern: list[str] = []
    spatial_pattern: list[str] = []
    witness_conflict_pattern: list[str] = []
    evidence_gap_pattern: list[str] = []
    event_sequence: list[str] = []
    conclusion: str


class ScenarioEventOut(ORMModel):
    id: str
    scenario_id: str
    event_order: int
    description: str
    event_type: str
    linked_fact_ids: list[str] = []
    evidence_links: list[str] = []
    timing: dict[str, Any] = {}
    location: str


class EvidenceLinkOut(ORMModel):
    id: str
    scenario_id: str
    evidence_item_id: str
    link_type: str
    rationale: str
    fact_ids: list[str] = []


class ScoreOut(ORMModel):
    id: str
    scenario_id: str
    total: int
    breakdown: dict[str, Any] = {}
    version: str


class ScenarioOut(ORMModel):
    id: str
    case_id: str
    hypothesis_id: str
    hypothesis_label: str = ""
    status: str
    summary: str
    cause_claim: str
    participants: list[str] = []
    rejection_reason: str = ""
    final_verdict: str = ""
    iteration_count: int
    is_survivor: bool
    score_total: int = 0
    score_breakdown: dict[str, Any] = {}
    supporting_evidence: list[str] = []
    contradicting_evidence: list[str] = []
    unknown_count: int = 0
    created_at: datetime


class ScenarioDetail(ScenarioOut):
    events: list[ScenarioEventOut] = []
    known: list[str] = []
    inferred: list[str] = []
    unknown: list[str] = []
    anchors_satisfied: list[str] = []
    similar_cases: list[dict[str, Any]] = []
    discriminating: list[dict[str, Any]] = []
    video: dict[str, Any] | None = None
    audit: list[dict[str, Any]] = []


class CompareRequest(BaseModel):
    scenario_ids: list[str] = []  # scenario UUIDs


class CompareResult(BaseModel):
    case_id: str
    scenarios: list[dict[str, Any]] = []
    shared: list[str] = []
    differences: list[str] = []
    discriminating: list[dict[str, Any]] = []