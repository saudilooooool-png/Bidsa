"""Authenticated Etimad session: capture-once, reuse, keep-alive.

The winning pattern against Etimad's F5/Shape WAF (confirmed by other projects
in the wild): you cannot solve the JavaScript challenge from a plain HTTP client
or a re-launched headless browser on every run. Instead —

  1. a REAL browser logs in ONCE and passes the challenge (login also unlocks the
     richer authenticated supplier endpoint),
  2. we persist the resulting cookie jar (F5 ``TSPD*`` + auth cookies),
  3. a plain httpx client reuses those cookies and a KEEP-ALIVE ping every ~60s
     keeps the F5 clearance warm so the jar stays valid for hours.

Hard constraint: F5 binds clearance to the client IP (and largely the User-Agent).
The reuse + keep-alive MUST run from the same machine/IP that captured the
cookies — your PC or a Saudi VPS, never a foreign cloud IP (Render/Vercel).

This module is meant to run LOCALLY (see scripts/fetch_live.py --login / --session).
Playwright is only needed for the one-time capture; the fetch loop is pure httpx.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.etimad_api import (
    NormalizedTender, WafChallenge, _extract_items, _looks_like_challenge,
    normalize_item,
)

logger = get_logger(__name__)
settings = get_settings()

# Pinned to match the capture browser — F5 clearance is largely UA-bound, so the
# reuse client must present the exact same User-Agent the cookies were issued to.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Any of these appearing in the jar means an authenticated session was captured.
_AUTH_COOKIE_HINTS = ("MobileAuthCookie", ".AspNetCore", "EtimadIdentity", ".AspNet.")


class CookieStore:
    """Persist / load the captured cookie jar (Playwright cookie shape + meta)."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.ETIMAD_COOKIE_FILE)

    def save(self, cookies: list[dict[str, Any]], *, method: str) -> None:
        payload = {
            "captured_at": time.time(),
            "method": method,
            "user_agent": _UA,
            "cookies": cookies,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        logger.info("etimad_cookies_saved", path=str(self.path), count=len(cookies))

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def cookie_pairs(self) -> dict[str, str]:
        data = self.load() or {}
        return {c["name"]: c["value"] for c in data.get("cookies", [])
                if c.get("name") and c.get("value") is not None}

    def age_seconds(self) -> float | None:
        data = self.load()
        if not data or "captured_at" not in data:
            return None
        return time.time() - float(data["captured_at"])

    def looks_authenticated(self) -> bool:
        names = set(self.cookie_pairs().keys())
        return any(any(h in n for n in names) for h in _AUTH_COOKIE_HINTS)


# --------------------------------------------------------------------------- #
# One-time capture via a real browser (Playwright)
# --------------------------------------------------------------------------- #
async def login_and_capture(
    store: CookieStore | None = None, *,
    username: str | None = None,
    password: str | None = None,
    headful: bool = True,
    manual_timeout: int = 300,
) -> dict[str, Any]:
    """Open a real browser, sign in, and persist the cookie jar.

    Flow (robust to Etimad's Nafath/OTP): navigate to the login page, prefill
    credentials when given, then WAIT (up to ``manual_timeout`` s) until an auth
    cookie appears — so you can approve Nafath on your phone or complete any step
    the site throws in. As soon as the session is authenticated we snapshot every
    cookie (incl. the F5 clearance cookie) and save it.

    Runs headful by default: a visible window is both easier for the human step
    and the hardest thing for F5 to fingerprint as a bot.
    """
    store = store or CookieStore()
    username = username if username is not None else settings.ETIMAD_USERNAME
    password = password if password is not None else settings.ETIMAD_PASSWORD

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "login capture needs playwright: "
            "pip install playwright && playwright install chromium") from exc

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=not headful,
            args=["--no-sandbox", "--disable-dev-shm-usage",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            locale="ar-SA", timezone_id="Asia/Riyadh",
            viewport={"width": 1366, "height": 768}, user_agent=_UA,
        )
        await context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome={runtime:{}};"
            "Object.defineProperty(navigator,'languages',{get:()=>['ar-SA','ar','en-US']});"
        )
        page = await context.new_page()
        await page.goto(settings.ETIMAD_LOGIN_URL, wait_until="domcontentloaded",
                        timeout=60_000)

        if username and password:
            await _try_prefill_credentials(page, username, password)

        # Poll the live jar until an auth cookie shows up (covers Nafath/OTP).
        deadline = time.monotonic() + manual_timeout
        captured: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            cookies = await context.cookies()
            names = {c["name"] for c in cookies}
            if any(any(h in n for n in names) for h in _AUTH_COOKIE_HINTS):
                captured = cookies
                break
            await asyncio.sleep(2)

        if not captured:
            captured = await context.cookies()  # save whatever we have (F5 at least)
            logger.warning("etimad_login_no_auth_cookie",
                           hint="saved F5/session cookies but no auth cookie detected")

        await browser.close()

    store.save(captured, method="browser_login")
    return {
        "cookies": len(captured),
        "authenticated": store.looks_authenticated(),
        "path": str(store.path),
    }


