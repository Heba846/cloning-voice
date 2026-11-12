from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import create_token, current_user, hash_password, verify_password
from ..config import PLANS, settings
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, SignupIn, TokenOut, UserOut
from ..services import credits

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, name=u.name, plan=u.plan, credits=u.credits,
                   is_admin=u.is_admin, api_key=u.api_key, plan_info=credits.plan_of(u))


@router.post("/signup", response_model=TokenOut)
def signup(data: SignupIn, db: Session = Depends(get_db)):
    if not settings.ALLOW_SIGNUP:
        raise HTTPException(403, "التسجيل مغلق حالياً")
    if db.query(User).filter(User.email == data.email.lower()).first():
        raise HTTPException(409, "الإيميل مسجل بالفعل")
    first = db.query(User).count() == 0
    u = User(email=data.email.lower(), name=data.name, password_hash=hash_password(data.password),
             plan="free", credits=PLANS["free"]["monthly_credits"],
             is_admin=first or data.email.lower() == settings.ADMIN_EMAIL.lower())
    db.add(u)
    db.commit()
    return TokenOut(access_token=create_token(u))


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == data.email.lower()).first()
    if not u or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "بيانات الدخول غير صحيحة")
    return TokenOut(access_token=create_token(u))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    credits.refresh_monthly(db, user)
    return user_out(user)


@router.post("/rotate-key", response_model=UserOut)
def rotate_key(user: User = Depends(current_user), db: Session = Depends(get_db)):
    import secrets
    user.api_key = "sk_" + secrets.token_urlsafe(32)
    db.commit()
    return user_out(user)
