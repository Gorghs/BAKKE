from __future__ import annotations

import json
from typing import Any, Protocol

from app.agents.contracts import (
    CritiqueResult,
    ExpansionResult,
    ExtractionResult,
    HypothesisSet,
    RevisionResult,
)

# Task names used across the agent layer. Each task has a well-defined
# input payload and a structured output validated by the caller.
LLM_TASKS = {
    "extract_evidence": "Extract structured facts, findings, entities and timeline events from evidence text.",
    "generate_hypotheses": "Generate a diverse set of candidate explanations compatible with the evidence.",
    "critique": "Adversarially attack a candidate scenario.",
    "revise": "Revise a scenario to fix fixable issues.",
    "expand_alternatives": "Suggest new materially distinct candidates from a rejected scenario.",
    "summarize_scenario": "Produce a concise scenario summary.",
    "similar_case_relevance": "Identify relevant analogical patterns from retrieved similar cases.",
    "compare_scenarios": "Compare scenarios to surface shared and differing elements.",
    "expand_video_prompt": (
        "Rewrite a visual-only video generation prompt so it is compact and ready for a "
        "text-to-video model. Keep every constraint, the shot structure and the exact "
        "NOT RECORDED FOOTAGE label. Add no facts, no evidence, no reasoning, no people."
    ),
}


def _schema(model: type) -> str:
    return json.dumps(model.model_json_schema(), separators=(",", ":"))


# Output contract per task, embedded in real providers' prompts. The mock
# provider ignores this (rule-based output already matches); a real model
# guesses the structure without it and the caller's model_validate fails
# (observed live: facts returned as plain strings, `timeline` vs
# `timeline_events`). Every LLM_TASKS entry needs a schema here.
TASK_RESPONSE_SCHEMAS: dict[str, str] = {
    "extract_evidence": _schema(ExtractionResult),
    "generate_hypotheses": _schema(HypothesisSet),
    "expand_alternatives": _schema(ExpansionResult),
    "critique": _schema(CritiqueResult),
    "revise": _schema(RevisionResult),
    "summarize_scenario": json.dumps({"summary": "one-paragraph scenario summary"}),
    "similar_case_relevance": json.dumps(
        {"patterns": ["analogical pattern"], "note": "retrieved cases are references only"}
    ),
    "compare_scenarios": json.dumps(
        {
            "shared": ["element both scenarios agree on"],
            "differences": ["element that differs"],
            "discriminating": [{"pair": ["label A", "label B"], "note": "evidence that would tell them apart"}],
        }
    ),
    "expand_video_prompt": json.dumps({"prompt": "rewritten visual-only prompt"}),
}

# Tasks whose output has a Pydantic contract, used by real providers to
# validate their own generation and issue one corrective re-call before the
# caller's model_validate ever sees it (observed live: gpt-oss-20b returned
# `metadata` as a list and an entity as ""). Tasks with hand-written schemas
# above have no model class; their callers tolerate missing fields.
TASK_CONTRACT_MODELS: dict[str, type] = {
    "extract_evidence": ExtractionResult,
    "generate_hypotheses": HypothesisSet,
    "expand_alternatives": ExpansionResult,
    "critique": CritiqueResult,
    "revise": RevisionResult,
}


class LLMProvider(Protocol):
    name: str
    is_mock: bool

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class EmbeddingProvider(Protocol):
    name: str
    is_mock: bool

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class SpeechToTextProvider(Protocol):
    name: str
    is_mock: bool

    def transcribe(self, audio_path: str) -> str: ...


class VisionProvider(Protocol):
    name: str
    is_mock: bool

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]: ...


class VideoUnderstandingProvider(Protocol):
    name: str
    is_mock: bool

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]: ...


class VideoGenerationProvider(Protocol):
    name: str
    is_mock: bool

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]: ...


# Allowed evidence item types.
EVIDENCE_TYPES = [
    "TEXT",
    "AUDIO",
    "IMAGE",
    "VIDEO",
    "FORENSIC_REPORT",
    "POST_MORTEM_REPORT",
    "INVESTIGATOR_REPORT",
    "WITNESS_STATEMENT",
    "PHYSICAL_EVIDENCE",
    "LOCATION_RECORD",
    "DIGITAL_RECORD",
    "OTHER",
]