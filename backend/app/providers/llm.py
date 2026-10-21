from __future__ import annotations

import json
import re
import time
from typing import Any

from app.config import get_settings
from app.providers.base import (
    LLM_TASKS,
    MAX_FACTS_PER_ITEM,
    TASK_CONTRACT_MODELS,
    TASK_RESPONSE_SCHEMAS,
)
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


# Keys the pipeline reads from an extraction. A provider that runs out of output
# budget leaves the section written last incomplete, so what survives the cut is
# the early sections. The extractor prompt now writes timeline_events first.
# Only extraction is salvaged this way: it is the one task whose long output
# cannot fit the budget, and the only one whose partial output is still usable.
_EXTRACTION_REQUIRED_KEYS = ("facts", "timeline_events")


def _maybe_complete_partial(contract: type, text: str) -> dict[str, Any] | None:
    """Return the validated partial when a cut completion is still usable.

    A completion cut at the output budget is a real partial answer, not noise. If
    it carries the sections the pipeline reads, the missing tail is the model's own
    omission and fusion covers it (facts that state a clock time still become
    timeline entries). Returning None sends the caller back for a compact rewrite
    instead.

    The cut lands mid-value, so the text usually ends in an unterminated array
    ("entities": [ or a half-written object). Repair the tail by removing the
    incomplete trailing element and closing the brackets that were opened.
    """
    data = _parse_truncated_json(text)
    if data is None:
        return None
    try:
        validated = contract.model_validate(data)
    except Exception:  # noqa: BLE001
        return None
    dumped = validated.model_dump()
    if all(dumped.get(key) for key in _EXTRACTION_REQUIRED_KEYS):
        return dumped
    return None


def _parse_truncated_json(text: str) -> dict[str, Any] | None:
    """Parse a JSON object whose tail was cut off mid-value."""
    body = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", body, re.DOTALL)
    if m:
        body = m.group(1).strip()
    start = body.find("{")
    if start == -1:
        return None
    # Try the whole object first: the cut may have landed right after a value.
    end = body.rfind("}")
    if end > start:
        try:
            parsed = json.loads(body[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    # Walk the text and remember the last position at which the object could be
    # closed cleanly (a complete value, outside a string). Cut there and close.
    depth = 0
    in_string = False
    escaped = False
    last_safe = -1
    for i, ch in enumerate(body[start:], start=start):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth == 0:
                last_safe = i
        elif ch == "," and depth >= 1:
            last_safe = i
    if last_safe == -1 or depth == 0:
        return None
    candidate = body[start:last_safe]
    # Close whatever brackets the cut left open.
    opens = candidate.count("[") - candidate.count("]")
    braces = candidate.count("{") - candidate.count("}")
    candidate += "}" * max(braces, 0) + "]" * max(opens, 0)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


# Sent back when a completion ran out of output budget and the partial was not
# usable (it did not carry both facts and timeline_events). The reply is not
# replayed to the model: keeping the oversized answer in context leaves the
# follow-up no room, so every attempt would end on the same cut.
TRUNCATION_REPAIR = (
    "Your reply was cut off by the output token budget, so everything after the cut is "
    "missing. Reply again with the complete JSON in the same schema, but compact: write at "
    "most 12 short one-sentence facts and put timeline_events and findings FIRST so a cut "
    "cannot lose them. Use one source_ref per fact at most and add no metadata block. "
    "Return every section the schema asks for. Build timeline_events from the times and "
    "ordered steps in the input. Do not drop a section because you ran out of room."
)


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
        elif task == "extract_evidence":
            base += (
                f"Write at most {MAX_FACTS_PER_ITEM} facts, one short sentence each, and only facts "
                "the text states. Do not pad the fact list. Then finish the other three sections: "
                "findings, entities, timeline_events. A timeline_events entry is required for every "
                "time or ordered step the text states, and the section is not optional even when the "
                "text has no clock times. Send the sections in this order: timeline_events first, "
                "then findings, then facts. Use one source_ref per fact at most. Do not add a "
                "metadata block; where the text states where a person was at a time, put it in the "
                "fact statement instead. "
            )
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
            if getattr(resp.choices[0], "finish_reason", None) == "length":
                # The provider cut the completion at the output budget. The partial
                # JSON still parses and validates because every missing list
                # defaults to [], so accepting it silently drops every section after
                # the cut (observed live: 5/5 items "extracted", 0 timeline events).
                #
                # The section order now puts timeline_events first, so a cut draft
                # usually already carries the section the old order lost (observed:
                # 3 facts + 4 timeline events, cut in entities). A partial that does
                # carry the sections the pipeline reads is a truthful partial result,
                # not a failure: fusion fills the rest from the facts. Only a
                # partial that is missing them is worth another call, and the
                # re-call cannot simply repeat the same request -- the earlier
                # oversized answer is still in context, so ask for the compact
                # rewrite with the reply dropped.
                if contract is not None:
                    partial = _maybe_complete_partial(contract, text)
                    if partial is not None:
                        return partial
                last_error = f"output cut off at the token budget after {len(text)} chars (finish_reason: length)"
                messages.append({"role": "user", "content": TRUNCATION_REPAIR})
                continue
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