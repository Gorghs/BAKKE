"""Speech-to-text port."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SpeechToTextPort(Protocol):
    """Provider-independent speech-to-text port."""

    name: str
    is_mock: bool
    label: str

    def transcribe(self, audio_path: str) -> str: ...
