"""Map NormalizedTender records onto the relational schema and upsert.

Responsibilities:
  * resolve/create lookup rows (agency, activity, type, region)
  * parse Arabic/ISO dates and money (-> exact halalas)
  * classify lifecycle (Python port, agrees with the SQL view)
  * upsert tenders by reference_number
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.lookup import Activity, Agency, Region, TenderType
from app.models.tender import Tender
from app.services.etimad_api import NormalizedTender
from app.services.lifecycle import TenderSignals, classify_tender
from app.services.money import to_halalas

logger = get_logger(__name__)

_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%d/%m/%Y %H:%M", "%d/%m/%Y", "%d-%m-%Y",
)


def parse_date(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    # Etimad sometimes returns /Date(1699999999000)/ millisecond epochs
    if text.startswith("/Date(") and text.endswith(")/"):
        try:
            ms = int(text[6:-2].split("+")[0].split("-")[0])
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        except (ValueError, IndexError):
            return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


async def _get_or_create(session: AsyncSession, model, name: str | None, *, external_id: str | None = None):
    """Resolve a lookup row by external_id or name_ar, creating it if absent."""
    if not name:
        return None
    name = str(name).strip()
    if hasattr(model, "external_id") and external_id:
        row = (await session.execute(select(model).where(model.external_id == str(external_id)))).scalar_one_or_none()
        if row:
            return row
    row = (await session.execute(select(model).where(model.name_ar == name))).scalar_one_or_none()
    if row:
        return row
    kwargs = {"name_ar": name}
    if hasattr(model, "external_id") and external_id:
        kwargs["external_id"] = str(external_id)
    row = model(**kwargs)
    session.add(row)
    await session.flush()
    return row


async def upsert_tender(session: AsyncSession, item: NormalizedTender, *, snapshot_id: str | None = None) -> tuple[Tender, bool]:
    """Insert or update a tender. Returns (tender, created)."""
    ref = item["reference_number"]
    existing = (await session.execute(select(Tender).where(Tender.reference_number == ref))).scalar_one_or_none()

    agency = await _get_or_create(session, Agency, item.get("agency_name"))
    activity = await _get_or_create(session, Activity, item.get("activity_name"))
    ttype = await _get_or_create(session, TenderType, item.get("type_name"))
    region = await _get_or_create(session, Region, item.get("region_name")) if item.get("region_name") else None

    deadline = parse_date(item.get("deadline"))
    win_halalas = to_halalas(item.get("document_price"))  # note: booklet price, not award value
    status_text = item.get("status_text")
    status_id = item.get("status_id")
    try:
        status_id = int(status_id) if status_id is not None else None
    except (TypeError, ValueError):
        status_id = None

    category, basis = classify_tender(
        TenderSignals(
            status_text=status_text,
            status_id=status_id,
            deadline=deadline,
            has_winners=False,
            win_amount_halalas=None,   # booklet price is not award proof
            bids_count=0,
        )
    )

    target = existing or Tender(reference_number=ref)
    target.title = item["title"]
    target.agency_id = agency.id if agency else None
    target.activity_id = activity.id if activity else None
    target.type_id = ttype.id if ttype else None
    target.region_id = region.id if region else None
    target.status_text = status_text
    target.status_id = status_id
    target.deadline = deadline
    target.lifecycle_snapshot = category
    target.lifecycle_basis = basis
    target.currency = "SAR" if win_halalas is not None else target.currency
    target.source_snapshot_id = snapshot_id
    target.provenance = {"source": "etimad_official_api", "tenderId": item.get("tender_id")}
    target.freshness = {"scrapedAt": datetime.now(timezone.utc).isoformat()}

    if existing is None:
        session.add(target)
    return target, existing is None


async def ingest_batch(session: AsyncSession, items: list[NormalizedTender], *, snapshot_id: str | None = None) -> dict[str, int]:
    created = updated = 0
    for item in items:
        _, is_new = await upsert_tender(session, item, snapshot_id=snapshot_id)
        created += int(is_new)
        updated += int(not is_new)
    await session.commit()
    logger.info("ingest_batch_done", created=created, updated=updated, total=len(items))
    return {"created": created, "updated": updated, "total": len(items)}
