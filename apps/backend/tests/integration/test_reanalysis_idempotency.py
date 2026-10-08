from __future__ import annotations

from app.adapters.persistence import SqlAlchemyUnitOfWork
from app.models import (
    Case,
    Constraint,
    Conflict,
    Entity,
    EvidenceItem,
    Fact,
    Finding,
    ForensicAnchor,
    Hypothesis,
    Scenario,
    TimelineEvent,
)
from app.workflows import AnalyzeCaseWorkflow
from tests.conftest import make_case
from tests.integration.test_demo_pipeline import EVIDENCE


def _graph_counts(db, case_id: str) -> dict[str, int]:
    def count(model) -> int:
        return db.query(model).filter_by(case_id=case_id).count()

    return {
        "facts": count(Fact),
        "findings": count(Finding),
        "entities": count(Entity),
        "timeline": count(TimelineEvent),
        "anchors": count(ForensicAnchor),
        "constraints": count(Constraint),
        "conflicts": count(Conflict),
        "hypotheses": count(Hypothesis),
        "scenarios": count(Scenario),
    }


def test_reanalysis_does_not_duplicate_knowledge_graph(db, dev_user):
    case = make_case(db, dev_user)
    for i, (itype, title, text) in enumerate(EVIDENCE, start=1):
        db.add(
            EvidenceItem(
                case_id=case.id,
                evidence_id=f"E-{i:03d}",
                item_type=itype,
                title=title,
                description=title,
                status="UPLOADED",
                raw_text=text,
                extra={"evidence_type": itype},
            )
        )
    case.evidence_count = len(EVIDENCE)
    db.commit()

    first = AnalyzeCaseWorkflow(SqlAlchemyUnitOfWork(db))
    first.run(case.id)
    db.commit()
    after_first = _graph_counts(db, case.id)

    assert after_first["facts"] > 0
    assert after_first["findings"] > 0
    assert after_first["hypotheses"] > 0

    second = AnalyzeCaseWorkflow(SqlAlchemyUnitOfWork(db))
    result = second.run(case.id)
    db.commit()
    after_second = _graph_counts(db, case.id)

    assert result["status"] == "ANALYZED"
    for key in ("facts", "findings", "entities", "timeline", "anchors", "constraints", "conflicts"):
        assert after_second[key] <= after_first[key], f"{key} duplicated: {after_first[key]} -> {after_second[key]}"
    assert after_second["facts"] > 0, "the graph must be rebuilt, not just purged"
    assert after_second["hypotheses"] == after_first["hypotheses"], "hypothesis count doubled"
    assert after_second["scenarios"] <= after_first["scenarios"]

    # M3: the fusion stage must be recorded exactly once per run.
    stage_names = [s["stage"] for s in second.ctx.stages]
    assert stage_names.count("extraction") == 1
    assert stage_names.count("fusion") == 1

    assert db.get(Case, case.id).status == "ANALYZED"
