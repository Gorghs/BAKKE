from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class EvidenceItem(Base, TimestampMixin):
    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_id: Mapped[str] = mapped_column(String(32))  # E-001
    item_type: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(String(4000), default="")
    file_path: Mapped[str] = mapped_column(String(1000), default="")
    original_filename: Mapped[str] = mapped_column(String(500), default="")
    mime_type: Mapped[str] = mapped_column(String(200), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(128), default="")
    status: Mapped[str] = mapped_column(String(40), default="UPLOADED")  # UPLOADED/PROCESSED/FAILED
    extracted: Mapped[bool] = mapped_column(default=False)
    raw_text: Mapped[str] = mapped_column(String, default="")  # for TEXT type items
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)
    provider_label: Mapped[str] = mapped_column(String(200), default="")  # which provider processed it


class EvidenceSource(Base, TimestampMixin):
    """Fine-grained provenance reference for an extracted fact."""

    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    fact_id: Mapped[str] = mapped_column(String(64), ForeignKey("facts.id"), index=True, nullable=True)
    page: Mapped[int] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(200), default="")
    paragraph_index: Mapped[int] = mapped_column(Integer, nullable=True)
    span_start: Mapped[int] = mapped_column(Integer, nullable=True)
    span_end: Mapped[int] = mapped_column(Integer, nullable=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    frame: Mapped[int] = mapped_column(Integer, nullable=True)
    region: Mapped[dict] = mapped_column(JsonType, nullable=True)  # image region
    speaker: Mapped[str] = mapped_column(String(200), default="")
    note: Mapped[str] = mapped_column(String(1000), default="")


class DocumentAsset(Base, TimestampMixin):
    __tablename__ = "document_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_text_path: Mapped[str] = mapped_column(String(1000), default="")


class AudioAsset(Base, TimestampMixin):
    __tablename__ = "audio_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    transcript: Mapped[str] = mapped_column(String, default="")
    speakers: Mapped[list] = mapped_column(JsonType, default=list)
    acoustic_events: Mapped[list] = mapped_column(JsonType, default=list)


class ImageAsset(Base, TimestampMixin):
    __tablename__ = "image_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    detected_objects: Mapped[list] = mapped_column(JsonType, default=list)
    exif: Mapped[dict] = mapped_column(JsonType, default=dict)


class VideoAsset(Base, TimestampMixin):
    __tablename__ = "video_assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    evidence_item_id: Mapped[str] = mapped_column(String(64), ForeignKey("evidence_items.id"), index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    scene_changes: Mapped[list] = mapped_column(JsonType, default=list)
    camera_metadata: Mapped[dict] = mapped_column(JsonType, default=dict)
