"""Registration, login, and session introspection."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth
from app.core.plans import TRIAL_DAYS
from app.core.security import create_token, hash_password, verify_password
from app.db.session import get_session
from app.models.saas import Organization, User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class SessionOut(BaseModel):
    token: str
    email: str
    full_name: str | None
    role: str
    company: str
    subscription: dict


@router.post("/register", response_model=SessionOut, status_code=201)
async def register(body: RegisterIn, session: AsyncSession = Depends(get_session)):
    exists = (await session.execute(
        select(User.id).where(User.email == body.email.lower())
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "هذا البريد مسجّل بالفعل — سجّل الدخول بدلًا من ذلك.")

    org = Organization(
        name=body.company_name.strip(),
        plan="trial",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=TRIAL_DAYS),
    )
    session.add(org)
    await session.flush()
    user = User(
        organization_id=org.id,
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        role="owner",
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()

    from app.core.plans import subscription_status
    return SessionOut(
        token=create_token(user_id=user.id, org_id=org.id, role=user.role),
        email=user.email, full_name=user.full_name, role=user.role,
        company=org.name,
        subscription=subscription_status(org.plan, org.trial_ends_at),
    )


@router.post("/login", response_model=SessionOut)
async def login(body: LoginIn, session: AsyncSession = Depends(get_session)):
    user = (await session.execute(
        select(User).where(User.email == body.email.lower())
    )).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "بيانات الدخول غير صحيحة.")
    org = (await session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )).scalar_one()

    from app.core.plans import subscription_status
    return SessionOut(
        token=create_token(user_id=user.id, org_id=org.id, role=user.role),
        email=user.email, full_name=user.full_name, role=user.role,
        company=org.name,
        subscription=subscription_status(org.plan, org.trial_ends_at),
    )


@router.get("/me")
async def me(auth: AuthContext = Depends(get_auth)):
    return {
        "email": auth.user.email,
        "full_name": auth.user.full_name,
        "role": auth.user.role,
        "company": auth.org.name,
        "subscription": auth.subscription,
    }
