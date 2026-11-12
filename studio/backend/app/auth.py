"""Password hashing (PBKDF2, no extra deps), JWT sessions and API-key auth."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

_ITER = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITER).hex()
    return f"pbkdf2${_ITER}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters)).hex()
        return hmac.compare_digest(calc, digest)
    except ValueError:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.ACCESS_TOKEN_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def current_user(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    t: str | None = Query(default=None, description="JWT for <audio>/<video> tags that cannot send headers"),
    db: Session = Depends(get_db),
) -> User:
    """Accepts `Authorization: Bearer <jwt>` (web app), `X-API-Key` (integrations) or `?t=<jwt>` (media tags)."""
    user: User | None = None
    if t and not authorization:
        authorization = "Bearer " + t
    if x_api_key:
        user = db.query(User).filter(User.api_key == x_api_key).first()
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        try:
            data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except jwt.PyJWTError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "جلسة غير صالحة، سجّل الدخول من جديد")
        user = db.get(User, data.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "غير مصرح")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "صلاحيات الأدمن مطلوبة")
    return user
