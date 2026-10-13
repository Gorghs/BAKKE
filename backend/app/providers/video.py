from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import get_settings
from app.providers import runtime as runtime_config
from app.providers.schematic import render_schematic_video


class MockVideoGenerationProvider:
    name = "mock-video"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK (schematic 3D animation)"

    def generate(self, prompt: str, output_path: str, duration_seconds: float, scene: dict[str, Any] | None = None) -> dict[str, Any]:
        # In mock mode we do not call a real AI video API. We render a schematic
        # animated floor-plan clip with ffmpeg, explicitly labelled as a mock
        # visualization so it is never mistaken for real AI output.
        scene = scene or {}
        path = render_schematic_video(
            scene, output_path, duration_seconds=max(duration_seconds, 2.0)
        )
        return {
            "path": path,
            "provider": self.name,
            "is_mock": True,
            "label": self.LABEL,
            "duration": duration_seconds,
            "format": "mp4",
        }


class _HttpVideoProvider:
    """Base class for real video-generation API adapters.

    Providers such as Kling, Runway and Hailuo expose different, frequently
    changing REST/async APIs. This adapter encodes the *contract*: a synchronous
    generate() call that blocks until the video is ready and returns local file
    info. Subclasses override `_submit` / `_poll`. Before using a real provider,
    verify the exact API shape for the configured model against the provider
    documentation (see VIDEO_PIPELINE.md).
    """

    is_mock = False
    _BASE_URL = ""
    _API_KEY_ENV = ""

    def __init__(self, api_key: str = "", model: str = "") -> None:
        s = get_settings()
        self.api_key = api_key or s.VIDEO_GENERATION_API_KEY
        self.model = model or s.VIDEO_GENERATION_MODEL or "default"
        self._client = httpx.Client(timeout=60.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        raise NotImplementedError("subclass must implement _submit")

    def _poll(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError("subclass must implement _poll")

    def _http_error(self, exc: httpx.HTTPStatusError) -> str:
        code = exc.response.status_code
        if code in (401, 403):
            return f"video provider '{self.name}' rejected the API key (HTTP {code}); check VIDEO_GENERATION_API_KEY"
        if code == 429:
            return f"video provider '{self.name}' rate limited the request (HTTP 429); out of credits or too many requests"
        return f"video provider '{self.name}' request failed (HTTP {code}): {exc.response.text[:200]}"

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                f"Video provider '{self.name}' is not configured. "
                f"Set VIDEO_GENERATION_API_KEY or use VIDEO_GENERATION_PROVIDER=mock."
            )
        try:
            task = self._submit(prompt, duration_seconds)
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._http_error(exc)) from exc
        task_id = task.get("id") or task.get("task_id")
        if not task_id:
            raise RuntimeError(f"video provider '{self.name}' returned no task id: {str(task)[:300]}")

        result: dict[str, Any] = {}
        for _ in range(120):
            try:
                result = self._poll(task_id)
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(self._http_error(exc)) from exc
            state = str(result.get("status", "")).lower()
            if state in ("succeed", "succeeded", "success", "done", "completed"):
                break
            if state in ("failed", "error", "cancelled"):
                raise RuntimeError(f"video task failed: {result.get('error') or str(result)[:500]}")
            time.sleep(5)
        else:
            raise RuntimeError(
                f"video provider '{self.name}' timed out after {120 * 5}s "
                f"(last state: {result.get('status', 'unknown')})"
            )

        url = result.get("url") or result.get("video_url") or task.get("url")
        if not url:
            raise RuntimeError(f"no video URL in provider response: {str(result)[:500]}")
        try:
            resp = self._client.get(url, timeout=120.0)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"failed to download video from '{self.name}' (HTTP {exc.response.status_code})"
            ) from exc
        if not resp.content:
            raise RuntimeError(f"video provider '{self.name}' returned an empty file")
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return {
            "path": output_path,
            "provider": self.name,
            "is_mock": False,
            "duration": duration_seconds,
            "format": "mp4",
        }


