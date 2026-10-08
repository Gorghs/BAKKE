from __future__ import annotations

from typing import Any


class MockSpeechToTextProvider:
    name = "mock-stt"
    is_mock = True
    label = "DEVELOPMENT MOCK"
    LABEL = "DEVELOPMENT MOCK"

    def transcribe(self, audio_path: str) -> str:
        return ""


class MockVisionProvider:
    name = "mock-vision"
    is_mock = True
    label = "DEVELOPMENT MOCK"
    LABEL = "DEVELOPMENT MOCK"

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]:
        return {"objects": [], "people": [], "note": "No visual analysis in mock mode."}


class MockVideoUnderstandingProvider:
    name = "mock-video-understanding"
    is_mock = True
    label = "DEVELOPMENT MOCK"
    LABEL = "DEVELOPMENT MOCK"

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]:
        return {"people": [], "objects": [], "note": "No video analysis in mock mode."}
