"""Shared FastAPI dependencies: current user, org, and subscription gates."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import subscription_status
from app.core.security import decode_token
from app.db.session import get_session
from app.models.saas import Organization, User


@dataclass
class AuthContext:
    user: User
    org: Organization
    subscription: dict  # {state, plan, trial_days_left}


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:]
    raise HTTPException(401, "missing bearer token")


async def get_auth(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthContext:
    token = _bearer_token(request)
    try:
        payload = decode_token(token)
    except pyjwt.PyJWTError:
        raise HTTPException(401, "invalid or expired token")

    user = (await session.execute(
        select(User).where(User.id == uuid.UUID(payload["sub"]))
    )).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(401, "user not found or deactivated")
    org = (await session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )).scalar_one_or_none()
    if org is None:
        raise HTTPException(401, "organization not found")
    return AuthContext(user=user, org=org,
                       subscription=subscription_status(org.plan, org.trial_ends_at))


async def require_subscription(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    """Feature gate: active plan or a trial that has not expired."""
    if auth.subscription["state"] == "expired":
        raise HTTPException(
            402,
            "انتهت الفترة التجريبية. فعّل اشتراكًا من صفحة الإعدادات للاستمرار.",
        )
    return auth


async def require_admin(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    if auth.user.role not in ("owner", "admin"):
        raise HTTPException(403, "requires owner or admin role")
    return auth
