from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from ..config import PLANS, settings
from ..models import CreditLedger, User


def plan_of(user: User) -> dict:
    return PLANS.get(user.plan, PLANS["free"])


def refresh_monthly(db: Session, user: User) -> None:
    """Top the balance up to the plan allowance once every 30 days."""
    reset = user.credits_reset_at
    if reset.tzinfo is None:
        reset = reset.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - reset >= timedelta(days=30):
        allowance = plan_of(user)["monthly_credits"]
        if user.credits < allowance:
            db.add(CreditLedger(user_id=user.id, delta=allowance - user.credits, reason="monthly_reset"))
            user.credits = allowance
        user.credits_reset_at = datetime.now(timezone.utc)
        db.commit()


def tts_cost(text: str) -> int:
    return max(1, round(len(text) / 1000 * settings.CREDITS_PER_1000_CHARS))


def video_cost(seconds: float) -> int:
    return max(1, round(seconds * settings.CREDITS_PER_VIDEO_SECOND))


def charge(db: Session, user: User, amount: int, reason: str, job_id: str = "") -> None:
    """Atomically reserve `amount` credits *before* any paid work happens.
    A single conditional UPDATE means concurrent requests cannot overdraw the balance."""
    refresh_monthly(db, user)
    result = db.execute(
        update(User).where(User.id == user.id, User.credits >= amount)
        .values(credits=User.credits - amount)
    )
    if result.rowcount != 1:
        db.rollback()
        db.refresh(user)
        raise HTTPException(402, f"رصيدك {user.credits} كريدت والعملية تحتاج {amount}. رقّي باقتك.")
    db.add(CreditLedger(user_id=user.id, delta=-amount, reason=reason, job_id=job_id))
    db.commit()
    db.refresh(user)


def refund(db: Session, user: User, amount: int, job_id: str, reason: str = "refund_failed_job") -> None:
    db.execute(update(User).where(User.id == user.id).values(credits=User.credits + amount))
    db.add(CreditLedger(user_id=user.id, delta=amount, reason=reason, job_id=job_id))
    db.commit()
    db.refresh(user)
