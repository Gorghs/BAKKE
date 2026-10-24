from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

import httpx

from app.config import ResolvedCapability, get_settings
from app.prompts import TASK_SCHEMAS, system_prompt, validate_task_output


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"no JSON object in response: {text[:300]}")
    return json.loads(text[start : end + 1])


# Statuses worth another attempt: the request was fine, the far side was not.
# 400 is deliberately absent — a rejected body is not transient.
_RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

# Ceiling for one backoff step. Free tiers often ask for 10-30s; anything
# longer than this turns a retry into a stalled job.
_MAX_BACKOFF_SECONDS = 30.0


_last_call_started_at: float | None = None
_pace_lock = threading.Lock()


def _pace() -> None:
    """Space consecutive upstream chat calls apart (LLM_CALL_MIN_INTERVAL).

    Token-per-minute limits are per account, so the wait has to be shared
    across threads: a worker pool that paces each thread separately still
    bursts. 0 disables pacing.
    """
    global _last_call_started_at
    interval = float(get_settings().LLM_CALL_MIN_INTERVAL or 0)
    with _pace_lock:
        now = time.monotonic()
        if interval > 0 and _last_call_started_at is not None:
            wait = interval - (now - _last_call_started_at)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
        _last_call_started_at = now


def _retry_delay(resp: httpx.Response | None, attempt: int) -> float:
    """Backoff for one retry: the server's own advice first, then exponential."""
    if resp is not None:
        raw = resp.headers.get("retry-after", "")
        if raw:
            try:
                return max(0.0, min(float(raw), _MAX_BACKOFF_SECONDS))
            except ValueError:
                pass
    return min(2.0 * (attempt + 1), _MAX_BACKOFF_SECONDS)


# ---------------------------------------------------------------------------
# Truncation repair
#
# A completion cut at the output budget is not noise: it is a real partial
# answer with the tail missing. Whether it is usable depends on which sections
# survived the cut, so the tasks whose sections the pipeline reads declare
# them. A partial that carries them is returned as it stands; anything else is
# re-called with a compact rewrite.
# ---------------------------------------------------------------------------

_TASK_OUTPUT_FLOOR: dict[str, int] = {"expand_video_prompt": 3200}
_TASK_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "extract_evidence": ("facts", "timeline_events"),
    "generate_hypotheses": ("hypotheses",),
    "expand_alternatives": ("hypotheses",),
}


