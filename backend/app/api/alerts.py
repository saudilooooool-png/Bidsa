"""Open-tenders feed + saved-search alerts (the competitor-parity core)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, require_subscription
from app.db.session import get_session
from app.models.saas import SavedSearch
from app.services.feed import matches_for_search, open_feed

router = APIRouter(prefix="/api/v1", tags=["alerts"])


# ---- open tenders feed (browse) --------------------------------------------
@router.get("/feed")
async def feed(
    session: AsyncSession = Depends(get_session),
    search: str | None = None,
    activity_id: int | None = None,
    region_id: int | None = None,
    agency_id: int | None = None,
    within_days: int | None = Query(None, ge=1, le=365),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return await open_feed(
        session, search=search, activity_id=activity_id, region_id=region_id,
        agency_id=agency_id, within_days=within_days, page=page, page_size=page_size,
    )


# ---- saved searches (alerts) -----------------------------------------------
class SearchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    keywords: str | None = None
    activity_id: int | None = None
    region_id: int | None = None
    notify_email: bool = True


def _out(s: SavedSearch) -> dict:
    return {
        "id": str(s.id), "name": s.name, "keywords": s.keywords,
        "activity_id": s.activity_id, "region_id": s.region_id,
        "notify_email": s.notify_email,
        "last_notified_at": s.last_notified_at.isoformat() if s.last_notified_at else None,
    }


@router.get("/alerts")
async def list_alerts(
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(SavedSearch).where(SavedSearch.organization_id == auth.org.id)
        .order_by(SavedSearch.created_at.desc())
    )).scalars().all()
    return [_out(s) for s in rows]


@router.post("/alerts", status_code=201)
async def create_alert(
    body: SearchIn,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    s = SavedSearch(
        organization_id=auth.org.id, created_by=auth.user.id, name=body.name.strip(),
        keywords=(body.keywords or None), activity_id=body.activity_id,
        region_id=body.region_id, notify_email=body.notify_email,
    )
    session.add(s)
    await session.commit()
    return _out(s)


@router.get("/alerts/{alert_id}/preview")
async def preview_alert(
    alert_id: uuid.UUID,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    s = (await session.execute(
        select(SavedSearch).where(SavedSearch.id == alert_id,
                                  SavedSearch.organization_id == auth.org.id)
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "alert not found")
    matches = await matches_for_search(
        session, keywords=s.keywords, activity_id=s.activity_id, region_id=s.region_id)
    return {"count": len(matches), "matches": matches}


@router.delete("/alerts/{alert_id}")
async def delete_alert(
    alert_id: uuid.UUID,
    auth: AuthContext = Depends(require_subscription),
    session: AsyncSession = Depends(get_session),
):
    s = (await session.execute(
        select(SavedSearch).where(SavedSearch.id == alert_id,
                                  SavedSearch.organization_id == auth.org.id)
    )).scalar_one_or_none()
    if s is None:
        raise HTTPException(404, "alert not found")
    await session.delete(s)
    await session.commit()
    return {"ok": True}
