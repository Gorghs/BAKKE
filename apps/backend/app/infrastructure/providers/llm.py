from __future__ import annotations

import json
import re
from typing import Any

from app.config import get_settings
from app.infrastructure.providers.base import LLM_TASKS
from app.infrastructure.providers import rule_based


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # strip code fences
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    # find first balanced {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in response: {text[:300]}")
    return json.loads(text[start : end + 1])


class MockLLMProvider:
    name = "mock-llm"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK"

    def __init__(self) -> None:
        self.label = self.LABEL

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task not in LLM_TASKS:
            raise ValueError(f"unknown task: {task}")
        fn_name = f"mock_{task}"
        if not hasattr(rule_based, fn_name):
            fn_name = "mock_extract" if task == "extract_evidence" else fn_name
        if not hasattr(rule_based, fn_name):
            fn_name = "mock_compare" if task == "compare_scenarios" else fn_name
        fn = getattr(rule_based, fn_name)
        return fn(payload)

    def describe(self) -> dict[str, Any]:
        return {"provider": self.name, "label": self.LABEL, "task": "structured rule-based"}


class OpenAILLMProvider:
    name = "openai-llm"
    is_mock = False

    def __init__(self, api_key: str = "", model: str = "") -> None:
        from openai import OpenAI

        s = get_settings()
        self.api_key = api_key or s.OPENAI_API_KEY
        self.model = model or s.OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)

    def _system_prompt(self, task: str) -> str:
        base = (
            "You are BAKKE, an evidence-constrained investigative reasoning system. "
            "You do NOT determine what happened. You systematically explore explanations "
            "compatible with the available evidence, preserve uncertainty, and never assert guilt "
            "or claim that a scenario is what actually happened.\n\n"
        )
        task_desc = LLM_TASKS[task]
        if task == "generate_hypotheses":
            base += (
                "Generate as many materially distinct candidate explanations as the evidence and "
                "search space justify. Do not fabricate facts. Preserve authoritative forensic "
                "findings exactly. Use similar cases only as analogical references. "
            )
        elif task == "critique":
            base += (
                "Your job is to attack the candidate scenario. Actively search for contradictions, "
                "impossible movement, impossible timing, forensic conflicts, unsupported facts, "
                "hidden assumptions, witness conflicts and missing evidence. Do not agree with the "
                "generator. Return PASS only if no hard conflict remains. "
            )
        elif task == "revise":
            base += "Revise the scenario to fix fixable issues. Never modify a hard forensic finding to save a hypothesis. "
        return f"{base}\nTask: {task_desc}\nReturn ONLY valid JSON matching the requested schema."

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        import json

        content = json.dumps(payload, default=str)
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._system_prompt(task)},
                {"role": "user", "content": f"Input data:\n{content}"},
            ],
        )
        text = resp.choices[0].message.content or "{}"
        try:
            return _extract_json(text)
        except Exception:
            raise ValueError(f"invalid JSON from provider: {text[:300]}")