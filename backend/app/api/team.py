"""Team management: list, invite (direct-create), deactivate members."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_admin, require_subscription
from app.core.plans import entitlements
from app.core.security import hash_password
from app.db.session import get_session
from app.models.saas import User

router = APIRouter(prefix="/api/v1/team", tags=["team"])


@router.get("/members")
async def members(
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(User).where(User.organization_id == auth.org.id).order_by(User.created_at)
    )).scalars().all()
    seats = entitlements(auth.org.plan).seats
    return {
        "seats_limit": seats,
        "members": [
            {"id": str(u.id), "email": u.email, "full_name": u.full_name,
             "role": u.role, "is_active": u.is_active}
            for u in rows
        ],
    }


class MemberIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="member", pattern="^(member|admin)$")


@router.post("/members", status_code=201)
async def add_member(
    body: MemberIn,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    active_count = (await session.execute(
        select(func.count(User.id)).where(
            User.organization_id == auth.org.id, User.is_active.is_(True))
    )).scalar_one()
    limit = entitlements(auth.org.plan).seats
    if active_count >= limit:
        raise HTTPException(
            402, f"وصلت حد المستخدمين لخطتك ({limit}). رقِّ الخطة لإضافة المزيد.")

    exists = (await session.execute(
        select(User.id).where(User.email == body.email.lower())
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(409, "هذا البريد مسجّل بالفعل.")

    user = User(
        organization_id=auth.org.id,
        email=body.email.lower(),
        full_name=body.full_name.strip(),
        role=body.role,
        password_hash=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.delete("/members/{member_id}")
async def deactivate_member(
    member_id: uuid.UUID,
    auth: AuthContext = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    user = (await session.execute(
        select(User).where(User.id == member_id, User.organization_id == auth.org.id)
    )).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "member not found")
    if user.role == "owner":
        raise HTTPException(403, "لا يمكن تعطيل مالك الحساب.")
    user.is_active = False
    await session.commit()
    return {"ok": True}
