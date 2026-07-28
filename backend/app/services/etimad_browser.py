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

def _body_text(raw: str) -> str:
    """Chromium wraps a raw JSON document in <pre>; unwrap when present."""
    s = raw.strip()
    if s.startswith("<pre") and "</pre>" in s:
        inner = s[s.index(">") + 1: s.rindex("</pre>")]
        return inner.strip()
    return s


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
        exe = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        # ETIMAD_HEADFUL=1 shows a real window — the hardest mode for a WAF to
        # flag as a bot, used as a fallback when headless is challenged.
        headless = os.environ.get("ETIMAD_HEADFUL", "") not in ("1", "true", "yes")
        launch_kwargs: dict[str, Any] = {
            "headless": headless,
            "args": [
                "--no-sandbox", "--disable-dev-shm-usage",
                # defeat the most common headless/automation fingerprints
                "--disable-blink-features=AutomationControlled",
            ],
        }
        if exe:
            launch_kwargs["executable_path"] = exe
        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        context = await self._browser.new_context(
            locale="ar-SA", timezone_id="Asia/Riyadh",
            viewport={"width": 1366, "height": 768},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
        )
        # Hide the automation tells F5 checks first (navigator.webdriver etc.).
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome={runtime:{}};"
            "Object.defineProperty(navigator,'languages',{get:()=>['ar-SA','ar','en-US']});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
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
        """Open the tenders page and let the WAF's challenge script run + settle.

        networkidle waits for the F5 challenge round-trip (which sets the
        clearance cookie) to finish before we start issuing JSON calls.
        """
        try:
            await self._page.goto(settings.ETIMAD_BASE_URL + WARMUP_PATH,
                                  wait_until="networkidle", timeout=60_000)
        except Exception:  # noqa: BLE001 - networkidle can time out; DOM is enough
            pass
        await asyncio.sleep(4)
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
        """Fetch a page by NAVIGATING to the API URL.

        A real navigation executes the F5 challenge's JavaScript (which sets the
        clearance cookie and reloads) — an in-page fetch() cannot, because it
        never runs the returned HTML's scripts. That was why every fetch()
        attempt saw the challenge forever.
        """
        url = self._page_url(page_number)
        attempts = len(CHALLENGE_RETRY_DELAYS) + 1
        for attempt in range(attempts):
            try:
                await self._page.goto(url, wait_until="networkidle", timeout=60_000)
            except Exception:  # noqa: BLE001 - networkidle may time out on the challenge
                pass
            raw = await self._page.evaluate("() => document.body ? document.body.innerText : ''")
            text = _body_text(raw)
            head = text[:400].lstrip().lower()
            is_challenge = (not text) or head.startswith("<") or "request rejected" in head \
                or "requested url was rejected" in head
            if not is_challenge:
                try:
                    return _extract_items(json.loads(text))
                except json.JSONDecodeError:
                    is_challenge = True  # not the JSON we expected — treat as challenge
            if attempt < len(CHALLENGE_RETRY_DELAYS):
                delay = CHALLENGE_RETRY_DELAYS[attempt]
                logger.warning("browser_waf_challenge_retry",
                               page=page_number, attempt=attempt + 1, delay=delay)
                # the goto above already ran the challenge JS; give it time to
                # set the clearance cookie, then retry the navigation.
                await asyncio.sleep(delay)
        raise WafChallenge(
            f"browser mode: challenge persisted after {attempts} attempts on page {page_number}")

    async def fetch_page(self, page_number: int) -> list[NormalizedTender]:
        items = await self.fetch_page_raw(page_number)
        normalized = [n for n in (normalize_item(i) for i in items) if n]
        logger.info("browser_page_fetched", page=page_number,
                    raw=len(items), kept=len(normalized))
        return normalized
