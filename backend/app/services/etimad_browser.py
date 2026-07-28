"""Browser-mode Etimad fetcher — defeats the F5 JavaScript challenge.

The WAF's challenge page computes a cookie in JavaScript; plain HTTP clients
can never pass it once armed. This fetcher drives a real headless Chromium:
it loads the tenders page (letting the challenge script run), then issues the
JSON calls with fetch() from inside that page — same origin, same cookies,
same browser fingerprint.

Requires:  pip install playwright  &&  playwright install chromium
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.parse import urlencode

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.etimad_api import (
    CHALLENGE_RETRY_DELAYS, WARMUP_PATH, NormalizedTender, WafChallenge,
    _extract_items, normalize_item,
)

logger = get_logger(__name__)
settings = get_settings()

_FETCH_JS = """
async (url) => {
  const r = await fetch(url, {
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      'Accept': 'application/json, text/javascript, */*; q=0.01',
    },
    credentials: 'same-origin',
  });
  return await r.text();
}
"""


class BrowserFetcher:
    """Same interface as EtimadApiClient (fetch_page / fetch_page_raw / _pace)."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._page = None

    async def __aenter__(self) -> "BrowserFetcher":
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "browser mode needs playwright: "
                "pip install playwright && playwright install chromium") from exc
        self._pw = await async_playwright().start()
        # Optional override for environments that ship their own Chromium
        # (e.g. a preinstalled binary); otherwise Playwright's managed build.
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        launch_kwargs: dict[str, Any] = {"headless": True,
                                         "args": ["--no-sandbox", "--disable-dev-shm-usage"]}
        if exe:
            launch_kwargs["executable_path"] = exe
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        context = await self._browser.new_context(
            locale="ar-SA", timezone_id="Asia/Riyadh",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        )
        self._page = await context.new_page()
        await self._load_warmup()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    async def _load_warmup(self) -> None:
        """Open the tenders page and give any challenge script time to settle."""
        await self._page.goto(settings.ETIMAD_BASE_URL + WARMUP_PATH,
                              wait_until="domcontentloaded", timeout=60_000)
        await asyncio.sleep(3)
        logger.info("browser_warmup_done", url=self._page.url)

    async def _pace(self) -> None:
        await asyncio.sleep(settings.ETIMAD_PAGE_DELAY_SECONDS)

    def _page_url(self, page_number: int) -> str:
        params = {
            "PageNumber": page_number,
            "PageSize": settings.ETIMAD_PAGE_SIZE,
            "PublishDateId": settings.ETIMAD_PUBLISH_DATE_ID,
            "TenderCategory": settings.ETIMAD_TENDER_CATEGORY,
            "IsSearch": "true", "SortDirection": "DESC", "Sort": "SubmitionDate",
        }
        return f"{settings.ETIMAD_BASE_URL}{settings.ETIMAD_LIST_PATH}?{urlencode(params)}"

    async def fetch_page_raw(self, page_number: int) -> list[dict[str, Any]]:
        attempts = len(CHALLENGE_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            text = await self._page.evaluate(_FETCH_JS, self._page_url(page_number))
            head = text[:400].lstrip().lower()
            if not (head.startswith("<") or "request rejected" in head):
                return _extract_items(json.loads(text))
            if attempt < len(CHALLENGE_RETRY_DELAYS):
                delay = CHALLENGE_RETRY_DELAYS[attempt]
                logger.warning("browser_waf_challenge_retry",
                               page=page_number, attempt=attempt + 1, delay=delay)
                await asyncio.sleep(delay)
                await self._load_warmup()
        raise WafChallenge(
            f"browser mode: challenge persisted after {attempts} attempts on page {page_number}")

    async def fetch_page(self, page_number: int) -> list[NormalizedTender]:
        items = await self.fetch_page_raw(page_number)
        normalized = [n for n in (normalize_item(i) for i in items) if n]
        logger.info("browser_page_fetched", page=page_number,
                    raw=len(items), kept=len(normalized))
        return normalized
