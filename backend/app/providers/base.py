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
        "Rewrite a visual-only video generation prompt into a richer cinematic brief for a "
        "text-to-video model. Expand terse directions with setting, surface, light, "
        "atmosphere, camera and motion detail, and keep an explicit time range for every "
        "shot. Keep every constraint, the shot order and the exact NOT RECORDED FOOTAGE "
        "label. Add no facts, no evidence, no reasoning, no people, no new objects and no "
        "actions the source does not already state."
    ),
    "build_visual_brief": (
        "Reduce a validated scenario to what a camera can show: the actors, the objects with "
        "their start and end states, the actions in the order they happen, and what stays "
        "continuous. Copy the wording of the input for every actor name, object name and action "
        "verb; a name or an action the input does not state is an invention and is rejected. An "
        "absence (no vehicle entered) is not an action: it belongs in absences, never in beats. "
        "Add no evidence, witness, score or reasoning text."
    ),
}


def _schema(model: type) -> str:
    return json.dumps(model.model_json_schema(), separators=(",", ":"))


# Extraction runs on a tight output budget. The route that carries the demo
# (Groq free tier, qwen/qwen3.8-27b) caps output at 1000 tokens per minute, so a
# live completion is cut at ~900-1400 tokens and the section written last is the
# section that is lost. Observed live: a 900-token completion spent itself on 6
# facts and stopped before findings, entities and timeline_events; a 1400-token
# completion wrote 10 facts and stopped in the same place. Raising the budget is
# not available (1800 was refused 429), so the prompt has to make the budget fit.
#
# Two changes do that. The schema names only the keys the pipeline reads, and it
# no longer advertises a per-fact `metadata` block: `spatial` needs a real person,
# place and time (the spatio-temporal constraint check reads it) and
# `camera_coverage` needs a real coverage source (the unknown-area counter and
# similar-case retrieval read it), but asking per fact made the model stamp
# fabricated defaults on every row ("time": "00:00", camera_coverage on every
# fact, including facts about paperwork). Both keys stay in the contract and are
# filled by the mock and by an explicit note in the system prompt instead.
_EXTRACT_SCHEMA = {
    "facts": [
        {
            "statement": "one sentence",
            "status": "HARD|BOUNDED|INFERRED|SOFT|CONTESTED|UNKNOWN",
            "constraint_strength": "HARD|SOFT|NONE",
            "category": "WHAT|WHEN|WHERE|WHO|HOW|GENERAL",
            "source_evidence_ids": ["E-001"],
            "source_refs": [{"evidence_id": "E-001"}],
        }
    ],
    "findings": [
        {
            "category": "FORENSIC|POST_MORTEM|INVESTIGATOR|WITNESS",
            "title": "",
            "summary": "",
            "details": {},
            "strength": "HARD|SOFT",
            "source_evidence_ids": ["E-001"],
        }
    ],
    "entities": [
        {
            "name": "",
            "entity_type": "PERSON|OBJECT|LOCATION|EVENT",
            "description": "",
        }
    ],
    "timeline_events": [
        {
            "title": "",
            "description": "",
            "time_type": "EXACT|APPROXIMATE|UNKNOWN",
            "time_start": "HH:MM",
            "time_end": "",
            "certainty": "KNOWN|BOUNDED",
            "linked_fact_ids": ["F-001"],
            "source_evidence_ids": ["E-001"],
        }
    ],
}

# Facts a single text may yield. The pipeline wants the fact list, but the list is
# what the model writes first and it writes it without a bound, so on a tight
# budget the list grows until the budget is gone and the later sections are lost.
# A text that names a dozen times still fits: the cap counts facts, and a
# timeline event is built per time, not per fact.
MAX_FACTS_PER_ITEM = 12


# Candidate explanations one hypothesis call may return. Same budget problem as
# the fact list: the model writes a long hypothesis per candidate and no bound,
# so the JSON runs past the output budget and the call ends on a cut (observed
# live: 3038 chars written, finish_reason=length, every attempt the same). A
# hypothesis carries far more than a fact (title, summary, cause_claim, events),
# so the count that fits is smaller than the fact count.
MAX_HYPOTHESES_PER_CALL = 8


# Output contract per task, embedded in real providers' prompts. The mock
# provider ignores this (rule-based output already matches); a real model
# guesses the structure without it and the caller's model_validate fails
# (observed live: facts returned as plain strings, `timeline` vs
# `timeline_events`). Every LLM_TASKS entry needs a schema here.
TASK_RESPONSE_SCHEMAS: dict[str, str] = {
    "extract_evidence": json.dumps(_EXTRACT_SCHEMA, separators=(",", ":")),
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
    "build_visual_brief": json.dumps(
        {
            "setting": "the yard and the store door",
            "actors": [{"label": "Unknown person", "appearance": "", "clothing": ""}],
            "props": [
                {
                    "label": "padlock",
                    "start_state": "present",
                    "end_state": "missing",
                    "location": "store door",
                }
            ],
            "beats": [{"clock": "19:12", "actor": "Unknown person", "action": "entered the yard"}],
            "continuity": ["the space stays empty apart from the figure and the object"],
            "absences": ["vehicle"],
        },
        separators=(",", ":"),
    ),
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