from __future__ import annotations

import json
import re
import time
from typing import Any

from app.config import get_settings
from app.providers.base import LLM_TASKS, TASK_CONTRACT_MODELS, TASK_RESPONSE_SCHEMAS
from app.providers import rule_based


_last_call_started_at: float | None = None


def _pace() -> None:
    """Space upstream attempts apart when LLM_CALL_MIN_INTERVAL is set."""
    global _last_call_started_at
    interval = get_settings().LLM_CALL_MIN_INTERVAL
    now = time.monotonic()
    if interval > 0 and _last_call_started_at is not None:
        wait = interval - (now - _last_call_started_at)
        if wait > 0:
            time.sleep(wait)
            now = time.monotonic()
    _last_call_started_at = now


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

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "") -> None:
        from openai import OpenAI

        s = get_settings()
        self.api_key = api_key or s.OPENAI_API_KEY
        self.model = model or s.OPENAI_MODEL
        # Free-tier endpoints answer 429 with retry-after; ride those out
        # instead of failing a whole job attempt on the first rate limit.
        # Account-level limits (Gemini web BardErrorInfo 13 1155) punish bursts,
        # so the retry budget and inter-call pacing are both configurable.
        self.client = OpenAI(api_key=self.api_key, base_url=base_url or None, max_retries=s.LLM_MAX_RETRIES)
        # 0 leaves max_tokens unset. Endpoints that cap output tokens per minute
        # refuse a request whose expected output they think is larger than the
        # cap, and an unset max_tokens reads as their 2048 default.
        self.max_output_tokens = int(s.LLM_MAX_OUTPUT_TOKENS)

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
        schema = TASK_RESPONSE_SCHEMAS.get(task, "")
        schema_line = f"\nOutput JSON schema (return exactly these keys):\n{schema}" if schema else ""
        return f"{base}\nTask: {task_desc}\nReturn ONLY valid JSON matching this exact output schema.{schema_line}"

    # 1 try + 2 corrective re-calls. Every real-provider failure seen live fits
    # one of three buckets: transient 400 `json_validate_failed` (the SDK does
    # not retry 400s), output that will not parse, output that fails the
    # contract. All three are one re-call away from recovery.
    MAX_GENERATION_ATTEMPTS = 3

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        from openai import BadRequestError
        from pydantic import ValidationError

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt(task)},
            {"role": "user", "content": f"Input data:\n{json.dumps(payload, default=str)}"},
        ]
        contract = TASK_CONTRACT_MODELS.get(task)
        last_error = "no attempts made"
        request: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        if self.max_output_tokens > 0:
            request["max_tokens"] = self.max_output_tokens
        for attempt in range(self.MAX_GENERATION_ATTEMPTS):
            _pace()
            try:
                resp = self.client.chat.completions.create(**request)
            except BadRequestError as exc:
                # Transient generation fault: no output to show the model, so
                # re-call the identical messages.
                last_error = str(exc)[:300]
                continue
            text = resp.choices[0].message.content or "{}"
            try:
                data = _extract_json(text)
            except Exception as exc:
                last_error = f"unparseable output: {exc}"
                messages.append({"role": "assistant", "content": text[:4000]})
                messages.append({"role": "user", "content": "That output was not valid JSON. Reply again with valid JSON only."})
                continue
            if contract is None:
                return data
            try:
                return contract.model_validate(data).model_dump()
            except ValidationError as exc:
                last_error = str(exc)[:400]
                messages.append({"role": "assistant", "content": text[:6000]})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"That output failed schema validation:\n{last_error}\n"
                            "Fix it and reply with the corrected valid JSON only, same keys."
                        ),
                    }
                )
                continue
        raise ValueError(
            f"provider returned unusable output for task '{task}' "
            f"after {self.MAX_GENERATION_ATTEMPTS} attempts: {last_error}"
        )