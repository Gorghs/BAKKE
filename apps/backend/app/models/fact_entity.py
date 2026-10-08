from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class Fact(Base, TimestampMixin):
    __tablename__ = "facts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    fact_id: Mapped[str] = mapped_column(String(32))  # F-001
    statement: Mapped[str] = mapped_column(String(4000))
    # HARD | BOUNDED | INFERRED | SOFT | CONTESTED | UNKNOWN
    status: Mapped[str] = mapped_column(String(24), default="HARD")
    # HARD | SOFT | NONE
    constraint_strength: Mapped[str] = mapped_column(String(16), default="NONE")
    source_type: Mapped[str] = mapped_column(String(40), default="TEXT")
    # category: GENERAL/FORENSIC/POST_MORTEM/INVESTIGATOR/WITNESS/SPATIAL/TEMPORAL/OBJECT
    category: Mapped[str] = mapped_column(String(40), default="GENERAL")
    qualifier: Mapped[str] = mapped_column(String(60), default="")
    source_evidence_ids: Mapped[list] = mapped_column(JsonType, default=list)  # ["E-001"]
    source_refs: Mapped[list] = mapped_column(JsonType, default=list)  # [{evidence_id,page,...}]
    is_authoritative: Mapped[bool] = mapped_column(default=False)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(32))  # EN-001
    name: Mapped[str] = mapped_column(String(300))
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # PERSON/OBJECT/LOCATION/EVENT
    canonical_name: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(String(2000), default="")
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    role: Mapped[str] = mapped_column(String(60), default="")  # e.g. witness, victim, unknown
    description: Mapped[str] = mapped_column(String(2000), default="")


class Object(Base, TimestampMixin):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    category: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(String(2000), default="")


class Location(Base, TimestampMixin):
    __tablename__ = "locations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    description: Mapped[str] = mapped_column(String(2000), default="")
    # KNOWN_COVERED | NO_COVERAGE | UNKNOWN
    camera_coverage: Mapped[str] = mapped_column(String(24), default="UNKNOWN")


class Event(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(60), default="")
    summary: Mapped[str] = mapped_column(String(2000), default="")


class EntityRelationship(Base, TimestampMixin):
    __tablename__ = "entity_relationships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    source_entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    target_entity_id: Mapped[str] = mapped_column(String(64), ForeignKey("entities.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), index=True)
    evidence_links: Mapped[list] = mapped_column(JsonType, default=list)
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)
