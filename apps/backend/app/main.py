from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.api import cases, providers, scenarios
from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.common import Message

app = FastAPI(title="BAKKE - Evidence-Constrained Hypothesis Intelligence", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(scenarios.router)
app.include_router(providers.router)


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