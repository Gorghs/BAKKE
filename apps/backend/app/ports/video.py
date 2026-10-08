"""Video ports: understanding (input) and generation (output)."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VideoUnderstandingPort(Protocol):
    """Provider-independent video understanding port (input side)."""

    name: str
    is_mock: bool
    label: str

    def understand_video(self, video_path: str, prompt: str) -> dict[str, Any]: ...


@runtime_checkable
class VideoGenerationPort(Protocol):
    """Provider-independent video generation port (output side)."""

    name: str
    is_mock: bool
    label: str

    def generate(self, prompt: str, output_path: str, duration_seconds: float) -> dict[str, Any]: ...
