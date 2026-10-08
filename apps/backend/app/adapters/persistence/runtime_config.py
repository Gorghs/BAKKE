from __future__ import annotations

import time
from typing import Any

from app.config import RUNTIME_KEYS  # single source of truth (generic + legacy keys)

_TTL_SECONDS = 2.0

# In-process cache of resolved runtime values: key -> (value, loaded_at).
_cache: dict[str, tuple[str, float]] = {}
_last_load = 0.0


def _read_db() -> dict[str, str]:
    """Load all provider settings from the DB using a short-lived session.

    Best-effort: any failure (DB unavailable, no tables) returns {} so the
    caller falls back to environment / defaults. This keeps provider
    construction working in tests and during startup.
    """
    try:
        from app.database import SessionLocal
        from app.models import ProviderSetting

        with SessionLocal() as db:
            rows = db.query(ProviderSetting).all()
            return {r.key: r.value for r in rows if r.value}
    except Exception:
        return {}


def _refresh() -> dict[str, str]:
    global _last_load
    now = time.monotonic()
    if now - _last_load >= _TTL_SECONDS:
        loaded = _read_db()
        _cache.clear()
        for k, v in loaded.items():
            _cache[k] = (v, now)
        _last_load = now
    return {k: v for k, (v, _) in _cache.items()}


def get_value(key: str) -> str:
    return _refresh().get(key, "")


def get_resolved(key: str, env: str = "") -> str:
    """Runtime DB override -> env value -> '' (caller supplies default)."""
    return get_value(key) or env


def set_values(mapping: dict[str, str]) -> dict[str, Any]:
    """Persist provider config and refresh the in-process cache immediately.

    Returns the stored values.
    """
    from app.database import SessionLocal
    from app.models import ProviderSetting

    stored: dict[str, str] = {}
    with SessionLocal() as db:
        for key, value in mapping.items():
            if key not in RUNTIME_KEYS:
                continue
            value = (value or "").strip()
            row = db.get(ProviderSetting, key)
            if value == "":
                if row:
                    db.delete(row)
                continue
            if row:
                row.value = value
            else:
                db.add(ProviderSetting(key=key, value=value))
            stored[key] = value
        db.commit()
    global _last_load
    _last_load = 0.0  # force reload
    _refresh()
    return stored


def clear() -> None:
    """Drop all runtime overrides (used by tests / reset)."""
    from app.database import SessionLocal
    from app.models import ProviderSetting

    with SessionLocal() as db:
        db.query(ProviderSetting).filter(ProviderSetting.key.in_(RUNTIME_KEYS)).delete()
        db.commit()
    global _last_load
    _last_load = 0.0
    _refresh()
