"""REST endpoints for tenders + job triggers."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.tender import Tender
from app.schemas.tender import TenderOut, TenderPage
from app.tasks.scrape_task import run_ingest_job

router = APIRouter(prefix="/api/v1", tags=["tenders"])


@router.get("/tenders", response_model=TenderPage)
async def list_tenders(
    session: AsyncSession = Depends(get_session),
    search: str | None = Query(None, description="full-text search on title/description"),
    lifecycle: str | None = Query(None, description="live lifecycle: open/awarding/examination/awarded/cancelled/unknown"),
    agency_id: int | None = None,
    activity_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Tender)
    count_stmt = select(func.count()).select_from(Tender)

    if search:
        cond = Tender.search_vector.op("@@")(func.plainto_tsquery("simple", search))
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if agency_id is not None:
        stmt = stmt.where(Tender.agency_id == agency_id)
        count_stmt = count_stmt.where(Tender.agency_id == agency_id)
    if activity_id is not None:
        stmt = stmt.where(Tender.activity_id == activity_id)
        count_stmt = count_stmt.where(Tender.activity_id == activity_id)
    if lifecycle:
        # live classification comes from the SQL view (CURRENT_TIMESTAMP-driven)
        ids = (await session.execute(
            text("SELECT id FROM tenders_live WHERE lifecycle_status = :lc"), {"lc": lifecycle}
        )).scalars().all()
        stmt = stmt.where(Tender.id.in_(ids))
        count_stmt = count_stmt.where(Tender.id.in_(ids))

    total = (await session.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Tender.deadline.desc().nullslast()).limit(page_size).offset((page - 1) * page_size)
    items = (await session.execute(stmt)).scalars().all()
    return TenderPage(total=total, page=page, page_size=page_size, items=[TenderOut.model_validate(t) for t in items])


@router.get("/tenders/{tender_id}", response_model=TenderOut)
async def get_tender(tender_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    tender = (await session.execute(select(Tender).where(Tender.id == tender_id))).scalar_one_or_none()
    if not tender:
        raise HTTPException(status_code=404, detail="tender not found")
    return TenderOut.model_validate(tender)


@router.post("/ingest/run")
async def trigger_ingest(background: BackgroundTasks, incremental: bool = True):
    background.add_task(run_ingest_job, incremental)
    return {"status": "started", "mode": "incremental" if incremental else "full"}
