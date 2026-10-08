from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.adapters.providers import validate_provider_types
from app.api import cases, providers, replay, scenarios
from app.api.deps import get_current_user
from app.config import ConfigError, get_settings, validate_settings
from app.database import get_db
from app.models import User
from app.schemas.common import Message

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail clearly on invalid configuration.

    Production refuses to start with invalid settings (no silent fallback to
    mocks, no wildcard CORS, no dev auth). Development logs the same problems
    as warnings so the stack stays runnable while misconfigured.
    """
    settings = get_settings()
    errors = validate_settings(settings) + validate_provider_types()
    if errors:
        if settings.is_production:
            raise ConfigError(errors)
        for err in errors:
            logger.warning("configuration: %s", err)
    yield


settings = get_settings()

app = FastAPI(
    title="BAKKE - Evidence-Constrained Hypothesis Intelligence",
    version="0.1.0",
    lifespan=lifespan,
)

_origins = settings.cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(scenarios.router)
app.include_router(providers.router)
app.include_router(replay.router)


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    from sqlalchemy import text

    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "database": db_ok}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "is_dev": user.is_dev}


@app.get("/", response_model=Message)
def root() -> Message:
    return Message(message="BAKKE API is running. Evidence-constrained hypothesis intelligence.")
