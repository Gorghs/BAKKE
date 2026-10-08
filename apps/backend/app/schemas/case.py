from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    description: str = ""
    tags: list[str] = []


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class CaseOut(ORMModel):
    id: str
    owner_id: str
    name: str
    description: str
    status: str
    tags: list[str] = []
    evidence_count: int
    created_at: datetime
    updated_at: datetime


class CaseDashboard(BaseModel):
    case: CaseOut
    evidence_count: int
    analysis_status: str
    fact_count: int
    timeline_count: int
    constraint_count: int
    hard_constraint_count: int
    conflict_count: int
    unknown_area_count: int
    anchor_count: int
    scenario_survivor_count: int
    scenario_rejected_count: int
    top_scenarios: list[dict[str, Any]] = []
    similar_case_count: int
    video_count: int