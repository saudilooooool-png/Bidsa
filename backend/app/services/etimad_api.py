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
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt, wait_exponential,
)

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


class WafChallenge(Exception):
    """Etimad's F5 WAF answered with an HTML challenge instead of JSON."""


# Path browsers visit before the XHR fires; hitting it first collects the
# session cookies the WAF expects on the async endpoint.
WARMUP_PATH = "/Tender/AllTendersForVisitor"
CHALLENGE_RETRY_DELAYS = (5, 12, 25)  # seconds between challenge retries


def _looks_like_challenge(resp: httpx.Response) -> bool:
    ctype = resp.headers.get("content-type", "")
    if "json" in ctype:
        return False
    head = resp.text[:400].lstrip().lower()
    return head.startswith("<") or "request rejected" in head


class EtimadApiClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ETIMAD_BASE_URL,
            timeout=settings.ETIMAD_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": settings.ETIMAD_BASE_URL + WARMUP_PATH,
            },
        )
        self._warmed = False

    async def __aenter__(self) -> "EtimadApiClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    async def warmup(self) -> None:
        """Visit the HTML page like a browser so WAF session cookies are set."""
        try:
            await self._client.get(
                WARMUP_PATH,
                headers={"Accept": "text/html,application/xhtml+xml",
                         "X-Requested-With": ""},
            )
            self._warmed = True
            logger.info("etimad_warmup_done", cookies=len(self._client.cookies))
        except httpx.HTTPError as exc:
            logger.warning("etimad_warmup_failed", error=str(exc))

    async def _get_page_response(self, page_number: int) -> httpx.Response:
        params = {
            "PageNumber": page_number,
            "PageSize": settings.ETIMAD_PAGE_SIZE,
            "PublishDateId": settings.ETIMAD_PUBLISH_DATE_ID,
            "TenderCategory": settings.ETIMAD_TENDER_CATEGORY,
            "IsSearch": "true",
            "SortDirection": "DESC",
            "Sort": "SubmitionDate",
        }
        return await self._client.get(settings.ETIMAD_LIST_PATH, params=params)

    async def fetch_page_raw(self, page_number: int) -> list[dict[str, Any]]:
        """Fetch one page's raw item list, negotiating WAF challenges.

        On an HTML challenge: wait, re-warm the session cookies, retry with
        growing delays. Raises WafChallenge when every attempt is rejected.
        """
        import asyncio

        if not self._warmed:
            await self.warmup()
        attempts = len(CHALLENGE_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            resp = await self._get_page_response(page_number)
            if not _looks_like_challenge(resp):
                resp.raise_for_status()
                return _extract_items(resp.json())
            if attempt < len(CHALLENGE_RETRY_DELAYS):
                delay = CHALLENGE_RETRY_DELAYS[attempt]
                logger.warning("etimad_waf_challenge_retry",
                               page=page_number, attempt=attempt + 1, delay=delay)
                await asyncio.sleep(delay)
                await self.warmup()
        raise WafChallenge(
            f"WAF challenge persisted after {attempts} attempts on page {page_number}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type(httpx.HTTPError))
    async def fetch_page(self, page_number: int) -> list[NormalizedTender]:
        items = await self.fetch_page_raw(page_number)
        normalized = [n for n in (normalize_item(i) for i in items) if n]
        logger.info("etimad_page_fetched", page=page_number, raw=len(items), kept=len(normalized))
        return normalized

    async def _pace(self) -> None:
        """Polite delay between page requests — rapid-fire is what arms the WAF."""
        import asyncio
        await asyncio.sleep(settings.ETIMAD_PAGE_DELAY_SECONDS)

    async def fetch_all(self, max_pages: int | None = None) -> list[NormalizedTender]:
        return await full_fetch(self, max_pages)

    async def fetch_incremental(self, known_refs: set[str], max_pages: int | None = None) -> list[NormalizedTender]:
        return await incremental_fetch(self, known_refs, max_pages)


async def incremental_fetch(fetcher, known_refs: set[str],
                            max_pages: int | None = None) -> list[NormalizedTender]:
    """Walk date-sorted pages until one yields no unseen references.

    `fetcher` is any object exposing fetch_page(page) and _pace()
    (EtimadApiClient or BrowserFetcher).
    """
    max_pages = max_pages or settings.ETIMAD_MAX_PAGES
    out: list[NormalizedTender] = []
    for page in range(1, max_pages + 1):
        if page > 1:
            await fetcher._pace()
        try:
            batch = await fetcher.fetch_page(page)
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


async def full_fetch(fetcher, max_pages: int | None = None) -> list[NormalizedTender]:
    """Walk every page via any fetcher exposing fetch_page/_pace."""
    max_pages = max_pages or settings.ETIMAD_MAX_PAGES
    out: list[NormalizedTender] = []
    for page in range(1, max_pages + 1):
        if page > 1:
            await fetcher._pace()
        try:
            batch = await fetcher.fetch_page(page)
        except Exception as exc:  # noqa: BLE001
            logger.error("etimad_page_failed", page=page, error=str(exc))
            break
        if not batch:
            break
        out.extend(batch)
    logger.info("etimad_fetch_all_done", total=len(out))
    return out
