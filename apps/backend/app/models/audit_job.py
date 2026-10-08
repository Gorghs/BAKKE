from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class AuditEvent(Base, TimestampMixin):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    category: Mapped[str] = mapped_column(String(60), default="SYSTEM")
    actor_type: Mapped[str] = mapped_column(String(20), default="SYSTEM")  # SYSTEM/INVESTIGATOR
    actor_id: Mapped[str] = mapped_column(String(64), default="")
    agent: Mapped[str] = mapped_column(String(120), default="")
    provider: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    prompt_version: Mapped[str] = mapped_column(String(40), default="")
    input_object_ids: Mapped[list] = mapped_column(JsonType, default=list)
    output_object_id: Mapped[str] = mapped_column(String(64), default="")
    summary: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(24), default="OK")
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)
    timestamp: Mapped[str] = mapped_column(String(40), default="")  # ISO string for display


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(40), index=True)  # ANALYZE_CASE/GENERATE_VIDEO
    status: Mapped[str] = mapped_column(String(24), default="PENDING", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JsonType, default=dict)
    result: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str] = mapped_column(String(2000), default="")
    attempts: Mapped[int] = mapped_column(Integer, default=0)