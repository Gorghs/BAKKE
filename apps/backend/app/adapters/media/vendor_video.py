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