class FalVideoProvider(_HttpVideoProvider):
    """fal.ai queue adapter. One key reaches Kling, Veo, Hailuo and more.

    Contract, verified against fal's queue documentation in October 2026:

        POST https://queue.fal.run/<model>   Authorization: Key <key>
          -> {request_id, status_url, response_url}
        GET  status_url    -> IN_QUEUE | IN_PROGRESS | COMPLETED (+ error field)
        GET  response_url  -> {video: {url, ...}}
    """

    name = "fal"
    _BASE_URL = "https://queue.fal.run"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Key {self.api_key}", "Content-Type": "application/json"}

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        if not self.model or self.model == "default":
            raise RuntimeError(
                "fal provider needs a model id; set VIDEO_GENERATION_MODEL "
                "(e.g. fal-ai/kling-video/v2.1/standard/text-to-video)."
            )
        # Prompt only: extra inputs such as duration are model-specific on fal
        # and a wrong one is a 422. Clip length depends on the model (5-10s).
        r = self._client.post(
            f"{self._BASE_URL}/{self.model}", headers=self._headers(), json={"prompt": prompt}
        )
        r.raise_for_status()
        data = r.json()
        self._queue_urls = (data.get("status_url", ""), data.get("response_url", ""))
        return {"id": data.get("request_id", "")}

    def _poll(self, task_id: str) -> dict[str, Any]:
        status_url, response_url = getattr(self, "_queue_urls", ("", ""))
        if not status_url:
            raise RuntimeError(f"fal poll before submit (task {task_id})")
        r = self._client.get(status_url, headers=self._headers())
        r.raise_for_status()
        data = r.json()
        state = str(data.get("status", ""))
        if state != "COMPLETED":
            return {"status": state.lower()}
        if data.get("error"):
            return {"status": "failed", "error": data["error"]}
        rr = self._client.get(response_url, headers=self._headers())
        rr.raise_for_status()
        result = rr.json()
        video_url = (result.get("video") or {}).get("url") or result.get("url")
        if not video_url:
            return {"status": "completed", "result": result}
        return {"status": "completed", "url": video_url}


class KlingProvider(_HttpVideoProvider):
    name = "kling"
    _BASE_URL = "https://api.klingai.com"

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        r = self._client.post(
            f"{self._BASE_URL}/v1/videos/text2video",
            headers=self._headers(),
            json={"model_name": self.model, "prompt": prompt, "duration": str(max(int(round(duration_seconds)), 5))},
        )
        r.raise_for_status()
        return r.json()["data"]

    def _poll(self, task_id: str) -> dict[str, Any]:
        r = self._client.get(
            f"{self._BASE_URL}/v1/videos/text2video/{task_id}", headers=self._headers()
        )
        r.raise_for_status()
        return r.json()["data"]


class RunwayProvider(_HttpVideoProvider):
    name = "runway"

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        r = self._client.post(
            "https://api.dev.runwayml.com/v1/text_to_video",
            headers=self._headers(),
            json={"model": self.model, "promptText": prompt, "duration": max(int(round(duration_seconds)), 5)},
        )
        r.raise_for_status()
        return r.json()

    def _poll(self, task_id: str) -> dict[str, Any]:
        r = self._client.get(
            f"https://api.dev.runwayml.com/v1/text_to_video/{task_id}", headers=self._headers()
        )
        r.raise_for_status()
        return r.json()


class HailuoProvider(_HttpVideoProvider):
    name = "hailuo"

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        r = self._client.post(
            "https://api.minimaxi.com/v1/video_generation",
            headers=self._headers(),
            json={"model": self.model, "prompt": prompt},
        )
        r.raise_for_status()
        return r.json()

    def _poll(self, task_id: str) -> dict[str, Any]:
        r = self._client.get(
            f"https://api.minimaxi.com/v1/query/video_generation?task_id={task_id}",
            headers=self._headers(),
        )
        r.raise_for_status()
        return r.json()


