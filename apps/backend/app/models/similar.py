from __future__ import annotations

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class ReferenceCase(Base, TimestampMixin):
    """Library of documented solved cases used as analogical reference material."""

    __tablename__ = "reference_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    reference_id: Mapped[str] = mapped_column(String(32), unique=True)  # SC-001
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4000), default="")
    summary: Mapped[str] = mapped_column(String(6000), default="")
    injury_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    weapon_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    timeline_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    spatial_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    witness_conflict_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    evidence_gap_pattern: Mapped[list] = mapped_column(JsonType, default=list)
    event_sequence: Mapped[list] = mapped_column(JsonType, default=list)
    conclusion: Mapped[str] = mapped_column(String(2000), default="")
    embedding: Mapped[list] = mapped_column(JsonType, default=list)  # float[]
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class SimilarCase(Base, TimestampMixin):
    """Retrieved similar-case reference linked to the current case."""

    __tablename__ = "similar_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    reference_id: Mapped[str] = mapped_column(String(64), ForeignKey("reference_cases.id"))
    reference_label: Mapped[str] = mapped_column(String(32))  # SC-018
    title: Mapped[str] = mapped_column(String(300), default="")
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    relevant_patterns: Mapped[list] = mapped_column(JsonType, default=list)
    relevance: Mapped[str] = mapped_column(String(60), default="investigative_reference_only")
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)