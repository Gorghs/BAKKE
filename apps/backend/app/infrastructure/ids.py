from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _max_suffix(db: Session, model, column_name: str, case_id: str, prefix: str, pad: int = 3) -> int:
    """Compute the next sequence number for a prefixed ID within a case."""
    col = getattr(model, column_name)
    stmt = select(func.max(col)).where(model.case_id == case_id)
    current = db.execute(stmt).scalar()
    if not current:
        return 1
    try:
        return int(str(current).split("-")[-1]) + 1
    except ValueError:
        return 1


class Ids:
    """Case-scoped ID generators: E-001, F-001, EN-001, T-001, FA-001, H-001, etc."""

    @staticmethod
    def next_evidence(db: Session, case_id: str, prefix: str = "E", pad: int = 3) -> str:
        from app.models import EvidenceItem

        return f"{prefix}-{_max_suffix(db, EvidenceItem, 'evidence_id', case_id, prefix, pad):0{pad}d}"

    @staticmethod
    def next_fact(db: Session, case_id: str) -> str:
        from app.models import Fact

        return f"F-{_max_suffix(db, Fact, 'fact_id', case_id, 'F'):0>3d}"

    @staticmethod
    def next_entity(db: Session, case_id: str) -> str:
        from app.models import Entity

        return f"EN-{_max_suffix(db, Entity, 'entity_id', case_id, 'EN'):0>3d}"

    @staticmethod
    def next_finding(db: Session, case_id: str) -> str:
        from app.models import Finding

        return f"FD-{_max_suffix(db, Finding, 'finding_id', case_id, 'FD'):0>3d}"

    @staticmethod
    def next_timeline(db: Session, case_id: str) -> str:
        from app.models import TimelineEvent

        return f"T-{_max_suffix(db, TimelineEvent, 'event_id', case_id, 'T'):0>3d}"

    @staticmethod
    def next_constraint(db: Session, case_id: str) -> str:
        from app.models import Constraint

        return f"C-{_max_suffix(db, Constraint, 'constraint_id', case_id, 'C'):0>3d}"

    @staticmethod
    def next_anchor(db: Session, case_id: str) -> str:
        from app.models import ForensicAnchor

        return f"FA-{_max_suffix(db, ForensicAnchor, 'anchor_id', case_id, 'FA'):0>3d}"

    @staticmethod
    def next_conflict(db: Session, case_id: str) -> str:
        from app.models import Conflict

        return f"CONFLICT-C-{_max_suffix(db, Conflict, 'conflict_id', case_id, 'CONFLICT-C'):0>3d}"

    @staticmethod
    def next_hypothesis(db: Session, case_id: str) -> str:
        from app.models import Hypothesis

        return f"H-{_max_suffix(db, Hypothesis, 'hypothesis_id', case_id, 'H'):0>3d}"