"""Replay manifests: recorded provenance for offline workflow replay."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import get_settings


def manifest_path(case_id: str, kind: str) -> Path:
    safe_case = "".join(c for c in case_id if c.isalnum() or c in "-_")
    safe_kind = "".join(c for c in kind if c.isalnum() or c in "-_.")
    return get_settings().data_path / "replay" / f"{safe_case}.{safe_kind}.json"


def write_manifest(case_id: str, kind: str, payload: dict[str, Any]) -> str:
    path = manifest_path(case_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "manifest_version": 1,
        "kind": kind,
        "written_at": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return str(path)


def load_manifest(case_id: str, kind: str) -> dict[str, Any] | None:
    path = manifest_path(case_id, kind)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
