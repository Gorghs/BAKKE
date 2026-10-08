from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str


class AnalysisStatus(BaseModel):
    case_id: str
    status: str
    progress: int
    job_id: str = ""
    error: str = ""
    result: dict[str, Any] = {}


class AuditEventOut(ORMModel):
    id: str
    case_id: str
    action: str
    category: str
    actor_type: str
    actor_id: str
    agent: str
    provider: str
    model: str
    prompt_version: str
    input_object_ids: list[str] = []
    output_object_id: str
    summary: str
    status: str
    extra: dict[str, Any] = {}
    timestamp: str
    created_at: datetime


class JobOut(ORMModel):
    id: str
    case_id: str
    job_type: str
    status: str
    progress: int
    error: str
    result: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime