from __future__ import annotations

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Force mock providers and an isolated DB before any app module reads settings.
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("VIDEO_GENERATION_PROVIDER", "mock")
os.environ.setdefault("STORAGE_PROVIDER", "local")

from app.models import Case, User  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture()
def engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
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
    return u


def make_case(db: Session, dev_user: User, name: str = "Test Case") -> Case:
    c = Case(owner_id=dev_user.id, name=name, description="test", status="DRAFT")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c
