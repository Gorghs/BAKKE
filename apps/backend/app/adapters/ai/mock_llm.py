from __future__ import annotations

from typing import Any

from app.adapters.ai import rule_based
from app.prompts import LLM_TASKS, validate_task_output

# Explicit task -> rule-based implementation map. Every task in LLM_TASKS must
# be listed here; a missing entry (or missing function) raises ValueError
# instead of falling through to an unrelated mock.
_TASK_IMPLEMENTATIONS: dict[str, str] = {
    "extract_evidence": "mock_extract",
    "generate_hypotheses": "mock_generate_hypotheses",
    "critique": "mock_critique",
    "revise": "mock_revise",
    "expand_alternatives": "mock_expand_alternatives",
    "summarize_scenario": "mock_summarize",
    "similar_case_relevance": "mock_similar_case_relevance",
    "compare_scenarios": "mock_compare",
}


class MockLLMProvider:
    name = "mock-llm"
    is_mock = True
    label = "DEVELOPMENT MOCK"
    LABEL = "DEVELOPMENT MOCK"

    def __init__(self) -> None:
        self.label = self.LABEL

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task not in LLM_TASKS:
            raise ValueError(f"unknown task: {task}")
        fn_name = _TASK_IMPLEMENTATIONS.get(task)
        fn = getattr(rule_based, fn_name, None) if fn_name else None
        if not callable(fn):
            raise ValueError(f"no rule-based implementation for task {task}")
        return validate_task_output(task, fn(payload))

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "label": self.LABEL, "task": "structured rule-based"}
