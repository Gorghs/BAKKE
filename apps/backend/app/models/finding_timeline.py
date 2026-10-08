from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class Finding(Base, TimestampMixin):
    """Unified structured finding from a specialized report agent.

    category selects the report type:
      FORENSIC / POST_MORTEM / INVESTIGATOR / WITNESS
    Findings explicitly reported in forensic or post-mortem reports become
    AUTHORITATIVE_SOURCE_FINDINGs and generate hard ForensicAnchors.
    """

    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    finding_id: Mapped[str] = mapped_column(String(32))  # FD-001
    category: Mapped[str] = mapped_column(String(32), index=True)  # FORENSIC/POST_MORTEM/INVESTIGATOR/WITNESS
    title: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(String(4000), default="")
    details: Mapped[dict] = mapped_column(JsonType, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="SOURCE_REPORTED")
    strength: Mapped[str] = mapped_column(String(16), default="HARD")
    source_evidence_ids: Mapped[list] = mapped_column(JsonType, default=list)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class TimelineEvent(Base, TimestampMixin):
    __tablename__ = "timeline_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(32))  # T-001
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(String(2000), default="")
    # EXACT | APPROXIMATE | INTERVAL | BEFORE | AFTER | UNKNOWN | CONTESTED
    time_type: Mapped[str] = mapped_column(String(24), default="UNKNOWN")
    time_start: Mapped[str] = mapped_column(String(60), default="")  # ISO or label like "20:10"
    time_end: Mapped[str] = mapped_column(String(60), default="")
    time_label: Mapped[str] = mapped_column(String(120), default="")
    # KNOWN | BOUNDED | INFERRED | CONTESTED | UNKNOWN
    certainty: Mapped[str] = mapped_column(String(24), default="KNOWN")
    ordering_index: Mapped[int] = mapped_column(default=0)
    linked_fact_ids: Mapped[list] = mapped_column(JsonType, default=list)  # ["F-001"]
    source_evidence_ids: Mapped[list] = mapped_column(JsonType, default=list)
    location_entity_id: Mapped[str] = mapped_column(String(64), default="")
    participants: Mapped[list] = mapped_column(JsonType, default=list)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class Constraint(Base, TimestampMixin):
    __tablename__ = "constraints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    constraint_id: Mapped[str] = mapped_column(String(32))  # C-001
    constraint_type: Mapped[str] = mapped_column(String(24))  # TEMPORAL/SPATIAL/PHYSICAL/FORENSIC/OBJECT/PERSON/WITNESS/EVIDENTIARY
    strength: Mapped[str] = mapped_column(String(16), default="HARD")
    description: Mapped[str] = mapped_column(String(2000), default="")
    expression: Mapped[dict] = mapped_column(JsonType, default=dict)
    anchor_id: Mapped[str] = mapped_column(String(64), default="")
    source_evidence_ids: Mapped[list] = mapped_column(JsonType, default=list)


class ForensicAnchor(Base, TimestampMixin):
    __tablename__ = "forensic_anchors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    anchor_id: Mapped[str] = mapped_column(String(32))  # FA-001
    type: Mapped[str] = mapped_column(String(40))  # INJURY_LOCATION/INJURY_MECHANISM/TOXICOLOGY/TIME_OF_DEATH/CAUSE_OF_DEATH/OTHER
    value: Mapped[dict] = mapped_column(JsonType, default=dict)
    normalized: Mapped[str] = mapped_column(String(500), default="")
    source_evidence_ids: Mapped[list] = mapped_column(JsonType, default=list)
    strength: Mapped[str] = mapped_column(String(16), default="HARD")


class Conflict(Base, TimestampMixin):
    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    conflict_id: Mapped[str] = mapped_column(String(32))  # CONFLICT-C-001
    description: Mapped[str] = mapped_column(String(2000), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    sides: Mapped[list] = mapped_column(JsonType, default=list)  # [{claim, evidence_ids}]
    status: Mapped[str] = mapped_column(String(24), default="OPEN")
