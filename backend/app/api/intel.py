"""Procurement-intelligence endpoints (Phase 2).

Read-only aggregations over the historical warehouse loaded by
scripts/etl_historical.py. Four launch-ready features per the coverage
report (db/reports/historical_coverage.md):

  * buyer intelligence   -> /intel/agencies, /intel/agencies/{id}
  * pricing benchmarks   -> /intel/pricing
  * competition analysis -> /intel/competition
  * subcontractor radar  -> /intel/matchmaking
  * company profiles     -> /intel/companies, /intel/companies/{id}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.lookup import Activity, Agency, Company, Region
from app.models.tender import Award, AwardWinner, Tender, TenderBid
from app.schemas.intel import (
    ActivityShareRow, AgencyProfileOut, AgencyRow, CompanyProfileOut,
    CompanySearchRow, CompetitionRow, MatchmakingRow, OverviewOut,
    PricingBenchmarkOut, TopWinnerRow,
)

router = APIRouter(prefix="/api/v1/intel", tags=["intelligence"])


def sar(halalas: int | float | None) -> float | None:
    return round(halalas / 100, 2) if halalas is not None else None


_single_bid = func.avg(case((Tender.bids_count == 1, 1), else_=0).cast(Integer)) * 100


@router.get("/lookups")
async def lookups(session: AsyncSession = Depends(get_session)):
    """Activities and regions with tender counts — powers frontend filter menus."""
    acts = (await session.execute(
        select(Activity.id, Activity.name_ar, func.count(Tender.id))
        .join(Tender, Tender.activity_id == Activity.id)
        .group_by(Activity.id, Activity.name_ar)
        .order_by(func.count(Tender.id).desc())
    )).all()
    regions = (await session.execute(
        select(Region.id, Region.name_ar, func.count(Tender.id))
        .join(Tender, Tender.region_id == Region.id)
        .group_by(Region.id, Region.name_ar)
        .order_by(func.count(Tender.id).desc())
    )).all()
    return {
        "activities": [{"id": r[0], "name": r[1], "tenders": r[2]} for r in acts],
        "regions": [{"id": r[0], "name": r[1], "tenders": r[2]} for r in regions],
    }


@router.get("/overview", response_model=OverviewOut)
async def overview(session: AsyncSession = Depends(get_session)):
    t = (await session.execute(select(
        func.count(Tender.id),
        func.sum(Tender.win_amount_halalas),
        func.avg(Tender.bids_count),
        func.min(Tender.deadline),
        func.max(Tender.deadline),
    ))).one()
    awards = (await session.execute(select(func.count(Award.id)))).scalar_one()
    companies = (await session.execute(select(func.count(Company.id)))).scalar_one()
    agencies = (await session.execute(select(func.count(Agency.id)))).scalar_one()
    return OverviewOut(
        tenders=t[0], awards=awards,
        total_award_halalas=t[1], total_award_sar=sar(t[1]),
        companies=companies, agencies=agencies,
        avg_bidders=round(float(t[2]), 1) if t[2] is not None else None,
        corpus_deadline_min=t[3], corpus_deadline_max=t[4],
    )


@router.get("/agencies", response_model=list[AgencyRow])
async def agencies_ranked(
    session: AsyncSession = Depends(get_session),
    sort: str = Query("spend", pattern="^(spend|tenders|competition)$"),
    limit: int = Query(20, ge=1, le=100),
):
    spend = func.sum(Tender.win_amount_halalas)
    stmt = (
        select(Agency.id, Agency.name_ar, func.count(Tender.id).label("n"),
               spend.label("spend"), func.avg(Tender.bids_count).label("avg_bids"))
        .join(Tender, Tender.agency_id == Agency.id)
        .group_by(Agency.id, Agency.name_ar)
    )
    order = {"spend": spend.desc().nullslast(),
             "tenders": func.count(Tender.id).desc(),
             "competition": func.avg(Tender.bids_count).desc().nullslast()}[sort]
    rows = (await session.execute(stmt.order_by(order).limit(limit))).all()
    return [
        AgencyRow(agency_id=r[0], agency=r[1], tenders=r[2],
                  total_award_halalas=r[3], total_award_sar=sar(r[3]),
                  avg_bidders=round(float(r[4]), 1) if r[4] is not None else None)
        for r in rows
    ]


@router.get("/agencies/{agency_id}", response_model=AgencyProfileOut)
async def agency_profile(agency_id: int, session: AsyncSession = Depends(get_session)):
    head = (await session.execute(
        select(Agency.name_ar, func.count(Tender.id),
               func.sum(Tender.win_amount_halalas),
               func.avg(Tender.bids_count), _single_bid)
        .join(Tender, Tender.agency_id == Agency.id)
        .where(Agency.id == agency_id)
        .group_by(Agency.name_ar)
    )).one_or_none()
    if head is None:
        raise HTTPException(404, "agency not found or has no tenders")
    name, n, total, avg_bids, single_pct = head

    winner_total = func.sum(AwardWinner.award_halalas)
    winners = (await session.execute(
        select(Company.id, Company.name_ar, func.count().label("wins"), winner_total)
        .select_from(AwardWinner)
        .join(Award, Award.id == AwardWinner.award_id)
        .join(Tender, Tender.id == Award.tender_id)
        .outerjoin(Company, Company.id == AwardWinner.company_id)
        .where(Tender.agency_id == agency_id)
        .group_by(Company.id, Company.name_ar)
        .order_by(winner_total.desc().nullslast()).limit(10)
    )).all()

    acts = (await session.execute(
        select(Activity.id, Activity.name_ar, func.count(Tender.id),
               func.sum(Tender.win_amount_halalas).label("s"))
        .join(Tender, Tender.activity_id == Activity.id)
        .where(Tender.agency_id == agency_id)
        .group_by(Activity.id, Activity.name_ar)
        .order_by(func.sum(Tender.win_amount_halalas).desc().nullslast()).limit(10)
    )).all()

    return AgencyProfileOut(
        agency_id=agency_id, agency=name, tenders=n,
        total_award_halalas=total, total_award_sar=sar(total),
        avg_bidders=round(float(avg_bids), 1) if avg_bids is not None else None,
        single_bid_pct=round(float(single_pct), 1) if single_pct is not None else None,
        top_winners=[
            TopWinnerRow(company_id=w[0], company=w[1], wins=w[2],
                         total_award_halalas=w[3], total_award_sar=sar(w[3]),
                         share_pct=round(100 * w[3] / total, 1) if w[3] and total else None)
            for w in winners
        ],
        top_activities=[
            ActivityShareRow(activity_id=a[0], activity=a[1], tenders=a[2],
                             total_award_halalas=a[3], total_award_sar=sar(a[3]))
            for a in acts
        ],
    )


@router.get("/pricing", response_model=PricingBenchmarkOut)
async def pricing_benchmark(
    session: AsyncSession = Depends(get_session),
    activity_id: int | None = None,
    region_id: int | None = None,
    agency_id: int | None = None,
    activity_contains: str | None = Query(None, description="substring match on activity name"),
):
    conds = [Tender.win_amount_halalas.isnot(None)]
    if activity_id is not None:
        conds.append(Tender.activity_id == activity_id)
    if region_id is not None:
        conds.append(Tender.region_id == region_id)
    if agency_id is not None:
        conds.append(Tender.agency_id == agency_id)
    stmt = select(
        func.count(Tender.id),
        func.avg(Tender.win_amount_halalas),
        func.percentile_cont(0.5).within_group(Tender.win_amount_halalas),
        func.percentile_cont(0.25).within_group(Tender.win_amount_halalas),
        func.percentile_cont(0.75).within_group(Tender.win_amount_halalas),
        func.min(Tender.win_amount_halalas),
        func.max(Tender.win_amount_halalas),
        func.avg(Tender.bids_count),
    ).where(*conds)
    if activity_contains:
        stmt = stmt.join(Activity, Activity.id == Tender.activity_id).where(
            Activity.name_ar.ilike(f"%{activity_contains}%"))
    r = (await session.execute(stmt)).one()
    as_int = lambda v: int(v) if v is not None else None  # noqa: E731
    return PricingBenchmarkOut(
        contracts=r[0],
        avg_halalas=as_int(r[1]), median_halalas=as_int(r[2]),
        p25_halalas=as_int(r[3]), p75_halalas=as_int(r[4]),
        min_halalas=r[5], max_halalas=r[6],
        avg_sar=sar(as_int(r[1])), median_sar=sar(as_int(r[2])),
        avg_bidders=round(float(r[7]), 1) if r[7] is not None else None,
        filters={"activity_id": activity_id, "region_id": region_id,
                 "agency_id": agency_id, "activity_contains": activity_contains},
    )


@router.get("/competition", response_model=list[CompetitionRow])
async def competition_by_activity(
    session: AsyncSession = Depends(get_session),
    min_tenders: int = Query(100, ge=1),
    order: str = Query("least", pattern="^(least|most)$",
                       description="least = easiest markets first"),
    limit: int = Query(20, ge=1, le=100),
):
    avg_bids = func.avg(Tender.bids_count)
    stmt = (
        select(Activity.id, Activity.name_ar, func.count(Tender.id), avg_bids,
               _single_bid,
               func.percentile_cont(0.5).within_group(Tender.win_amount_halalas))
        .join(Tender, Tender.activity_id == Activity.id)
        .group_by(Activity.id, Activity.name_ar)
        .having(func.count(Tender.id) >= min_tenders)
        .order_by(avg_bids.asc() if order == "least" else avg_bids.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()
    return [
        CompetitionRow(
            activity_id=r[0], activity=r[1], tenders=r[2],
            avg_bidders=round(float(r[3]), 1) if r[3] is not None else None,
            single_bid_pct=round(float(r[4]), 1) if r[4] is not None else None,
            median_award_sar=sar(int(r[5])) if r[5] is not None else None,
        )
        for r in rows
    ]


@router.get("/matchmaking", response_model=list[MatchmakingRow])
async def subcontractor_radar(
    session: AsyncSession = Depends(get_session),
    min_award_sar: float = Query(10_000_000, ge=0, description="minimum award value in SAR"),
    activity_id: int | None = None,
    region_id: int | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    """Recent large-award winners — prime targets for subcontracting outreach."""
    conds = [AwardWinner.award_halalas >= int(min_award_sar * 100)]
    if activity_id is not None:
        conds.append(Tender.activity_id == activity_id)
    if region_id is not None:
        conds.append(Tender.region_id == region_id)
    rows = (await session.execute(
        select(Tender.id, Tender.reference_number, Tender.title,
               Agency.name_ar, Activity.name_ar, Region.name_ar,
               Company.id, Company.name_ar,
               AwardWinner.award_halalas, Tender.deadline, Tender.details_url)
        .select_from(AwardWinner)
        .join(Award, Award.id == AwardWinner.award_id)
        .join(Tender, Tender.id == Award.tender_id)
        .outerjoin(Agency, Agency.id == Tender.agency_id)
        .outerjoin(Activity, Activity.id == Tender.activity_id)
        .outerjoin(Region, Region.id == Tender.region_id)
        .outerjoin(Company, Company.id == AwardWinner.company_id)
        .where(*conds)
        .order_by(Tender.deadline.desc().nullslast())
        .limit(limit)
    )).all()
    return [
        MatchmakingRow(
            tender_id=str(r[0]), reference_number=r[1], title=r[2],
            agency=r[3], activity=r[4], region=r[5],
            winner_company_id=r[6], winner=r[7],
            award_halalas=r[8], award_sar=sar(r[8]),
            deadline=r[9], details_url=r[10],
        )
        for r in rows
    ]


@router.get("/companies", response_model=list[CompanySearchRow])
async def search_companies(
    session: AsyncSession = Depends(get_session),
    q: str = Query(..., min_length=2, description="company name substring"),
    limit: int = Query(20, ge=1, le=100),
):
    total = func.sum(AwardWinner.award_halalas)
    rows = (await session.execute(
        select(Company.id, Company.name_ar,
               func.count(AwardWinner.id).label("wins"), total)
        .outerjoin(AwardWinner, AwardWinner.company_id == Company.id)
        .where(Company.name_ar.ilike(f"%{q}%"))
        .group_by(Company.id, Company.name_ar)
        .order_by(total.desc().nullslast())
        .limit(limit)
    )).all()
    return [
        CompanySearchRow(company_id=r[0], name=r[1], wins=r[2],
                         total_award_halalas=r[3], total_award_sar=sar(r[3]))
        for r in rows
    ]


@router.get("/companies/{company_id}", response_model=CompanyProfileOut)
async def company_profile(company_id: int, session: AsyncSession = Depends(get_session)):
    company = (await session.execute(
        select(Company.name_ar).where(Company.id == company_id)
    )).scalar_one_or_none()
    if company is None:
        raise HTTPException(404, "company not found")

    wins, total = (await session.execute(
        select(func.count(AwardWinner.id), func.sum(AwardWinner.award_halalas))
        .where(AwardWinner.company_id == company_id)
    )).one()
    participated = (await session.execute(
        select(func.count(TenderBid.id)).where(TenderBid.company_id == company_id)
    )).scalar_one()

    top_agencies = (await session.execute(
        select(Agency.id, Agency.name_ar, func.count().label("n"),
               func.sum(AwardWinner.award_halalas).label("s"),
               func.avg(Tender.bids_count))
        .select_from(AwardWinner)
        .join(Award, Award.id == AwardWinner.award_id)
        .join(Tender, Tender.id == Award.tender_id)
        .join(Agency, Agency.id == Tender.agency_id)
        .where(AwardWinner.company_id == company_id)
        .group_by(Agency.id, Agency.name_ar)
        .order_by(func.sum(AwardWinner.award_halalas).desc().nullslast()).limit(5)
    )).all()

    top_acts = (await session.execute(
        select(Activity.id, Activity.name_ar, func.count(),
               func.sum(AwardWinner.award_halalas))
        .select_from(AwardWinner)
        .join(Award, Award.id == AwardWinner.award_id)
        .join(Tender, Tender.id == Award.tender_id)
        .join(Activity, Activity.id == Tender.activity_id)
        .where(AwardWinner.company_id == company_id)
        .group_by(Activity.id, Activity.name_ar)
        .order_by(func.sum(AwardWinner.award_halalas).desc().nullslast()).limit(5)
    )).all()

    return CompanyProfileOut(
        company_id=company_id, name=company,
        wins=wins, bids_participated=participated,
        win_rate_pct=round(100 * wins / participated, 1) if participated else None,
        total_award_halalas=total, total_award_sar=sar(total),
        top_agencies=[
            AgencyRow(agency_id=a[0], agency=a[1], tenders=a[2],
                      total_award_halalas=a[3], total_award_sar=sar(a[3]),
                      avg_bidders=round(float(a[4]), 1) if a[4] is not None else None)
            for a in top_agencies
        ],
        top_activities=[
            ActivityShareRow(activity_id=a[0], activity=a[1], tenders=a[2],
                             total_award_halalas=a[3], total_award_sar=sar(a[3]))
            for a in top_acts
        ],
    )
