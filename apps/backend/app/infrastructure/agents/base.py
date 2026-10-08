from __future__ import annotations

from typing import Any, TypeVar, Generic

from app.config import get_settings
from app.adapters.providers import get_llm_provider

settings = get_settings()
T = TypeVar("T")


class AgentError(Exception):
    pass


class BaseAgent:
    """Common plumbing for all BAKKE agents.

    Agents are extraction and reasoning workers. They do NOT decide the truth
    of a case and they never assert guilt.
    """

    name = "base"

    def __init__(self) -> None:
        self.llm = get_llm_provider()
        self.provider_label = getattr(self.llm, "label", self.llm.name)

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.llm.run_task(task, payload)
        except Exception as exc:  # provider failure handling
            raise AgentError(f"{self.name}: provider '{self.llm.name}' failed on task '{task}': {exc}") from exc

    def describe(self) -> dict[str, Any]:
        return {
            "agent": self.name,
            "provider": self.llm.name,
            "provider_label": self.provider_label,
            "mock": bool(getattr(self.llm, "is_mock", False)),
        }