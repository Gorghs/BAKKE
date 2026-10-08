"""Explicit workflows: the named units of work BAKKE executes.

Workflows orchestrate ports and feature building blocks. Jobs are thin
dispatchers that construct a unit of work and call exactly one workflow:

    AnalyzeCase   — extraction -> fusion -> retrieval -> reasoning -> scores
    GenerateVideo — visual spec -> prompt (visual-only) -> render
    ExtractEvidence — multimodal extraction + fusion (standalone / replay)

No workflow imports an SDK, HTTP client, Redis, or FFmpeg directly.
"""
from __future__ import annotations

from app.workflows.analyze_case import AnalyzeCaseWorkflow
from app.workflows.context import AnalysisContext
from app.workflows.extract_evidence import ExtractEvidenceWorkflow
from app.workflows.generate_video import GenerateVideoWorkflow
from app.workflows.replay import load_manifest, replay_case

__all__ = [
    "AnalysisContext",
    "AnalyzeCaseWorkflow",
    "ExtractEvidenceWorkflow",
    "GenerateVideoWorkflow",
    "load_manifest",
    "replay_case",
]
