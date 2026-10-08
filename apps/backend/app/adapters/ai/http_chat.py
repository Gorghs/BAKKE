from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import ResolvedCapability
from app.prompts import system_prompt, validate_task_output


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
        # Content-Type is left to httpx so multipart bodies (e.g. speech
        # transcription) are not forced to application/json.
        self._client = httpx.Client(
            base_url=f"{cfg.api_base_url}/",
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            timeout=timeout,
        )

    def _post_json(self, path: str, body: dict[str, Any], allow_response_format: bool = True) -> dict[str, Any]:
        if not allow_response_format:
            body = {k: v for k, v in body.items() if k != "response_format"}
        resp = self._client.post(path, json=body)
        if resp.status_code == 400 and allow_response_format and "response_format" in resp.text:
            # Some compatible endpoints do not implement response_format.
            return self._post_json(path, body, allow_response_format=False)
        resp.raise_for_status()
        return resp.json()


class HttpChatLLM(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-llm")

    def run_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        content = json.dumps(payload, default=str)
        data = self._post_json(
            "chat/completions",
            {
                "model": self.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt(task)},
                    {"role": "user", "content": f"Input data:\n{content}"},
                ],
            },
        )
        try:
            text = data["choices"][0]["message"]["content"] or "{}"
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"unexpected chat completion response: {str(data)[:300]}") from exc
        try:
            parsed = extract_json(text)
        except Exception as exc:
            raise ValueError(f"invalid JSON from provider: {text[:300]}") from exc
        return validate_task_output(task, parsed)


class HttpChatEmbeddings(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-embedding", timeout=60.0)

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post_json("embeddings", {"model": self.model, "input": texts})
        try:
            return [d["embedding"] for d in data["data"]]
        except (KeyError, TypeError) as exc:
            raise ValueError(f"unexpected embeddings response: {str(data)[:300]}") from exc
