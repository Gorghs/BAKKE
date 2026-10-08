from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force explicit mock providers and an isolated DB before any app module
# reads settings — no silent live-provider use in tests. Hard-assign (not
# setdefault): an ambient live key in the developer's shell must never win.
os.environ["LLM_PROVIDER_TYPE"] = "mock"
os.environ["EMBEDDING_PROVIDER_TYPE"] = "mock"
os.environ["STT_PROVIDER_TYPE"] = "mock"
os.environ["VISION_PROVIDER_TYPE"] = "mock"
os.environ["VIDEO_UNDERSTANDING_PROVIDER_TYPE"] = "mock"
os.environ["VIDEO_GENERATION_PROVIDER_TYPE"] = "mock"
os.environ["STORAGE_PROVIDER"] = "local"

from app.models import Case, User  # noqa: E402
from app.models.base import Base  # noqa: E402

import app.database as app_database  # noqa: E402
from app.adapters.persistence import runtime_config  # noqa: E402
from app.config import get_settings  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_data_dirs(tmp_path):
    """Send DATA_DIR / VIDEO_OUTPUT_DIR to a per-test tmp dir so manifests,
    uploads and video artefacts never touch the developer's ./data tree."""
    settings = get_settings()
    old_data, old_video = settings.DATA_DIR, settings.VIDEO_OUTPUT_DIR
    settings.DATA_DIR = str(tmp_path / "data")
    settings.VIDEO_OUTPUT_DIR = str(tmp_path / "videos")
    yield
    settings.DATA_DIR = old_data
    settings.VIDEO_OUTPUT_DIR = old_video


@pytest.fixture(autouse=True)
def _reset_runtime_config_cache():
    """The in-process provider override cache is global: clear it around every
    test so values loaded from one test's DB can never leak into the next."""
    def _clear() -> None:
        runtime_config._cache.clear()
        runtime_config._last_load = 0.0

    _clear()
    yield
    _clear()


@pytest.fixture()
def engine(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    monkeypatch.setattr(app_database, "engine", eng)
    monkeypatch.setattr(app_database, "SessionLocal", sessionmaker(bind=eng, expire_on_commit=False))
    yield eng
    eng.dispose()
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture()
def db(engine):
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def dev_user(db) -> User:
    u = User(email="dev@test.local", display_name="Dev", is_dev=True)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_case(db: Session, dev_user: User, name: str = "Test Case") -> Case:
    c = Case(owner_id=dev_user.id, name=name, description="test", status="DRAFT")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@pytest.fixture()
def client(engine):
    """FastAPI test client with get_db bound to the per-test engine."""
    from fastapi.testclient import TestClient

    from app.api.deps import ensure_dev_user
    from app.api.replay import get_session_factory
    from app.database import get_db
    from app.main import app as fastapi_app

    factory = sessionmaker(bind=engine, expire_on_commit=False)

    # Seed the DEV user up front: otherwise the first request opens a write
    # transaction on the request session, which blocks the runtime provider
    # override store (separate connection) from writing to the same DB file.
    with factory() as seed:
        ensure_dev_user(seed)
        seed.commit()

    def _override_get_db():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    fastapi_app.dependency_overrides[get_session_factory] = lambda: factory
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
