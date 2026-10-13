from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.providers.video import FalVideoProvider

MODEL = "fal-ai/kling-video/v2.1/standard/text-to-video"
PROMPT = "Hallway scene. NOT RECORDED FOOTAGE."
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


class _FakeFal:
    """Minimal fal queue: submit, status sequence, result, media download."""

    def __init__(
        self,
        status_states: list[str] | None = None,
        error: str | None = None,
        video_bytes: bytes | None = None,
        submit_status: int = 200,
        result_json: dict | None = None,
    ) -> None:
        self.status_states = status_states or ["COMPLETED"]
        self.error = error
        self.video_bytes = MP4_BYTES if video_bytes is None else video_bytes
        self.submit_status = submit_status
        self.result_json = result_json
        self.requests: list[httpx.Request] = []
        self.status_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.url.host
        path = request.url.path
        if host == "queue.fal.run" and request.method == "POST":
            if self.submit_status != 200:
                return httpx.Response(self.submit_status, json={"detail": "rejected"})
            return httpx.Response(
                200,
                json={
                    "request_id": "req-1",
                    "status_url": f"https://queue.fal.run/{MODEL}/requests/req-1/status",
                    "response_url": f"https://queue.fal.run/{MODEL}/requests/req-1/response",
                },
            )
        if path.endswith("/status"):
            state = self.status_states[min(self.status_calls, len(self.status_states) - 1)]
            self.status_calls += 1
            body: dict = {"status": state, "request_id": "req-1"}
            if state == "COMPLETED" and self.error:
                body["error"] = self.error
            return httpx.Response(200, json=body)
        if path.endswith("/response"):
            if self.result_json is not None:
                return httpx.Response(200, json=self.result_json)
            return httpx.Response(200, json={"video": {"url": "https://v3.fal.media/files/out.mp4"}})
        if host == "v3.fal.media":
            return httpx.Response(200, content=self.video_bytes, headers={"content-type": "video/mp4"})
        return httpx.Response(404, json={"detail": "not found"})


def _provider(fake: _FakeFal, api_key: str = "fal-test-key", model: str = MODEL) -> FalVideoProvider:
    p = FalVideoProvider(api_key=api_key, model=model)
    p._client = httpx.Client(transport=httpx.MockTransport(fake.handler))
    return p


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda _s: None)


class TestFalVideoProvider:
    def test_submit_uses_key_auth_and_downloads(self, tmp_path):
        fake = _FakeFal()
        out = tmp_path / "out.mp4"
        result = _provider(fake).generate(PROMPT, str(out), 6.0)

        submit = fake.requests[0]
        assert str(submit.url) == f"https://queue.fal.run/{MODEL}"
        assert submit.headers["authorization"] == "Key fal-test-key"
        assert json.loads(submit.content) == {"prompt": PROMPT}

        assert result["provider"] == "fal"
        assert result["is_mock"] is False
        assert result["format"] == "mp4"
        assert Path(result["path"]).read_bytes() == MP4_BYTES

    def test_queue_states_are_polled_until_done(self, tmp_path):
        fake = _FakeFal(status_states=["IN_QUEUE", "IN_PROGRESS", "COMPLETED"])
        _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)
        assert fake.status_calls == 3

    def test_completed_with_error_fails(self, tmp_path):
        fake = _FakeFal(error="insufficient credit balance")
        with pytest.raises(RuntimeError, match="insufficient credit balance"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)

    def test_result_without_video_url_fails(self, tmp_path):
        fake = _FakeFal(result_json={"audio": {"url": "https://x/y.mp3"}})
        with pytest.raises(RuntimeError, match="no video URL"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)

    def test_empty_download_fails(self, tmp_path):
        fake = _FakeFal(video_bytes=b"")
        with pytest.raises(RuntimeError, match="empty"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)

    def test_missing_model_is_rejected_before_any_request(self, tmp_path):
        fake = _FakeFal()
        with pytest.raises(RuntimeError, match="VIDEO_GENERATION_MODEL"):
            _provider(fake, model="default").generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)
        assert fake.requests == []

    def test_missing_key_is_rejected(self, tmp_path):
        fake = _FakeFal()
        p = _provider(fake)
        p.api_key = ""
        with pytest.raises(RuntimeError, match="VIDEO_GENERATION_API_KEY"):
            p.generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)
        assert fake.requests == []

    def test_http_401_maps_to_key_error(self, tmp_path):
        fake = _FakeFal(submit_status=401)
        with pytest.raises(RuntimeError, match="API key"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)

    def test_http_429_maps_to_credit_error(self, tmp_path):
        fake = _FakeFal(submit_status=429)
        with pytest.raises(RuntimeError, match="rate limited|out of credits"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)

    def test_poll_gives_up_after_timeout(self, tmp_path):
        fake = _FakeFal(status_states=["IN_QUEUE"])
        with pytest.raises(RuntimeError, match="timed out"):
            _provider(fake).generate(PROMPT, str(tmp_path / "o.mp4"), 6.0)
        assert fake.status_calls == 120