def _parse_truncated_json(text: str) -> dict[str, Any] | None:
    """Parse a JSON object whose tail was cut off mid-value."""
    body = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", body, re.DOTALL)
    if m:
        body = m.group(1).strip()
    start = body.find("{")
    if start == -1:
        return None
    # The cut may have landed just after a complete value.
    end = body.rfind("}")
    if end > start:
        try:
            parsed = json.loads(body[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    # Walk the text and remember the last position where the object could be
    # closed cleanly (a complete value, outside a string). Cut there and close
    # whatever brackets the cut left open.
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
    opens = candidate.count("[") - candidate.count("]")
    braces = candidate.count("{") - candidate.count("}")
    candidate += "}" * max(braces, 0) + "]" * max(opens, 0)
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _maybe_complete_partial(task: str, text: str) -> dict[str, Any] | None:
    """Return the validated partial when a cut completion is still usable."""
    required = _TASK_REQUIRED_KEYS.get(task)
    contract = TASK_SCHEMAS.get(task)
    if not required or contract is None:
        return None
    data = _parse_truncated_json(text)
    if data is None:
        return None
    try:
        dumped = contract.model_validate(data).model_dump()
    except Exception:  # noqa: BLE001 - any contract failure means "not usable"
        return None
    if all(dumped.get(key) for key in required):
        return dumped
    return None


TRUNCATION_REPAIR = (
    "Your reply was cut off by the output token budget, so everything after the cut is "
    "missing. Reply again with the complete JSON in the same schema, but compact: write at "
    "most 12 short one-sentence facts and put timeline_events and findings FIRST so a cut "
    "cannot lose them. Use one source_ref per fact at most and add no metadata block. "
    "Return every section the schema asks for. Build timeline_events from the times and "
    "ordered steps in the input. Do not drop a section because you ran out of room."
)

# The hypothesis tasks need their own repair: the extraction repair talks about
# facts and timeline_events, which a hypothesis reply has no room for.
TRUNCATION_REPAIR_BY_TASK = {
    "generate_hypotheses": (
        "Your reply was cut off by the output token budget, so the candidates after the cut "
        "are missing. Reply again with the same JSON schema but a shorter set: at most 8 "
        "hypotheses, each with a short title, a one-sentence summary, a one-sentence "
        "cause_claim and at most two events with one-line descriptions. Name the actors in "
        "participants with a plain role; leave unknowns, similar_case_patterns_used and "
        "injury_location empty. Send the whole set in one reply and add no text outside the "
        "JSON."
    ),
    "expand_alternatives": (
        "Your reply was cut off by the output token budget, so the candidates after the cut "
        "are missing. Reply again with the same JSON schema but a shorter set: at most 8 new "
        "candidates, each with a short title, a one-sentence summary, a one-sentence "
        "cause_claim and at most two events with one-line descriptions. Name the actors in "
        "participants with a plain role; leave unknowns, similar_case_patterns_used and "
        "injury_location empty. Send the whole set in one reply and add no text outside the "
        "JSON."
    ),
}


class ProviderUnavailable(RuntimeError):
    """The provider could not be reached, or refused the request repeatedly.

    Raised only after the adapter's own retry budget is spent: at that point a
    generation-level retry would replay the same request into the same wall, so
    the failure is surfaced with the HTTP status instead of being relabelled.
    """


class _HttpChatBase:
    """Minimal client for OpenAI-compatible HTTP APIs (chat/embeddings).

    The generic adapter speaks the de-facto ``/chat/completions`` and
    ``/embeddings`` dialect over plain HTTP, so any endpoint that implements
    it works without vendor SDKs. Provider-specific endpoints are added as
    separate adapters, never by modifying this one.
    """

    is_mock = False

    def __init__(self, cfg: ResolvedCapability, *, name: str, timeout: float = 120.0) -> None:
        self.name = name
        self.model = cfg.model
        self.api_base_url = cfg.api_base_url
        self.label = f"live:{cfg.model or cfg.provider_type}"
        # Structured output is optional: endpoints that reject response_format
        # are retried without it (see _post_json).
        self.max_retries = max(0, int(get_settings().LLM_MAX_RETRIES or 0))
        # Content-Type is left to httpx so multipart bodies (e.g. speech
        # transcription) are not forced to application/json.
        self._client = httpx.Client(
            base_url=f"{cfg.api_base_url}/",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            timeout=timeout,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send one request, riding out transient failures.

        Free tiers answer 429 on bursts and 5xx on load. Retrying here keeps
        the failure out of the pipeline, where one dropped call used to end a
        whole analysis attempt.
        """
        attempt = 0
        while True:
            try:
                resp = self._client.request(method, path, **kwargs)
            except httpx.RequestError as exc:
                if attempt >= self.max_retries:
                    raise ProviderUnavailable(
                        f"provider '{self.name}' is unreachable after {attempt + 1} attempts: {exc}"
                    ) from exc
                time.sleep(_retry_delay(None, attempt))
                attempt += 1
                continue
            if resp.status_code in _RETRYABLE_STATUS and attempt < self.max_retries:
                time.sleep(_retry_delay(resp, attempt))
                attempt += 1
                continue
            if resp.status_code in _RETRYABLE_STATUS:
                raise ProviderUnavailable(
                    f"provider '{self.name}' kept failing after {attempt + 1} attempts "
                    f"(HTTP {resp.status_code}): {resp.text[:200]}"
                )
            return resp

    def _post_json(self, path: str, body: dict[str, Any], allow_response_format: bool = True) -> dict[str, Any]:
        if not allow_response_format:
            body = {k: v for k, v in body.items() if k != "response_format"}
        resp = self._request("POST", path, json=body)
        if resp.status_code == 400 and allow_response_format and "response_format" in resp.text:
            # Some compatible endpoints do not implement response_format.
            return self._post_json(path, body, allow_response_format=False)
        resp.raise_for_status()
        return resp.json()


class HttpChatLLM(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-llm")

    # 1 try + 2 corrective re-calls. Every real-provider failure seen live fits
    # one of three buckets: a transient 400 (Groq `json_validate_failed`),
    # output that will not parse, and output that fails the contract. All three
    # are one re-call away from recovery.
    MAX_GENERATION_ATTEMPTS = 3

    def _completion(self, request: dict[str, Any]) -> tuple[str, str | None]:
        """One upstream completion. Returns (content, finish_reason)."""
        data = self._post_json("chat/completions", request)
        try:
            choice = data["choices"][0]
            content = choice["message"]["content"] or ""
            return content, choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ValueError(f"unexpected chat completion response: {str(data)[:300]}") from exc

    def _request_body(self, task: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        s = get_settings()
        body: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": messages,
        }
        budget = max(int(s.LLM_MAX_OUTPUT_TOKENS or 0), _TASK_OUTPUT_FLOOR.get(task, 0))
        if budget > 0:
            body["max_tokens"] = budget
        effort = (s.LLM_REASONING_EFFORT or "").strip()
        if effort:
            # Reasoning models charge hidden reasoning to the same completion
            # budget; unset, a 900-token call comes back empty with
            # finish_reason "length".
            body["reasoning_effort"] = effort
        return body

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt(task)},
            {"role": "user", "content": f"Input data:\n{json.dumps(payload, default=str)}"},
        ]
        last_error = "no attempts made"
        for _attempt in range(self.MAX_GENERATION_ATTEMPTS):
            _pace()
            try:
                text, finish_reason = self._completion(self._request_body(task, messages))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 400:
                    raise
                # Transient generation fault: there is no output to show the
                # model, so re-call the identical messages.
                last_error = f"provider rejected the request: {exc.response.text[:300]}"
                continue
            except ProviderUnavailable:
                # The transport already spent its retry budget; replaying the
                # request from here would just hit the same limit.
                raise
            except (httpx.RequestError, ConnectionError) as exc:
                # The route from the container to the provider drops for a few
                # seconds now and then; the same call succeeds moments later
                # (observed live: two extractions and the hypothesis call ended
                # on "Connection error").
                last_error = f"connection error: {exc}"[:300]
                continue

            if finish_reason == "length":
                # The provider cut the completion at the output budget. The
                # partial JSON still validates because every missing list
                # defaults to [], so accepting it silently drops every section
                # after the cut (observed live: 5/5 items "extracted", 0
                # timeline events).
                partial = _maybe_complete_partial(task, text)
                if partial is not None:
                    return partial
                last_error = (
                    f"output cut off at the token budget after {len(text)} chars (finish_reason: length)"
                )
                # Do not replay the oversized reply: it leaves the follow-up no
                # room, so every attempt would end on the same cut.
                messages.append({"role": "user", "content": TRUNCATION_REPAIR_BY_TASK.get(task, TRUNCATION_REPAIR)})
                continue

            try:
                parsed = extract_json(text)
            except Exception as exc:
                last_error = f"unparseable output: {exc}"
                messages.append({"role": "assistant", "content": text[:4000]})
                messages.append({"role": "user", "content": "That output was not valid JSON. Reply again with valid JSON only."})
                continue

            try:
                return validate_task_output(task, parsed)
            except ValueError as exc:
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


class HttpChatEmbeddings(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-embedding", timeout=60.0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post_json("embeddings", {"model": self.model, "input": texts})
        try:
            return [d["embedding"] for d in data["data"]]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"unexpected embeddings response: {str(data)[:300]}") from exc
