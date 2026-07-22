import hashlib
import hmac
import secrets
from typing import Annotated
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import Settings, get_settings
from .database import get_db, utcnow
from .models import Profile

COOKIE_NAME = "airspace_session"


def session_hash(token: str, settings: Settings) -> str:
    return hmac.new(
        settings.session_pepper.get_secret_value().encode(), token.encode(), hashlib.sha256
    ).hexdigest()


def new_session() -> str:
    return secrets.token_urlsafe(48)


def current_profile(
    token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Profile:
    if token is None:
        raise HTTPException(status_code=401, detail="This browser has no Airspace profile.")
    profile = db.scalar(
        select(Profile).where(
            Profile.session_hash == session_hash(token, settings), Profile.deleted_at.is_(None)
        )
    )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="The Airspace browser session is no longer valid."
        )
    profile.last_active_at = utcnow()
    db.commit()
    return profile


def require_admin(request: Request, settings: Settings = Depends(get_settings)) -> None:
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not supplied or not secrets.compare_digest(
        supplied, settings.admin_password.get_secret_value()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Administrator authentication required"
        )
