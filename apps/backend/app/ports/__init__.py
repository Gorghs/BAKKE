"""Provider-independent ports (interfaces).

The domain and workflow layers depend only on these Protocols. Concrete
implementations live behind ``app.adapters`` — adding a new provider means
writing an adapter, never modifying core application code.
"""
from __future__ import annotations

from app.ports.embeddings import EmbeddingsPort
from app.ports.llm import LLMPort
from app.ports.repositories import (
    AuditPort,
    CaseStatusPort,
    EvidenceStatusPort,
    JobPort,
    UnitOfWork,
)
from app.ports.speech import SpeechToTextPort
from app.ports.storage import StoragePort
from app.ports.video import VideoGenerationPort, VideoUnderstandingPort
from app.ports.vision import VisionPort

__all__ = [
    "AuditPort",
    "CaseStatusPort",
    "EmbeddingsPort",
    "EvidenceStatusPort",
    "JobPort",
    "LLMPort",
    "SpeechToTextPort",
    "StoragePort",
    "UnitOfWork",
    "VideoGenerationPort",
    "VideoUnderstandingPort",
    "VisionPort",
]
