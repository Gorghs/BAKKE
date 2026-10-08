"""Shared execution context for workflow runs."""
from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from app.prompts import PROMPT_VERSION


@dataclass
class AnalysisContext:
    """Correlation and provenance data shared by every workflow stage.

    The same context object flows through a run so audit entries, job
    progress, logs and the replay manifest all carry one ``run_id`` and the
    prompt version that was active.
    """

    case_id: str
    job_id: str = ""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    prompt_version: str = PROMPT_VERSION
    providers: dict[str, str] = field(default_factory=dict)
    stages: list[dict[str, Any]] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Time a stage and record its outcome (ok/error) in order."""
        t0 = time.monotonic()
        status = "ok"
        try:
            yield
        except Exception:
            status = "error"
            raise
        finally:
            self.stages.append(
                {
                    "stage": name,
                    "status": status,
                    "seconds": round(time.monotonic() - t0, 3),
                }
            )

    def note_provider(self, capability: str, label: str, is_mock: bool) -> None:
        self.providers[capability] = f"{label}{' (mock)' if is_mock else ''}"

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "case_id": self.case_id,
            "job_id": self.job_id,
            "prompt_version": self.prompt_version,
            "providers": dict(self.providers),
            "stages": list(self.stages),
            "elapsed_seconds": round(time.time() - self.started_at, 3),
        }
