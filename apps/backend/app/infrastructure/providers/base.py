from __future__ import annotations

from typing import Any, Protocol

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