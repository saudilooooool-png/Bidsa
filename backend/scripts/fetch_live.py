"""Fetch live tenders from Etimad and load them into the Bidsa database.

Designed to run from a machine whose IP Etimad's WAF accepts (i.e. inside
Saudi Arabia) — cloud datacenter IPs get "Request Rejected". Writes straight
to the production Postgres (Neon), so results appear on the site immediately.

Quick start (from the backend/ directory):
    pip install -r requirements-fetch.txt
    set DATABASE_URL=postgresql://...neon.tech/neondb?sslmode=require   (Windows)
    export DATABASE_URL=...                                             (macOS/Linux)

    python scripts/fetch_live.py --dry-run     # fetch 1 page, print, no DB writes
    python scripts/fetch_live.py               # incremental fetch + ingest
    python scripts/fetch_live.py --full        # walk all pages (first backfill)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

if sys.version_info < (3, 10):  # the codebase uses 3.10+ syntax (X | None)
    sys.stderr.write(
        f"This script needs Python 3.10+ (you are on {sys.version.split()[0]}).\n"
        "يتطلب السكربت Python 3.10 أو أحدث — ثبّت 3.12 من python.org ثم شغّله بـ:  py -3.12 scripts/fetch_live.py\n")
    raise SystemExit(1)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):  # Arabic output on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")


async def run(args: argparse.Namespace) -> int:
    # Imports happen after DATABASE_URL is in the environment (settings cache).
    import httpx
    from sqlalchemy import func, select

    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.models.tender import Tender
    from app.services.etimad_api import (
        EtimadApiClient, _extract_items, normalize_item,
    )
    from app.services.ingest import ingest_batch

    settings = get_settings()

    # ---- probe page 1 with full diagnostics --------------------------------
    print("→ فحص أولي: صفحة واحدة من اعتماد ...")
    async with EtimadApiClient() as client:
        params = {
            "PageNumber": 1, "PageSize": settings.ETIMAD_PAGE_SIZE,
            "PublishDateId": settings.ETIMAD_PUBLISH_DATE_ID,
            "TenderCategory": settings.ETIMAD_TENDER_CATEGORY,
            "IsSearch": "true", "SortDirection": "DESC", "Sort": "SubmitionDate",
        }
        try:
            resp = await client._client.get(settings.ETIMAD_LIST_PATH, params=params)
        except httpx.HTTPError as exc:
            print(f"✗ فشل الاتصال بمنصة اعتماد: {exc}")
            return 1
        body = resp.text
        if resp.status_code != 200 or "Request Rejected" in body[:500]:
            print(f"✗ اعتماد رفضت الطلب (HTTP {resp.status_code}).")
            print("  إن ظهرت 'Request Rejected' فجدار الحماية يحجب عنوان IP هذا —")
            print("  شغّل السكربت من اتصال داخل السعودية.")
            print(f"  أول 300 حرف من الرد: {body[:300]!r}")
            return 1
        try:
            payload = resp.json()
        except ValueError:
            print("✗ الرد ليس JSON — أول 300 حرف:")
            print(f"  {body[:300]!r}")
            return 1

        raw_items = _extract_items(payload)
        normalized = [n for n in (normalize_item(i) for i in raw_items) if n]
        print(f"✓ اعتماد استجابت: {len(raw_items)} سجلًا خامًا، {len(normalized)} بعد التطبيع.")

        if raw_items and not normalized:
            print("\n⚠ التطبيع أسقط كل السجلات — أسماء الحقول تغيّرت على الأرجح.")
            print("  مفاتيح أول سجل خام (أرسلها للمطوّر لتحديث FIELD_MAP):")
            for k, v in raw_items[0].items():
                print(f"    {k}: {repr(v)[:60]}")
            return 1
        if isinstance(payload, dict) and not raw_items:
            print("⚠ لم يُعثر على قائمة سجلات — مفاتيح الرد:", list(payload.keys())[:10])
            return 1

        if normalized:
            sample = dict(normalized[0])
            sample.pop("raw", None)
            print("  عيّنة سجل مطبّع:")
            print(json.dumps(sample, ensure_ascii=False, indent=2)[:600])

        if args.dry_run:
            print("\n(وضع الفحص --dry-run: لا كتابة في قاعدة البيانات.)")
            return 0

        # ---- real fetch ----------------------------------------------------
        async with AsyncSessionLocal() as session:
            known = set((await session.execute(select(Tender.reference_number))).scalars().all())
        print(f"→ في القاعدة حاليًا: {len(known):,} منافسة. بدء الجلب "
              f"({'كامل' if args.full else 'تزايدي — يتوقف عند أول صفحة بلا جديد'}) ...")
        if args.full:
            items = await client.fetch_all(max_pages=args.max_pages)
            items = [t for t in items if t["reference_number"] not in known] or items
        else:
            items = await client.fetch_incremental(known, max_pages=args.max_pages)

    if not items:
        print("✓ لا سجلات جديدة منذ آخر جلب — كل شيء محدّث.")
        return 0

    async with AsyncSessionLocal() as session:
        stats = await ingest_batch(session, items)
        open_count = (await session.execute(
            select(func.count(Tender.id)).where(Tender.lifecycle_snapshot == "open")
        )).scalar_one()

    print(f"✓ اكتمل الإدخال: {stats['created']} جديدة، {stats['updated']} محدّثة.")
    print(f"✓ إجمالي المنافسات المفتوحة في القاعدة الآن: {open_count:,}")
    print("  افتح الموقع وجرّب المطابقة — الجديد يظهر فورًا.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="database URL (otherwise the DATABASE_URL env var)")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch one page and print it — no database writes")
    ap.add_argument("--full", action="store_true",
                    help="walk every page instead of stopping at the first known one")
    ap.add_argument("--max-pages", type=int, default=100)
    args = ap.parse_args()

    if args.db:
        os.environ["DATABASE_URL"] = args.db
    if not args.dry_run and not os.environ.get("DATABASE_URL"):
        ap.error("set DATABASE_URL (Neon URL) or pass --db, or use --dry-run")

    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
