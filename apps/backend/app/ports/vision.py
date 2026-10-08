"""Vision (image understanding) port."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class VisionPort(Protocol):
    """Provider-independent image analysis port."""

    name: str
    is_mock: bool
    label: str

    def analyze_image(self, image_path: str, prompt: str) -> dict[str, Any]: ...
