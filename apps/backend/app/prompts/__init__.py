"""Versioned prompts and typed task output validation.

Prompts are content-addressed by ``PROMPT_VERSION``. Every live provider
adapter builds its system prompt through :func:`system_prompt`, and every
provider response (live or mock) passes through :func:`validate_task_output`
before it reaches the domain layer.

Prompt files live in ``prompts/v1/*.md`` (one per task plus ``_base.md``,
the shared preamble). When a prompt changes incompatibly, add a new version
directory and bump ``PROMPT_VERSION``; recorded manifests store the version
so replay uses the same instructions.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain import contracts

PROMPT_VERSION = "v1"

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts" / PROMPT_VERSION

# Task catalogue: name -> one-line task description (shown to the model and
# used for provider capability reporting).
LLM_TASKS: dict[str, str] = {
    "extract_evidence": "Extract structured facts, findings, entities and timeline events from evidence text.",
    "generate_hypotheses": "Generate a diverse set of candidate explanations compatible with the evidence.",
    "critique": "Adversarially attack a candidate scenario.",
    "revise": "Revise a scenario to fix fixable issues.",
    "expand_alternatives": "Suggest new materially distinct candidates from a rejected scenario.",
    "summarize_scenario": "Produce a concise scenario summary.",
    "similar_case_relevance": "Identify relevant analogical patterns from retrieved similar cases.",
    "compare_scenarios": "Compare scenarios to surface shared and differing elements.",
}


class CompareScenariosOutput(BaseModel):
    """Permissive contract for ``compare_scenarios``.

    ``model_dump`` excludes unset fields so a provider is never credited with
    elements it did not return (no fabricated empty lists).
    """

    model_config = ConfigDict(extra="ignore")

    shared: list[str]
    differences: list[str]
    discriminating: list[dict[str, Any]] = Field(default_factory=list)
    note: str | None = None
    provider: str | None = None

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("exclude_unset", True)
        return super().model_dump(*args, **kwargs)


# Typed output contracts per task (validated for mock and live providers).
TASK_SCHEMAS: dict[str, type[Any]] = {
    "extract_evidence": contracts.ExtractionResult,
    "generate_hypotheses": contracts.HypothesisSet,
    "critique": contracts.CritiqueResult,
    "revise": contracts.RevisionResult,
    "expand_alternatives": contracts.ExpansionResult,
    "compare_scenarios": CompareScenariosOutput,
}


@lru_cache
def _read_prompt(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt '{name}' not found for version '{PROMPT_VERSION}' ({path})")
    return path.read_text(encoding="utf-8").strip()


def system_prompt(task: str) -> str:
    """Build the full system prompt for a task at the current version."""
    if task not in LLM_TASKS:
        raise ValueError(f"unknown task: {task}")
    parts = [_read_prompt("_base"), _read_prompt(task)]
    text = "\n\n".join(parts)
    text += f"\n\nTask: {LLM_TASKS[task]}\nReturn ONLY valid JSON matching the requested schema."
    schema = TASK_SCHEMAS.get(task)
    if schema is not None:
        text += "\n\nOutput JSON schema:\n" + json.dumps(schema.model_json_schema(), indent=2)
    return text


def validate_task_output(task: str, data: Any) -> dict[str, Any]:
    """Validate a provider response (mock or live) against the task contract.

    Raises ``ValueError`` on malformed output so failures are explicit and
    never silently degrade to empty results.
    """
    if not isinstance(data, dict):
        raise ValueError(f"task '{task}' returned {type(data).__name__}, expected a JSON object")
    schema = TASK_SCHEMAS.get(task)
    if schema is None:
        return data
    try:
        validated = schema.model_validate(data)
    except Exception as exc:
        raise ValueError(f"task '{task}' output failed contract validation: {exc}") from exc
    dump = validated.model_dump()
    # Hand back the caller's object when validation changed nothing.
    return data if dump == data else dump
