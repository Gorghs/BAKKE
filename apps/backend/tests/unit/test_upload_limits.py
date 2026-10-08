from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app.config import get_settings
from app.features.cases.case_service import CaseService
from app.models import EvidenceItem
from tests.conftest import make_case


def _upload(data: bytes) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename="upload.bin",
        headers=Headers({"content-type": "image/png"}),
    )


def test_upload_rejects_file_over_limit(db, dev_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_MAX_MB", 1)
    case = make_case(db, dev_user)
    oversized = _upload(b"x" * (1024 * 1024 + 1))

    with pytest.raises(HTTPException) as exc:
        CaseService().upload_evidence(db, case.id, "IMAGE", "Big", "", "", oversized)

    assert exc.value.status_code == 413
    assert "1 MB" in exc.value.detail
    assert db.query(EvidenceItem).filter_by(case_id=case.id).count() == 0


def test_upload_accepts_file_within_limit(db, dev_user, monkeypatch):
    monkeypatch.setattr(get_settings(), "UPLOAD_MAX_MB", 1)
    case = make_case(db, dev_user)
    small = _upload(b"x" * 1024)

    ev = CaseService().upload_evidence(db, case.id, "IMAGE", "Small", "", "", small)

    assert ev.size_bytes == 1024
    assert ev.status == "UPLOADED"


def test_upload_empty_file_still_rejected_as_422(db, dev_user):
    case = make_case(db, dev_user)
    empty = _upload(b"")

    with pytest.raises(HTTPException) as exc:
        CaseService().upload_evidence(db, case.id, "IMAGE", "Empty", "", "", empty)

    assert exc.value.status_code == 422
