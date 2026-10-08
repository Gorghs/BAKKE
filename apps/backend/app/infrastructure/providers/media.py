from __future__ import annotations

from typing import Any

from app.config import get_settings


class MockSpeechToTextProvider:
    name = "mock-stt"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK"

    def transcribe(self, audio_path: str) -> str:
        return ""


class OpenAISpeechToTextProvider:
    name = "openai-stt"
    is_mock = False

    def __init__(self, api_key: str = "", model: str = "") -> None:
        from openai import OpenAI

        s = get_settings()
        self.api_key = api_key or s.OPENAI_API_KEY
        self.model = model or s.STT_MODEL
        self.client = OpenAI(api_key=self.api_key)

    def transcribe(self, audio_path: str) -> str:
        with open(audio_path, "rb") as f:
            tr = self.client.audio.transcriptions.create(model=self.model, file=f)
        return tr.text


class MockVisionProvider:
    name = "mock-vision"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK"

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]:
        return {"objects": [], "people": [], "note": "No visual analysis in mock mode."}


class OpenAIVisionProvider:
    name = "openai-vision"
    is_mock = False

    def __init__(self, api_key: str = "", model: str = "") -> None:
        from openai import OpenAI

        s = get_settings()
        self.api_key = api_key or s.OPENAI_API_KEY
        self.model = model or s.OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]:
        import base64

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    ],
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        import json

        return json.loads(resp.choices[0].message.content or "{}")


class MockVideoUnderstandingProvider:
    name = "mock-video-understanding"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK"

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]:
        return {"people": [], "objects": [], "note": "No video analysis in mock mode."}


class OpenAIVideoUnderstandingProvider:
    name = "openai-video-understanding"
    is_mock = False

    def __init__(self, api_key: str = "", model: str = "") -> None:
        from openai import OpenAI

        s = get_settings()
        self.api_key = api_key or s.OPENAI_API_KEY
        self.model = model or s.OPENAI_MODEL
        self.client = OpenAI(api_key=self.api_key)

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]:
        # Representative implementation: sample frames and run vision analysis.
        import json

        frames = _sample_frames(video_path, n=4)
        notes = []
        for i, frame in enumerate(frames):
            r = OpenAIVisionProvider(self.client.api_key, self.model).analyze_image(frame, prompt)
            notes.append({"frame": i, "analysis": r})
        return {"frame_analyses": notes, "note": "frame-sampled analysis"}


def _sample_frames(video_path: str, n: int = 4) -> list[str]:
    import subprocess

    import numpy as np

    out = []
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video_path],
        capture_output=True,
        text=True,
    )
    try:
        duration = float(probe.stdout.strip())
    except ValueError:
        duration = 0.0
    for i in range(n):
        t = (duration * i) / max(n - 1, 1) if duration > 0 else 0
        target = f"/tmp/bakke_frame_{i}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", video_path, "-frames:v", "1", "-q:v", "3", target],
            capture_output=True,
        )
        out.append(target)
    return out