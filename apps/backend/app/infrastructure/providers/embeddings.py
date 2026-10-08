from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from app.config import get_settings
from app.infrastructure.providers import runtime as runtime_config

settings = get_settings()


class MockEmbeddingProvider:
    name = "mock-embedding"
    is_mock = True
    LABEL = "DEVELOPMENT MOCK"

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            vec = np.zeros(self.dim)
            for token in t.lower().split():
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if (h >> 31) & 1 else -1.0
                vec[idx] += sign
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            out.append(vec.tolist())
        return out


class OpenAIEmbeddingProvider:
    name = "openai-embedding"
    is_mock = False

    def __init__(self, api_key: str = "", model: str = "") -> None:
        from openai import OpenAI

        self.api_key = api_key or get_settings().OPENAI_API_KEY
        self.model = model or get_settings().EMBEDDING_MODEL
        self.client = OpenAI(api_key=self.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedding_provider() -> Any:
    provider = runtime_config.get_resolved("EMBEDDING_PROVIDER", settings.EMBEDDING_PROVIDER).lower()
    api_key = runtime_config.get_resolved("OPENAI_API_KEY", settings.OPENAI_API_KEY)
    model = runtime_config.get_resolved("EMBEDDING_MODEL", settings.EMBEDDING_MODEL)
    if provider == "openai" and api_key:
        return OpenAIEmbeddingProvider(api_key=api_key, model=model)
    return MockEmbeddingProvider()
