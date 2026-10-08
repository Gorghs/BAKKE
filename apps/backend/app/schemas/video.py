from __future__ import annotations

from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class VideoShotOut(ORMModel):
    id: str
    spec_id: str
    shot_index: int
    duration_seconds: float
    description: str
    prompt_fragment: str
    status: str


class VideoSpecOut(ORMModel):
    id: str
    scenario_id: str
    case_id: str
    status: str
    spec: dict[str, Any] = {}
    visual_prompt: str
    shots: list[VideoShotOut] = []


class VideoOut(ORMModel):
    id: str
    scenario_id: str
    case_id: str
    provider: str
    model: str
    status: str
    duration_seconds: float
    width: int
    height: int
    format: str
    label_text: str
    validation: dict[str, Any] = {}
    is_mock: bool
    error: str
    created_at: datetime
    stream_url: str = ""