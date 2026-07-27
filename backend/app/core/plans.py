"""Subscription plan catalogue and entitlement checks (single source of truth)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

TRIAL_DAYS = 14


@dataclass(frozen=True)
class Plan:
    key: str
    name_ar: str
    price_sar_month: int | None   # None => contact sales
    seats: int
    proposals_per_month: int | None  # None => unlimited
    features_ar: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "starter": Plan(
        key="starter", name_ar="الأساسية", price_sar_month=499, seats=3,
        proposals_per_month=10,
        features_ar=(
            "كل لوحات الاستخبارات",
            "مطابقة المناقصات من ملف الشركة",
            "10 مسودات RFP شهريًا",
            "3 مستخدمين",
        ),
    ),
    "pro": Plan(
        key="pro", name_ar="الاحترافية", price_sar_month=1499, seats=15,
        proposals_per_month=None,
        features_ar=(
            "كل مزايا الأساسية",
            "مسودات RFP غير محدودة",
            "15 مستخدمًا",
            "أولوية في الدعم",
        ),
    ),
    "enterprise": Plan(
        key="enterprise", name_ar="المنشآت", price_sar_month=None, seats=100,
        proposals_per_month=None,
        features_ar=(
            "كل مزايا الاحترافية",
            "واجهة API للبيانات (DaaS)",
            "مستخدمون غير محدودين عمليًا",
            "اتفاقية مستوى خدمة",
        ),
    ),
}

# The trial grants pro-level entitlements for TRIAL_DAYS.
TRIAL_ENTITLEMENTS = PLANS["pro"]


def subscription_status(plan: str, trial_ends_at: datetime | None) -> dict:
    """Return {state, plan, trial_days_left} where state in active|trial|expired."""
    now = datetime.now(timezone.utc)
    if plan in PLANS:
        return {"state": "active", "plan": plan, "trial_days_left": None}
    if trial_ends_at is not None and trial_ends_at > now:
        return {
            "state": "trial", "plan": "trial",
            "trial_days_left": max(0, (trial_ends_at - now).days),
        }
    return {"state": "expired", "plan": plan, "trial_days_left": 0}


def entitlements(plan: str) -> Plan:
    return PLANS.get(plan, TRIAL_ENTITLEMENTS)
