"""Subscription status, plan catalogue, and activation requests.

Online card payment is intentionally NOT wired yet: real billing requires the
company's payment-provider account (Stripe / Moyasar / Tap). The activation
endpoint records the upgrade request so sales can complete it manually, and
the code path is shaped so a checkout-session call slots in later.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import AuthContext, get_auth, require_admin
from app.core.logging import get_logger
from app.core.plans import PLANS, TRIAL_DAYS

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/plans")
async def plans():
    return {
        "trial_days": TRIAL_DAYS,
        "plans": [
            {
                "key": p.key,
                "name": p.name_ar,
                "price_sar_month": p.price_sar_month,
                "seats": p.seats,
                "proposals_per_month": p.proposals_per_month,
                "features": list(p.features_ar),
            }
            for p in PLANS.values()
        ],
    }


@router.get("/status")
async def status(auth: AuthContext = Depends(get_auth)):
    return {
        "company": auth.org.name,
        "subscription": auth.subscription,
        "trial_ends_at": auth.org.trial_ends_at.isoformat() if auth.org.trial_ends_at else None,
    }


class UpgradeIn(BaseModel):
    plan: str


@router.post("/upgrade-request")
async def upgrade_request(body: UpgradeIn, auth: AuthContext = Depends(require_admin)):
    if body.plan not in PLANS:
        return {"ok": False, "message": "خطة غير معروفة."}
    logger.info("upgrade_requested", org=str(auth.org.id), company=auth.org.name,
                requested_plan=body.plan, by=auth.user.email)
    return {
        "ok": True,
        "message": (
            "استلمنا طلب الترقية — سيتواصل فريق المبيعات لإتمام الدفع وتفعيل الخطة. "
            "الدفع الإلكتروني المباشر قادم قريبًا."
        ),
    }
