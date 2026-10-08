"""Persistence ports used by workflows.

Workflows persist their own state (case status, evidence status, audit
entries, job progress) through these ports. Adapters in
``app.adapters.persistence`` implement them over SQLAlchemy; tests can
substitute in-memory fakes. Sub-services that still take a database session
receive it from ``UnitOfWork.session`` — that handle is provided by the
persistence adapter, never constructed by the workflow.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditPort(Protocol):
    """Append-only audit trail writer."""

    def record(
        self,
        case_id: str,
        *,
        action: str,
        agent: str,
        provider: str = "",
        summary: str = "",
        input_object_ids: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None: ...


@runtime_checkable
class JobPort(Protocol):
    """Progress reporting for the currently executing background job.

    A no-op implementation is used when a workflow runs interactively
    (no job row), so the same workflow code works in both contexts.
    """

    def set_progress(self, progress: int, stage: str) -> None: ...

    def set_result(self, result: dict[str, Any]) -> None: ...


@runtime_checkable
class CaseStatusPort(Protocol):
    def set_status(self, case_id: str, status: str) -> None: ...


@runtime_checkable
class EvidenceStatusPort(Protocol):
    def mark_processed(self, evidence_pk: str, provider_label: str = "") -> None: ...

    def mark_failed(self, evidence_pk: str, error: str) -> None: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Persistence boundary handed to a workflow by the adapter layer."""

    @property
    def session(self) -> Any: ...

    @property
    def audit(self) -> AuditPort: ...

    @property
    def job(self) -> JobPort: ...

    @property
    def case_status(self) -> CaseStatusPort: ...

    @property
    def evidence_status(self) -> EvidenceStatusPort: ...

    def flush(self) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
