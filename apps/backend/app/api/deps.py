from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Case, GeneratedVideo, Scenario, User

settings = get_settings()

_DEV_EMAIL = "dev@bakke.local"
_DEV_NAME = "BAKKE Developer (DEV MODE)"


def ensure_dev_user(db: Session) -> User:
    user = db.query(User).filter_by(email=_DEV_EMAIL).first()
    if not user:
        user = User(email=_DEV_EMAIL, display_name=_DEV_NAME, is_dev=True)
        db.add(user)
        db.flush()
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Authentication.

    Production: verifies a Firebase ID token from the Authorization header.
    Development: returns a built-in DEV user (clearly labelled). Evidence is
    never sent anywhere unless providers are explicitly configured.
    """
    auth_header = request.headers.get("Authorization", "")
    if settings.FIREBASE_PROJECT_ID and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY:
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            import firebase_admin
            from firebase_admin import credentials, auth as fb_auth

            if not firebase_admin._apps:
                cred = credentials.Certificate(
                    {
                        "project_id": settings.FIREBASE_PROJECT_ID,
                        "client_email": settings.FIREBASE_CLIENT_EMAIL,
                        "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
                    }
                )
                firebase_admin.initialize_app(cred)
            token = auth_header.removeprefix("Bearer ").strip()
            decoded = fb_auth.verify_id_token(token)
            user = db.query(User).filter_by(firebase_uid=decoded.get("uid")).first()
            if not user:
                user = User(
                    email=decoded.get("email", "firebase@bakke.local"),
                    display_name=decoded.get("name", "Firebase User"),
                    firebase_uid=decoded.get("uid", ""),
                )
                db.add(user)
                db.flush()
            return user
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"invalid firebase token: {exc}")
    if settings.is_production:
        raise HTTPException(status_code=503, detail="authentication not configured")
    return ensure_dev_user(db)


def ensure_owned_case(db: Session, case_id: str, user: User) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="case not found")
    if case.owner_id != user.id:
        raise HTTPException(status_code=403, detail="not allowed to access this case")
    return case


def get_owned_case(case_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Case:
    return ensure_owned_case(db, case_id, user)


def get_owned_scenario(
    scenario_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Scenario:
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")
    ensure_owned_case(db, scenario.case_id, user)
    return scenario


def get_owned_video(video_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GeneratedVideo:
    video = db.get(GeneratedVideo, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    ensure_owned_case(db, video.case_id, user)
    return video