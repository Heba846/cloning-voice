"""Plans + a manual-activation flow that fits the Egyptian market (Vodafone Cash / InstaPay /
bank transfer confirmed over WhatsApp). Stripe/Paymob webhooks plug into `activate_plan`."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import admin_user, current_user
from ..config import PLANS, settings
from ..db import get_db
from ..models import CreditLedger, User
from ..schemas import AdminCreditsIn, PlanChangeIn

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
def plans():
    return PLANS


def activate_plan(db: Session, user: User, plan: str) -> None:
    if plan not in PLANS:
        raise HTTPException(400, "باقة غير معروفة")
    user.plan = plan
    allowance = PLANS[plan]["monthly_credits"]
    db.add(CreditLedger(user_id=user.id, delta=allowance, reason=f"plan_activate:{plan}"))
    user.credits += allowance
    db.commit()


@router.post("/request-upgrade")
def request_upgrade(data: PlanChangeIn, user: User = Depends(current_user)):
    """Returns the WhatsApp deep-link the client uses to send proof of payment."""
    if data.plan not in PLANS:
        raise HTTPException(400, "باقة غير معروفة")
    p = PLANS[data.plan]
    wa = settings.PUBLIC_URL  # placeholder so the frontend can build the message
    msg = (f"أهلاً، عايزة أفعّل باقة {p['name']} ({p['price_egp']} جنيه/شهر) على {settings.APP_NAME}.\n"
           f"الإيميل: {user.email}\nرقم العملية: ")
    return {"plan": data.plan, "price_egp": p["price_egp"], "message": msg, "site": wa}


@router.post("/admin/activate")
def admin_activate(data: AdminCreditsIn, plan: str = "", admin: User = Depends(admin_user),
                   db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == data.user_email.lower()).first()
    if not u:
        raise HTTPException(404, "المستخدم غير موجود")
    if plan:
        activate_plan(db, u, plan)
    if data.delta:
        u.credits += data.delta
        db.add(CreditLedger(user_id=u.id, delta=data.delta, reason=data.reason))
        db.commit()
    return {"email": u.email, "plan": u.plan, "credits": u.credits}


@router.get("/admin/users")
def admin_users(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [{"email": u.email, "name": u.name, "plan": u.plan, "credits": u.credits,
             "voices": len(u.voices), "jobs": len(u.jobs), "created_at": u.created_at.isoformat()}
            for u in db.query(User).order_by(User.created_at.desc()).all()]


@router.get("/ledger")
def ledger(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(CreditLedger).filter(CreditLedger.user_id == user.id).order_by(
        CreditLedger.created_at.desc()).limit(50)
    return [{"delta": r.delta, "reason": r.reason, "job_id": r.job_id, "at": r.created_at.isoformat()}
            for r in rows]
