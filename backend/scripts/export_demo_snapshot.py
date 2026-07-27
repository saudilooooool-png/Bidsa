"""Export a static demo snapshot of the intel API into the frontend.

Produces frontend/src/data/demo/*.json so the dashboard can run in
"demo mode" with zero backend (e.g. a Vercel import with no API_URL set).
Endpoint-shaped payloads are captured through the real ASGI app to
guarantee parity with live mode; the pricing benchmark matrix is computed
directly in SQL (GROUPING SETS) because it covers all filter combinations.

Usage:
    DATABASE_URL=postgresql+asyncpg://... python3 scripts/export_demo_snapshot.py \
        --out ../frontend/src/data/demo
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

PROFILE_COUNT = 24        # agency + company profiles included in the demo
COMPANY_LIST = 300        # searchable company rows
MATCHMAKING_FLOOR_SAR = 10_000_000
PAIR_MIN_CONTRACTS = 5    # pricing cells smaller than this are omitted


async def capture(out: Path) -> None:
    from app.db.session import AsyncSessionLocal
    from app.main import app

    out.mkdir(parents=True, exist_ok=True)

    def dump(name: str, payload) -> None:
        path = out / f"{name}.json"
        # default=float covers SQL Decimal aggregates
        path.write_text(json.dumps(payload, ensure_ascii=False, default=float), encoding="utf-8")
        print(f"  {name}.json  {path.stat().st_size:,} bytes")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://demo"
    ) as c:
        async def get(path: str):
            r = await c.get(path)
            r.raise_for_status()
            return r.json()

        dump("overview", await get("/api/v1/intel/overview"))
        dump("lookups", await get("/api/v1/intel/lookups"))

        # union of the three sort orders so demo sorting is faithful in-page
        seen: dict[int, dict] = {}
        for sort in ("spend", "tenders", "competition"):
            for row in await get(f"/api/v1/intel/agencies?sort={sort}&limit=100"):
                seen.setdefault(row["agency_id"], row)
        dump("agencies", list(seen.values()))

        spend_top = await get("/api/v1/intel/agencies?sort=spend&limit=" + str(PROFILE_COUNT))
        agency_profiles = {}
        for row in spend_top:
            aid = row["agency_id"]
            agency_profiles[str(aid)] = await get(f"/api/v1/intel/agencies/{aid}")
        dump("agency_profiles", agency_profiles)

        # competition: full activity table (min filter applied client-side)
        dump("competition", await get("/api/v1/intel/competition?min_tenders=50&order=most&limit=100"))

        dump("matchmaking", await get(
            f"/api/v1/intel/matchmaking?min_award_sar={MATCHMAKING_FLOOR_SAR}&limit=100"
        ))

        # top companies by awarded value — search corpus + profile set
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(text("""
                SELECT c.id, c.name_ar, count(w.id) AS wins,
                       sum(w.award_halalas) AS total
                FROM companies c
                JOIN award_winners w ON w.company_id = c.id
                GROUP BY c.id, c.name_ar
                ORDER BY sum(w.award_halalas) DESC NULLS LAST
                LIMIT :n
            """), {"n": COMPANY_LIST})).all()
        companies = [
            {
                "company_id": r[0], "name": r[1], "wins": r[2],
                "total_award_halalas": r[3],
                "total_award_sar": round(r[3] / 100, 2) if r[3] is not None else None,
            }
            for r in rows
        ]
        dump("companies", companies)

        company_profiles = {}
        for row in companies[:PROFILE_COUNT]:
            cid = row["company_id"]
            company_profiles[str(cid)] = await get(f"/api/v1/intel/companies/{cid}")
        dump("company_profiles", company_profiles)

        # pricing matrix: overall / per-activity / per-region / pairs
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(text("""
                SELECT activity_id, region_id,
                       count(*) AS contracts,
                       avg(win_amount_halalas)::bigint AS avg_h,
                       (percentile_cont(0.5) WITHIN GROUP (ORDER BY win_amount_halalas))::bigint AS med_h,
                       (percentile_cont(0.25) WITHIN GROUP (ORDER BY win_amount_halalas))::bigint AS p25_h,
                       (percentile_cont(0.75) WITHIN GROUP (ORDER BY win_amount_halalas))::bigint AS p75_h,
                       min(win_amount_halalas) AS min_h,
                       max(win_amount_halalas) AS max_h,
                       round(avg(bids_count), 1) AS avg_bidders
                FROM tenders
                WHERE win_amount_halalas IS NOT NULL
                GROUP BY GROUPING SETS ((), (activity_id), (region_id), (activity_id, region_id))
            """))).all()
        pricing: dict[str, dict] = {}
        for r in rows:
            aid, rid, n = r[0], r[1], r[2]
            if aid is not None and rid is not None and n < PAIR_MIN_CONTRACTS:
                continue
            key = f"a{aid or ''}|r{rid or ''}"
            pricing[key] = {
                "contracts": n,
                "avg_halalas": r[3], "median_halalas": r[4],
                "p25_halalas": r[5], "p75_halalas": r[6],
                "min_halalas": r[7], "max_halalas": r[8],
                "avg_sar": round(r[3] / 100, 2) if r[3] is not None else None,
                "median_sar": round(r[4] / 100, 2) if r[4] is not None else None,
                "avg_bidders": float(r[9]) if r[9] is not None else None,
            }
        dump("pricing", pricing)

    print("demo snapshot complete ->", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path,
                    default=Path(__file__).resolve().parents[2] / "frontend/src/data/demo")
    args = ap.parse_args()
    asyncio.run(capture(args.out))


if __name__ == "__main__":
    main()
