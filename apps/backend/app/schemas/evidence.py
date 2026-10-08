from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.schemas.common import ORMModel


class EvidenceUpload(BaseModel):
    item_type: str  # TEXT/AUDIO/IMAGE/VIDEO/FORENSIC_REPORT/POST_MORTEM_REPORT/INVESTIGATOR_REPORT/WITNESS_STATEMENT/PHYSICAL_EVIDENCE/LOCATION_RECORD/DIGITAL_RECORD/OTHER
    title: str = ""
    description: str = ""
    raw_text: str = ""  # used for TEXT-typed evidence without a file


class EvidenceOut(ORMModel):
    id: str
    case_id: str
    evidence_id: str
    item_type: str
    title: str
    description: str
    original_filename: str
    mime_type: str
    size_bytes: int
    content_hash: str
    status: str
    extracted: bool
    raw_text: str = ""
    extra: dict[str, Any] = {}
    provider_label: str = ""
    created_at: datetime


class FactOut(ORMModel):
    id: str
    case_id: str
    fact_id: str
    statement: str
    status: str
    constraint_strength: str
    source_type: str
    category: str
    qualifier: str
    source_evidence_ids: list[str] = []
    source_refs: list[dict[str, Any]] = []
    is_authoritative: bool
    extra: dict[str, Any] = {}


class FactSourceOut(BaseModel):
    evidence_id: str
    title: str
    item_type: str
    page: Optional[int] = None
    section: str = ""
    paragraph_index: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    timestamp_seconds: Optional[float] = None
    frame: Optional[int] = None
    speaker: str = ""
    note: str = ""


class FactWithSources(FactOut):
    sources: list[FactSourceOut] = []


class EntityOut(ORMModel):
    id: str
    case_id: str
    entity_id: str
    name: str
    entity_type: str
    canonical_name: str
    description: str
    extra: dict[str, Any] = {}


class RelationshipOut(ORMModel):
    id: str
    case_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    evidence_links: list[str] = []
    extra: dict[str, Any] = {}


class FindingOut(ORMModel):
    id: str
    case_id: str
    finding_id: str
    category: str
    title: str
    summary: str
    details: dict[str, Any] = {}
    status: str
    strength: str
    source_evidence_ids: list[str] = []


class TimelineEventOut(ORMModel):
    id: str
    case_id: str
    event_id: str
    title: str
    description: str
    time_type: str
    time_start: str
    time_end: str
    time_label: str
    certainty: str
    ordering_index: int
    linked_fact_ids: list[str] = []
    source_evidence_ids: list[str] = []
    location_entity_id: str
    participants: list[str] = []
    extra: dict[str, Any] = {}


class ConstraintOut(ORMModel):
    id: str
    case_id: str
    constraint_id: str
    constraint_type: str
    strength: str
    description: str
    expression: dict[str, Any] = {}
    anchor_id: str
    source_evidence_ids: list[str] = []


class AnchorOut(ORMModel):
    id: str
    case_id: str
    anchor_id: str
    type: str
    value: dict[str, Any] = {}
    normalized: str
    source_evidence_ids: list[str] = []
    strength: str


class ConflictOut(ORMModel):
    id: str
    case_id: str
    conflict_id: str
    description: str
    subject: str
    sides: list[dict[str, Any]] = []
    status: str