class GeminiWebVideoProvider:
    """Adapter for a self-hosted gemini-web-to-api bridge.

    The bridge drives Gemini Web's native Videos tool and exposes it as an
    OpenAI-compatible asynchronous job API:

        POST {base}/openai/v1/videos            -> {id, status, ...}
        GET  {base}/openai/v1/videos/{id}       -> status / progress
        GET  {base}/openai/v1/videos/{id}/content -> MP4 (409 until completed)

    Text-to-video only; the bridge decides clip length and resolution
    (1280x720 / 720x1280). One job at a time. Unlike the fal/kling/runway
    adapters, the bridge is a local service so it needs a base URL rather than
    a vendor API key.
    """

    name = "gemini-web"
    is_mock = False

    def __init__(self, base_url: str = "", api_key: str = "", model: str = "") -> None:
        s = get_settings()
        self.base_url = (base_url or s.VIDEO_GENERATION_BASE_URL or "").rstrip("/")
        self.api_key = api_key or s.VIDEO_GENERATION_API_KEY or "not-needed"
        self.model = model or s.VIDEO_GENERATION_MODEL or "sora-2"
        self._client = httpx.Client(timeout=90.0)

    def _http_error(self, exc: httpx.HTTPStatusError) -> str:
        code = exc.response.status_code
        body = (exc.response.text or "")[:200]
        if code in (401, 403):
            return f"gemini-web bridge rejected the request (HTTP {code}): {body}"
        if code == 429:
            return "gemini-web bridge is already generating a video (HTTP 429); retry when it is idle"
        return f"gemini-web bridge request failed (HTTP {code}): {body}"

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]:
        if not self.base_url:
            raise RuntimeError(
                "gemini-web video provider is not configured; set VIDEO_GENERATION_BASE_URL "
                "to the bridge (e.g. http://host.docker.internal:4981)."
            )
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            r = self._client.post(
                f"{self.base_url}/openai/v1/videos",
                headers=headers,
                json={"prompt": prompt, "model": self.model, "aspect_ratio": "16:9"},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._http_error(exc)) from exc
        data = r.json()
        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"video bridge returned no job id: {str(data)[:300]}")

        result: dict[str, Any] = {}
        for _ in range(180):  # ~15 min, past the bridge's own ~11.5 min deadline
            try:
                rr = self._client.get(f"{self.base_url}/openai/v1/videos/{job_id}", headers=self._headers())
                rr.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(self._http_error(exc)) from exc
            result = rr.json()
            state = str(result.get("status", "")).lower()
            if state == "completed":
                break
            if state in ("failed", "error", "cancelled"):
                raise RuntimeError(f"video bridge job failed: {result.get('error') or str(result)[:300]}")
            time.sleep(5)
        else:
            raise RuntimeError(
                f"video bridge job timed out after {120 * 5}s "
                f"(last state: {result.get('status', 'unknown')})"
            )

        try:
            resp = self._client.get(f"{self.base_url}/openai/v1/videos/{job_id}/content", headers=self._headers())
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(self._http_error(exc)) from exc
        if not resp.content:
            raise RuntimeError("video bridge returned an empty file")
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return {
            "path": output_path,
            "provider": self.name,
            "is_mock": False,
            "duration": duration_seconds,
            "format": "mp4",
        }

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}


_PROVIDERS = {
    "mock": MockVideoGenerationProvider,
    "gemini-web": GeminiWebVideoProvider,
    "fal": FalVideoProvider,
    "kling": KlingProvider,
    "runway": RunwayProvider,
    "hailuo": HailuoProvider,
}


def get_video_provider() -> Any:
    s = get_settings()
    name = runtime_config.get_resolved("VIDEO_GENERATION_PROVIDER", s.VIDEO_GENERATION_PROVIDER).lower()
    api_key = runtime_config.get_resolved("VIDEO_GENERATION_API_KEY", s.VIDEO_GENERATION_API_KEY)
    model = runtime_config.get_resolved("VIDEO_GENERATION_MODEL", s.VIDEO_GENERATION_MODEL)
    base_url = runtime_config.get_resolved("VIDEO_GENERATION_BASE_URL", s.VIDEO_GENERATION_BASE_URL)
    cls = _PROVIDERS.get(name, MockVideoGenerationProvider)
    if cls is MockVideoGenerationProvider:
        return cls()
    if cls is GeminiWebVideoProvider:
        return cls(base_url=base_url, api_key=api_key, model=model)
    return cls(api_key=api_key, model=model)