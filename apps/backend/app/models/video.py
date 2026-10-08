from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JsonType, TimestampMixin, gen_uuid


class VideoScenarioSpec(Base, TimestampMixin):
    """3D animation specification for one validated scenario.

    The spec is a *visual-only* production document. It is derived from the
    scenario and does not contain forensic reasoning, evidence IDs, or the
    case reports.
    """

    __tablename__ = "video_scenario_specs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenarios.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")  # DRAFT/DIRECTING/COMPLETE
    spec: Mapped[dict] = mapped_column(JsonType, default=dict)
    visual_prompt: Mapped[str] = mapped_column(String, default="")
    extra: Mapped[dict] = mapped_column(JsonType, default=dict)


class VideoShot(Base, TimestampMixin):
    __tablename__ = "video_shots"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    spec_id: Mapped[str] = mapped_column(String(64), ForeignKey("video_scenario_specs.id"), index=True)
    shot_index: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float] = mapped_column(Float, default=4.0)
    description: Mapped[str] = mapped_column(String(2000), default="")
    prompt_fragment: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")


class GeneratedVideo(Base, TimestampMixin):
    __tablename__ = "generated_videos"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=gen_uuid)
    scenario_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenarios.id"), index=True)
    spec_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("video_scenario_specs.id"), index=True, nullable=True)
    case_id: Mapped[str] = mapped_column(String(64), ForeignKey("cases.id"), index=True)
    provider: Mapped[str] = mapped_column(String(60), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    # PENDING/GENERATING/READY/FAILED/INVALID
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    video_path: Mapped[str] = mapped_column(String(1000), default="")
    thumbnail_path: Mapped[str] = mapped_column(String(1000), default="")
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    format: Mapped[str] = mapped_column(String(20), default="mp4")
    label_text: Mapped[str] = mapped_column(String(500), default="")
    prompt_used: Mapped[str] = mapped_column(String, default="")
    validation: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str] = mapped_column(String(2000), default="")
    is_mock: Mapped[bool] = mapped_column(default=False)