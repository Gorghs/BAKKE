from __future__ import annotations

import hashlib
from typing import Any

import numpy as np


class MockEmbeddingProvider:
    name = "mock-embedding"
    is_mock = True
    label = "DEVELOPMENT MOCK"
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
