"""Response schemas for the procurement-intelligence endpoints.

Money convention: exact integer halalas plus a convenience SAR float
(rounded to 2 decimals) — the halalas value is the auditable source.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class OverviewOut(BaseModel):
    tenders: int
    awards: int
    total_award_halalas: int | None
    total_award_sar: float | None
    companies: int
    agencies: int
    avg_bidders: float | None
    corpus_deadline_min: datetime | None
    corpus_deadline_max: datetime | None


class AgencyRow(BaseModel):
    agency_id: int
    agency: str
    tenders: int
    total_award_halalas: int | None
    total_award_sar: float | None
    avg_bidders: float | None


class TopWinnerRow(BaseModel):
    company_id: int | None
    company: str | None
    wins: int
    total_award_halalas: int | None
    total_award_sar: float | None
    share_pct: float | None      # of the agency's total awarded value


class ActivityShareRow(BaseModel):
    activity_id: int | None
    activity: str | None
    tenders: int
    total_award_halalas: int | None
    total_award_sar: float | None


class AgencyProfileOut(BaseModel):
    agency_id: int
    agency: str
    tenders: int
    total_award_halalas: int | None
    total_award_sar: float | None
    avg_bidders: float | None
    single_bid_pct: float | None   # % of tenders decided with exactly one bid
    top_winners: list[TopWinnerRow]
    top_activities: list[ActivityShareRow]


class PricingBenchmarkOut(BaseModel):
    contracts: int
    avg_halalas: int | None
    median_halalas: int | None
    p25_halalas: int | None
    p75_halalas: int | None
    min_halalas: int | None
    max_halalas: int | None
    avg_sar: float | None
    median_sar: float | None
    avg_bidders: float | None
    filters: dict


class CompetitionRow(BaseModel):
    activity_id: int
    activity: str
    tenders: int
    avg_bidders: float | None
    single_bid_pct: float | None
    median_award_sar: float | None


class MatchmakingRow(BaseModel):
    tender_id: str
    reference_number: str
    title: str
    agency: str | None
    activity: str | None
    region: str | None
    winner_company_id: int | None
    winner: str | None
    award_halalas: int | None
    award_sar: float | None
    deadline: datetime | None
    details_url: str | None


class CompanySearchRow(BaseModel):
    company_id: int
    name: str
    wins: int
    total_award_halalas: int | None
    total_award_sar: float | None


class CompanyProfileOut(BaseModel):
    company_id: int
    name: str
    wins: int
    bids_participated: int
    win_rate_pct: float | None
    total_award_halalas: int | None
    total_award_sar: float | None
    top_agencies: list[AgencyRow]
    top_activities: list[ActivityShareRow]
