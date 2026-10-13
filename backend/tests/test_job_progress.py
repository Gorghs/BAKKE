from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.jobs import progress as progress_mod
from app.models import EvidenceItem
from app.services.analysis_service import AnalysisService
from tests.conftest import make_case


def _bind_reporter_to_engine(monkeypatch, engine) -> None:
    """Point the reporter's private session at the test engine.

    The reporter opens its own session so progress is visible before the
    caller commits; the test engine must be that session's bind.
    """
    monkeypatch.setattr(progress_mod, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))


def test_progress_reporter_roundtrip(db, engine, monkeypatch):
    _bind_reporter_to_engine(monkeypatch, engine)
    rep = progress_mod.ProgressReporter("job-1")

    rep.report("Extracting evidence E-001", 12)
    row = progress_mod.read_progress(db, "job-1")
    assert row is not None
    assert (row.stage, row.percent) == ("Extracting evidence E-001", 12)

    rep.report("Reasoning iteration 2/5", 60)
    db.expire_all()
    row = progress_mod.read_progress(db, "job-1")
    assert row.percent == 60
    assert "iteration 2/5" in row.stage

    rep.clear()
    db.expire_all()
    assert progress_mod.read_progress(db, "job-1") is None


def test_progress_percent_is_clamped(db, engine, monkeypatch):
    _bind_reporter_to_engine(monkeypatch, engine)
    rep = progress_mod.ProgressReporter("job-2")

    rep.report("too high", 250)
    assert progress_mod.read_progress(db, "job-2").percent == 100

    rep.report("too low", -5)
    db.expire_all()
    assert progress_mod.read_progress(db, "job-2").percent == 0

    rep.clear()


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, int]] = []

    def report(self, stage: str, percent: int) -> None:
        self.events.append((stage, percent))

    def clear(self) -> None:
        return


def test_analyze_case_reports_monotonic_progress(db, dev_user):
    case = make_case(db, dev_user)
    db.add(
        EvidenceItem(
            case_id=case.id,
            evidence_id="E-001",
            item_type="INVESTIGATOR_REPORT",
            title="Entry log",
            description="Entry log",
            status="UPLOADED",
            raw_text="Person A entered the apartment at 20:14 and left at 20:20.",
            extra={"evidence_type": "INVESTIGATOR_REPORT"},
        )
    )
    case.evidence_count = 1
    db.commit()

    rec = _Recorder()
    AnalysisService().analyze_case(db, case.id, progress=rec)
    db.commit()

    assert rec.events, "no progress was reported"
    assert rec.events[-1] == ("Analysis complete", 100)
    stages = [s for s, _ in rec.events]
    assert any(s.startswith("Extracting evidence") for s in stages)
    assert any(s.startswith("Reasoning iteration") for s in stages)
    pcts = [p for _, p in rec.events]
    assert pcts == sorted(pcts), f"progress went backwards: {pcts}"
