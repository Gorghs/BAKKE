from __future__ import annotations

import time
from typing import Any

from app.adapters.media.schematic import render_schematic_video
from app.config import ResolvedCapability


class MockVideoGenerationProvider:
    name = "mock-video"
    is_mock = True
    label = "DEVELOPMENT MOCK (schematic 3D animation)"
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
            "label": self.label,
            "duration": duration_seconds,
            "format": "mp4",
        }


class _HttpVideoProvider:
    """Base class for real video-generation API adapters.

    Each video provider exposes a different, frequently changing async REST
    API. This adapter encodes the shared *contract*: a synchronous generate()
    call that blocks until the video is ready and returns local file info.
    Subclasses implement `_submit` / `_poll` against their endpoint. Before
    using a real provider, verify the exact API shape for the configured
    model against the provider documentation (see docs/video-pipeline.md).
    """

    is_mock = False
    _PATH_SUBMIT = ""
    _PATH_POLL = ""
    _BASE_URL = ""

    def __init__(self, cfg: ResolvedCapability) -> None:
        import httpx

        self.api_key = cfg.api_key
        self.model = cfg.model or "default"
        self.label = f"live:{self.name}:{self.model}"
        self._client = httpx.Client(timeout=60.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _submit(self, prompt: str, duration_seconds: float) -> dict[str, Any]:
        raise NotImplementedError("subclass must implement _submit")

    def _poll(self, task_id: str) -> dict[str, Any]:
        raise NotImplementedError("subclass must implement _poll")

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                f"Video provider '{self.name}' is not configured. "
                f"Set VIDEO_GENERATION_API_KEY or use VIDEO_GENERATION_PROVIDER_TYPE=mock."
            )
        task = self._submit(prompt, duration_seconds)
        task_id = task.get("id") or task.get("task_id")
        result: dict[str, Any] = {}
        for _ in range(120):
            result = self._poll(task_id)
            state = str(result.get("status", "")).lower()
            if state in ("succeeded", "success", "done", "completed"):
                break
            if state in ("failed", "error", "cancelled"):
                raise RuntimeError(f"video task failed: {result}")
            time.sleep(5)
        url = result.get("url") or result.get("video_url") or task.get("url")
        if not url:
            raise RuntimeError(f"no video URL in provider response: {result}")
        resp = self._client.get(url)
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(resp.content)
        return {
            "path": output_path,
            "provider": self.name,
            "is_mock": False,
            "duration": duration_seconds,
            "format": "mp4",
        }


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
    (1280x720 / 720x1280) and runs one job at a time. Unlike the vendor
    adapters, the bridge is a local service, so it needs a base URL rather than
    an API key.
    """

    name = "gemini-web"
    is_mock = False

    # The bridge's own default deadline is 20 minutes; poll past it in 5s steps
    # so a long render does not fail on this side first.
    POLL_INTERVAL_SECONDS = 5
    POLL_ATTEMPTS = 260

    def __init__(self, cfg: ResolvedCapability) -> None:
        import httpx

        self.base_url = (cfg.api_base_url or "").rstrip("/")
        self.api_key = cfg.api_key or "not-needed"
        self.model = cfg.model or "sora-2"
        self.label = f"live:{self.name}:{self.model}"
        self._client = httpx.Client(timeout=90.0)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _http_error(self, exc: Any) -> str:
        code = exc.response.status_code
        body = (exc.response.text or "")[:200]
        if code in (401, 403):
            return f"gemini-web bridge rejected the request (HTTP {code}): {body}"
        if code == 409:
            return "gemini-web bridge has no content yet (HTTP 409); the job is not finished"
        if code == 429:
            return "gemini-web bridge is already generating a video (HTTP 429); retry when it is idle"
        return f"gemini-web bridge request failed (HTTP {code}): {body}"

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]:
        import httpx

        if not self.base_url:
            raise RuntimeError(
                "gemini-web video provider is not configured; set VIDEO_GENERATION_API_BASE_URL "
                "(or VIDEO_GENERATION_BASE_URL) to the bridge, e.g. http://host.docker.internal:4981."
            )
        try:
            r = self._client.post(
                f"{self.base_url}/openai/v1/videos",
                headers=self._headers(),
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
        for _ in range(self.POLL_ATTEMPTS):
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
            time.sleep(self.POLL_INTERVAL_SECONDS)
        else:
            raise RuntimeError(
                f"video bridge job timed out after {self.POLL_ATTEMPTS * self.POLL_INTERVAL_SECONDS}s "
                f"(last state: {result.get('status', 'unknown')})"
            )

        try:
            resp = self._client.get(
                f"{self.base_url}/openai/v1/videos/{job_id}/content", headers=self._headers(), timeout=300.0
            )
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

