"""Primary extraction: Etimad's official JSON endpoint.

``/Tender/AllSupplierTendersForVisitorAsync`` returns paginated JSON, which is
far more robust than HTML scraping (no DOM-selector breakage, faster, lighter).
This client fetches pages and normalises each item into a source-agnostic
``NormalizedTender`` dict that ``ingest.py`` maps onto the ORM models.

IMPORTANT: Etimad occasionally renames JSON keys. The FIELD_MAP below is the
single place to adjust; ``_first`` tries several candidate keys so minor
renames degrade gracefully instead of dropping data. Validate against a live
response before production (couldn't be reached from this sandbox).
"""
from __future__ import annotations

from typing import Any, Iterable, TypedDict

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class NormalizedTender(TypedDict, total=False):
    reference_number: str
    tender_number: str | None
    title: str
    agency_name: str | None
    activity_name: str | None
    type_name: str | None
    region_name: str | None
    status_text: str | None
    status_id: int | None
    deadline: str | None            # ISO or raw; ingest parses
    submission_date: str | None
    document_price: str | None      # raw -> halalas in ingest
    tender_id: str | None
    raw: dict[str, Any]


# candidate JSON keys (first non-empty wins) -> normalized field
FIELD_MAP: dict[str, tuple[str, ...]] = {
    "reference_number": ("referenceNumber", "tenderReferenceNumber", "referenceNo"),
    "tender_number": ("tenderNumber", "tenderNo"),
    "title": ("tenderName", "tenderTitle", "name"),
    "agency_name": ("agencyName", "governmentAgency", "agency"),
    "activity_name": ("tenderActivityName", "activityName", "mainActivityName"),
    "type_name": ("tenderTypeName", "typeName"),
    "region_name": ("branchName", "regionName", "areaName"),
    "status_text": ("tenderStatusName", "statusName", "tenderStatus"),
    "status_id": ("tenderStatusId", "statusId"),
    "deadline": ("lastOfferPresentationDate", "offerPresentationDate", "lastEnqueryDate"),
    "submission_date": ("submitionDate", "submissionDate", "publishDate"),
    "document_price": ("condetionalBookletPrice", "conditionalBookletPrice", "bookletPrice"),
    "tender_id": ("tenderId", "tenderIdString", "id"),
}


def _first(item: dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", []):
            return value
    return None


def normalize_item(item: dict[str, Any]) -> NormalizedTender | None:
    ref = _first(item, FIELD_MAP["reference_number"]) or _first(item, FIELD_MAP["tender_id"])
    title = _first(item, FIELD_MAP["title"])
    if not ref or not title:
        return None
    result: NormalizedTender = {"reference_number": str(ref).strip(), "title": str(title).strip(), "raw": item}
    for field, keys in FIELD_MAP.items():
        if field in ("reference_number", "title"):
            continue
        value = _first(item, keys)
        if value is not None:
            result[field] = value  # type: ignore[literal-required]
    return result


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    """Etimad wraps the list under a data-ish key; be defensive about the shape."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "tenders", "items", "results", "aaData"):
            value = payload.get(key)
            if isinstance(value, list):
                return [x for x in value if isinstance(x, dict)]
    return []


class EtimadApiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ETIMAD_BASE_URL,
            timeout=settings.ETIMAD_TIMEOUT_SECONDS,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            },
        )

    async def __aenter__(self) -> "EtimadApiClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_page(self, page_number: int) -> list[NormalizedTender]:
        params = {
            "PageNumber": page_number,
            "PageSize": settings.ETIMAD_PAGE_SIZE,
            "PublishDateId": settings.ETIMAD_PUBLISH_DATE_ID,
            "TenderCategory": settings.ETIMAD_TENDER_CATEGORY,
            "IsSearch": "true",
            "SortDirection": "DESC",
            "Sort": "SubmitionDate",
        }
        resp = await self._client.get(settings.ETIMAD_LIST_PATH, params=params)
        resp.raise_for_status()
        items = _extract_items(resp.json())
        normalized = [n for n in (normalize_item(i) for i in items) if n]
        logger.info("etimad_page_fetched", page=page_number, raw=len(items), kept=len(normalized))
        return normalized

    async def fetch_all(self, max_pages: int | None = None) -> list[NormalizedTender]:
        max_pages = max_pages or settings.ETIMAD_MAX_PAGES
        out: list[NormalizedTender] = []
        for page in range(1, max_pages + 1):
            try:
                batch = await self.fetch_page(page)
            except Exception as exc:  # noqa: BLE001 - log and stop the run
                logger.error("etimad_page_failed", page=page, error=str(exc))
                break
            if not batch:
                break
            out.extend(batch)
        logger.info("etimad_fetch_all_done", total=len(out))
        return out

    async def fetch_incremental(self, known_refs: set[str], max_pages: int | None = None) -> list[NormalizedTender]:
        """Stop as soon as a page yields no unseen references (list is date-sorted)."""
        max_pages = max_pages or settings.ETIMAD_MAX_PAGES
        out: list[NormalizedTender] = []
        for page in range(1, max_pages + 1):
            try:
                batch = await self.fetch_page(page)
            except Exception as exc:  # noqa: BLE001
                logger.error("etimad_page_failed", page=page, error=str(exc))
                break
            if not batch:
                break
            fresh = [t for t in batch if t["reference_number"] not in known_refs]
            for t in fresh:
                known_refs.add(t["reference_number"])
            out.extend(fresh)
            if not fresh:
                logger.info("etimad_incremental_caught_up", stopped_at_page=page)
                break
        logger.info("etimad_incremental_done", new=len(out))
        return out
