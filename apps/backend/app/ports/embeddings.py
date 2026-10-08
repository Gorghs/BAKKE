"""Embeddings port."""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingsPort(Protocol):
    """Provider-independent text embedding port."""

    name: str
    is_mock: bool
    label: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...