async def _try_prefill_credentials(page: Any, username: str, password: str) -> None:
    """Best-effort credential prefill; selectors vary, so fail soft to manual."""
    user_selectors = [
        "input[name='UserName']", "input#UserName", "input[name='username']",
        "input[type='text']:not([type='hidden'])", "input[name*='user' i]",
    ]
    pass_selectors = ["input[type='password']", "input[name='Password']", "input#Password"]
    try:
        for sel in user_selectors:
            el = await page.query_selector(sel)
            if el:
                await el.fill(username)
                break
        for sel in pass_selectors:
            el = await page.query_selector(sel)
            if el:
                await el.fill(password)
                break
        # Submit via the password field's form (Enter) — selector-agnostic.
        pw_el = await page.query_selector("input[type='password']")
        if pw_el:
            await pw_el.press("Enter")
        logger.info("etimad_credentials_prefilled")
    except Exception as exc:  # noqa: BLE001 - manual completion still works
        logger.warning("etimad_prefill_failed", error=str(exc))


# --------------------------------------------------------------------------- #
# Reuse: plain-HTTP fetch with the saved cookies + keep-alive
# --------------------------------------------------------------------------- #
class SessionApiClient:
    """Fetcher (fetch_page/_pace) backed by a persisted, kept-alive cookie jar.

    Plugs into ``full_fetch`` / ``incremental_fetch`` exactly like EtimadApiClient
    and BrowserFetcher, but issues plain httpx calls with the captured cookies and
    hits the authenticated supplier endpoint by default.
    """

    def __init__(self, store: CookieStore | None = None, *,
                 list_path: str | None = None) -> None:
        self._store = store or CookieStore()
        self._list_path = list_path or settings.ETIMAD_SUPPLIER_LIST_PATH
        self._keepalive_task: asyncio.Task | None = None
        self._client = httpx.AsyncClient(
            base_url=settings.ETIMAD_BASE_URL,
            timeout=settings.ETIMAD_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": _UA,
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "ar-SA,ar;q=0.9,en-US;q=0.8",
                "Referer": settings.ETIMAD_BASE_URL + settings.ETIMAD_KEEPALIVE_PATH,
            },
            cookies=self._store.cookie_pairs(),
        )

    async def __aenter__(self) -> "SessionApiClient":
        if not self._store.cookie_pairs():
            raise RuntimeError(
                "no saved Etimad cookies — run the login capture first "
                "(scripts/fetch_live.py --login)")
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
        await self._client.aclose()

    async def _keepalive_loop(self) -> None:
        """Ping a light endpoint on a cadence so F5 clearance never goes cold."""
        while True:
            await asyncio.sleep(settings.ETIMAD_KEEPALIVE_SECONDS)
            try:
                resp = await self._client.get(
                    settings.ETIMAD_KEEPALIVE_PATH,
                    headers={"Accept": "text/html,application/xhtml+xml", "X-Requested-With": ""},
                )
                # Each cleared response rotates the TS* cookie; httpx's jar updates
                # in place, so the session stays warm automatically.
                logger.debug("etimad_keepalive", status=resp.status_code,
                             cookies=len(self._client.cookies))
            except httpx.HTTPError as exc:
                logger.warning("etimad_keepalive_failed", error=str(exc))

    def _params(self, page_number: int) -> dict[str, Any]:
        return {
            "PageNumber": page_number,
            "PageSize": settings.ETIMAD_PAGE_SIZE,
            "PublishDateId": settings.ETIMAD_PUBLISH_DATE_ID,
            "TenderCategory": settings.ETIMAD_TENDER_CATEGORY,
            "IsSearch": "true", "SortDirection": "DESC", "Sort": "SubmitionDate",
        }

    async def fetch_page_raw(self, page_number: int) -> list[dict[str, Any]]:
        resp = await self._client.get(self._list_path, params=self._params(page_number))
        if _looks_like_challenge(resp):
            raise WafChallenge(
                "session cookies were rejected by F5 — they likely expired or the "
                "fetch is running from a different IP than the capture. Re-run --login "
                f"on the SAME machine. (page {page_number}, url {resp.url})")
        resp.raise_for_status()
        return _extract_items(resp.json())

    async def fetch_page(self, page_number: int) -> list[NormalizedTender]:
        items = await self.fetch_page_raw(page_number)
        normalized = [n for n in (normalize_item(i) for i in items) if n]
        logger.info("etimad_session_page_fetched", page=page_number,
                    raw=len(items), kept=len(normalized))
        return normalized

    async def _pace(self) -> None:
        await asyncio.sleep(settings.ETIMAD_PAGE_DELAY_SECONDS)


def _keepalive_url(page_number: int) -> str:  # pragma: no cover - reserved for debugging
    return f"{settings.ETIMAD_BASE_URL}{settings.ETIMAD_KEEPALIVE_PATH}?{urlencode({'p': page_number})}"
