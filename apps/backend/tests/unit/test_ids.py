from __future__ import annotations

from app.infrastructure.ids import Ids, _max_suffix
from app.models import Fact
from tests.conftest import make_case


def _add_facts(db, case, fact_ids: list[str]) -> None:
    for fid in fact_ids:
        db.add(Fact(case_id=case.id, fact_id=fid, statement=f"statement {fid}"))
    db.commit()


def test_next_fact_parses_suffixes_as_integers(db, dev_user):
    case = make_case(db, dev_user)
    _add_facts(db, case, ["F-009", "F-999", "F-abc"])

    assert Ids.next_fact(db, case.id) == "F-1000"


def test_next_fact_continues_from_numeric_max_not_lexicographic(db, dev_user):
    case = make_case(db, dev_user)
    # Lexicographic max would be "F-009" -> next "F-010", colliding with the
    # existing sequence; integer parsing must continue from F-100.
    _add_facts(db, case, ["F-009", "F-100"])

    assert Ids.next_fact(db, case.id) == "F-101"


def test_next_fact_ignores_non_numeric_suffix_only_rows(db, dev_user):
    case = make_case(db, dev_user)
    _add_facts(db, case, ["F-abc"])

    assert Ids.next_fact(db, case.id) == "F-001"


def test_first_id_on_empty_case_is_001(db, dev_user):
    case = make_case(db, dev_user)

    assert Ids.next_fact(db, case.id) == "F-001"


def test_max_suffix_scoped_to_case(db, dev_user):
    case_a = make_case(db, dev_user, name="Case A")
    case_b = make_case(db, dev_user, name="Case B")
    _add_facts(db, case_a, ["F-005"])
    _add_facts(db, case_b, ["F-042"])

    assert Ids.next_fact(db, case_a.id) == "F-006"
    assert Ids.next_fact(db, case_b.id) == "F-043"


def test_max_suffix_empty_table_returns_one(db, dev_user):
    case = make_case(db, dev_user)

    assert _max_suffix(db, Fact, "fact_id", case.id, "F") == 1
