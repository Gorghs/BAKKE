from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.adapters.ai.http_chat import _HttpChatBase
from app.config import ResolvedCapability


class HttpChatSpeechToText(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-stt", timeout=300.0)

    def transcribe(self, audio_path: str) -> str:
        path = Path(audio_path)
        with path.open("rb") as f:
            resp = self._client.post(
                "audio/transcriptions",
                data={"model": self.model},
                files={"file": (path.name, f, "application/octet-stream")},
            )
        resp.raise_for_status()
        return resp.json().get("text", "")


class HttpChatVision(_HttpChatBase):
    def __init__(self, cfg: ResolvedCapability) -> None:
        super().__init__(cfg, name="http-chat-vision")

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        data = self._post_json(
            "chat/completions",
            {
                "model": self.model,
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        ],
                    }
                ],
            },
        )
        try:
            text = data["choices"][0]["message"]["content"] or "{}"
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError(f"unexpected chat completion response: {str(data)[:300]}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from vision provider: {text[:300]}") from exc


class HttpChatVideoUnderstanding(_HttpChatBase):
    """Frame-sampled video understanding on top of a vision-capable endpoint."""

    def __init__(self, cfg: ResolvedCapability, vision: HttpChatVision | None = None) -> None:
        super().__init__(cfg, name="http-chat-video-understanding")
        self._vision = vision or HttpChatVision(cfg)

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]:
        frames = sample_frames(video_path, n=4)
        try:
            notes = []
            for i, frame in enumerate(frames):
                r = self._vision.analyze_image(frame, prompt)
                notes.append({"frame": i, "analysis": r})
            return {"frame_analyses": notes, "note": "frame-sampled analysis"}
        finally:
            if frames:
                shutil.rmtree(Path(frames[0]).parent, ignore_errors=True)


def sample_frames(video_path: str, n: int = 4) -> list[str]:
    out_dir = Path(tempfile.mkdtemp(prefix="bakke_frames_"))
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True,
        text=True,
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        duration = 0.0
    out = []
    try:
        for i in range(n):
            t = (duration * i) / max(n - 1, 1) if duration > 0 else 0
            target = out_dir / f"frame_{i}.jpg"
            proc = subprocess.run(
                ["ffmpeg", "-y", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "3", str(target)],
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                stderr_tail = (proc.stderr or "")[-300:]
                raise RuntimeError(
                    f"ffmpeg frame extraction failed (exit {proc.returncode}) for {video_path}: {stderr_tail}"
                )
            out.append(str(target))
    except Exception:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    return out


__all__ = [
    "HttpChatSpeechToText",
    "HttpChatVideoUnderstanding",
    "HttpChatVision",
    "sample_frames",
]
