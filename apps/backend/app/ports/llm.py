"""LLM / structured-reasoning port."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    """Provider-independent completion port for BAKKE reasoning tasks.

    Implementations receive a task name (see ``app.prompts`` for the task
    catalogue and versioned prompts) plus a JSON-safe payload and must return
    a JSON object. The returned object is validated against the task's typed
    schema before it reaches the domain layer.
    """

    name: str
    is_mock: bool
    label: str

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]: ...
