"""Shared query for the open-tenders feed and saved-search matching."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lookup import Activity, Agency, Region
from app.models.tender import Tender


def _sar(halalas: int | None) -> float | None:
    return round(halalas / 100, 2) if halalas is not None else None


async def _open_ids(session: AsyncSession) -> list:
    """IDs of tenders whose LIVE lifecycle is 'open' (deadline not elapsed)."""
    return (await session.execute(
        text("SELECT id FROM tenders_live WHERE lifecycle_status = 'open'")
    )).scalars().all()


def _base_query():
    return (
        select(
            Tender.id, Tender.reference_number, Tender.title, Tender.deadline,
            Tender.details_url, Tender.bids_count, Tender.win_amount_halalas,
            Agency.id, Agency.name_ar, Activity.id, Activity.name_ar,
            Region.id, Region.name_ar,
        )
        .outerjoin(Agency, Agency.id == Tender.agency_id)
        .outerjoin(Activity, Activity.id == Tender.activity_id)
        .outerjoin(Region, Region.id == Tender.region_id)
    )


def _row_to_dict(r, now: datetime) -> dict:
    deadline = r[3]
    days_left = None
    if deadline is not None:
        days_left = max(0, (deadline - now).days)
    return {
        "tender_id": str(r[0]), "reference_number": r[1], "title": r[2],
        "deadline": deadline.isoformat() if deadline else None,
        "days_left": days_left, "details_url": r[4], "bids_count": r[5],
        "agency_id": r[7], "agency": r[8],
        "activity_id": r[9], "activity": r[10],
        "region_id": r[11], "region": r[12],
    }


async def open_feed(
    session: AsyncSession, *,
    search: str | None = None,
    activity_id: int | None = None,
    region_id: int | None = None,
    agency_id: int | None = None,
    within_days: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Paginated feed of OPEN tenders with the given filters."""
    now = datetime.now().astimezone()
    conds = [Tender.id.in_(await _open_ids(session))]
    if search:
        conds.append(Tender.search_vector.op("@@")(func.plainto_tsquery("simple", search)))
    if activity_id is not None:
        conds.append(Tender.activity_id == activity_id)
    if region_id is not None:
        conds.append(Tender.region_id == region_id)
    if agency_id is not None:
        conds.append(Tender.agency_id == agency_id)
    if within_days is not None:
        conds.append(Tender.deadline <= now.replace(microsecond=0) + timedelta(days=within_days))

    total = (await session.execute(
        select(func.count()).select_from(Tender).where(*conds)
    )).scalar_one()
    rows = (await session.execute(
        _base_query().where(*conds)
        .order_by(Tender.deadline.asc().nullslast())
        .limit(page_size).offset((page - 1) * page_size)
    )).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [_row_to_dict(r, now) for r in rows],
    }


async def matches_for_search(
    session: AsyncSession, *, keywords: str | None,
    activity_id: int | None, region_id: int | None, limit: int = 25,
    since: datetime | None = None,
) -> list[dict]:
    """Open tenders matching a saved search; `since` limits to newly-added rows."""
    now = datetime.now().astimezone()
    conds = [Tender.id.in_(await _open_ids(session))]
    if keywords:
        conds.append(Tender.search_vector.op("@@")(func.plainto_tsquery("simple", keywords)))
    if activity_id is not None:
        conds.append(Tender.activity_id == activity_id)
    if region_id is not None:
        conds.append(Tender.region_id == region_id)
    if since is not None:
        conds.append(Tender.created_at >= since)
    rows = (await session.execute(
        _base_query().where(*conds).order_by(Tender.created_at.desc()).limit(limit)
    )).all()
    return [_row_to_dict(r, now) for r in rows]
