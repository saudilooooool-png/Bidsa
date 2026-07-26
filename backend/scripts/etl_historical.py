"""ETL: load the historical awarded corpus (etimad-plus-viewer shards) into Postgres.

Reads data/awarded_details/00..63.json (55K+ awarded tenders with winners,
exact halalas amounts, and full bid ledgers) and populates the relational
warehouse: lookups, tenders, awards, award_winners, tender_bids.

Also produces a field-coverage report that states — with numbers — which
intelligence features the corpus can and cannot power.

Usage:
    # coverage report only (no DB needed)
    python scripts/etl_historical.py --data-dir ../etimad-plus-viewer/data --report-only

    # full load (idempotent; re-running updates in place)
    python scripts/etl_historical.py --data-dir ../etimad-plus-viewer/data \
        --db postgresql+psycopg2://bidsa:bidsa@localhost:5432/bidsa
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models import (  # noqa: E402
    Activity, Agency, Award, AwardWinner, Company, Region, Tender, TenderBid, TenderType,
)

SAUDI_TZ = timezone(timedelta(hours=3))
_FRACTION = re.compile(r"\.(\d{6})\d+")  # trim >6 fractional digits for fromisoformat
BATCH = 2000


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def parse_ts(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text_ = _FRACTION.sub(r".\1", str(value).strip())
    try:
        dt = datetime.fromisoformat(text_)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_deadline(value: Any) -> datetime | None:
    """Date-only deadlines mean end-of-day in Saudi time (mirrors the exporter)."""
    if value in (None, ""):
        return None
    text_ = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_):
        d = datetime.fromisoformat(text_)
        return d.replace(hour=23, minute=59, second=59, tzinfo=SAUDI_TZ)
    return parse_ts(text_)


def iter_shards(data_dir: Path) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    shard_dir = data_dir / "awarded_details"
    files = sorted(shard_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"no shards found under {shard_dir}")
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        yield f.stem, payload.get("records", [])


# --------------------------------------------------------------------------- #
# Coverage report
# --------------------------------------------------------------------------- #
FEATURE_FIELDS = (
    "componentDetails", "awardAnnouncedAt", "awardGroups", "groups", "awardState",
    "awardMode", "awardCompleteness", "duration", "contractDuration", "executionDuration",
)


def build_coverage(records_by_shard: list[tuple[str, list[dict]]]) -> dict[str, Any]:
    total = 0
    src = Counter()
    have = Counter()
    winners = Counter()
    money = Counter()
    years = Counter()
    bids_rows = 0
    companies: set[str] = set()
    lookups = {k: set() for k in ("agency", "activity", "type", "region")}

    for _, records in records_by_shard:
        for r in records:
            total += 1
            src[r.get("_source") or "unknown"] += 1
            for k in FEATURE_FIELDS:
                if r.get(k) not in (None, "", [], {}):
                    have[k] += 1
            w = r.get("winners") or []
            if w:
                winners["has_winners"] += 1
            if len(w) > 1:
                winners["multi_winner"] += 1
            if any(isinstance(x, dict) and x.get("awardHalalas") is not None for x in w):
                winners["winner_award_amount"] += 1
            if r.get("winAmountHalalas") is not None:
                money["winAmountHalalas"] += 1
            mc = (r.get("moneyConsistency") or {}).get("status")
            money[f"consistency_{mc}"] += 1
            years[str(r.get("deadline") or "")[:4] or "none"] += 1
            allb = r.get("allBids") or []
            bids_rows += len(allb)
            for b in allb:
                if isinstance(b, dict) and b.get("key"):
                    companies.add(b["key"])
            for k in lookups:
                if r.get(k):
                    lookups[k].add(r[k])

    return {
        "total": total, "sources": dict(src), "optional_fields": dict(have),
        "winners": dict(winners), "money": dict(money),
        "deadline_years": dict(sorted(years.items())),
        "bids_rows": bids_rows, "unique_companies": len(companies),
        "lookup_counts": {k: len(v) for k, v in lookups.items()},
    }


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


def render_report(cov: dict[str, Any]) -> str:
    t = cov["total"]
    w = cov["winners"]
    m = cov["money"]
    opt = cov["optional_fields"]

    def row(label: str, n: int) -> str:
        return f"| {label} | {n:,} | {pct(n, t)} |"

    verdict_ready = (
        "**جاهزة للإطلاق** — تغطية كاملة" if w.get("winner_award_amount", 0) == t
        else "تغطية جزئية"
    )
    lines = [
        "# تقرير تغطية المستودع التاريخي (Historical Corpus Coverage)",
        "",
        f"- إجمالي سجلات الترسية: **{t:,}**",
        f"- إجمالي صفوف العروض (allBids): **{cov['bids_rows']:,}**",
        f"- شركات فريدة (بعد التطبيع): **{cov['unique_companies']:,}**",
        f"- الجهات: {cov['lookup_counts']['agency']:,} · الأنشطة: {cov['lookup_counts']['activity']:,}"
        f" · الأنواع: {cov['lookup_counts']['type']:,} · المناطق/المدن: {cov['lookup_counts']['region']:,}",
        f"- سنوات المواعيد النهائية: {cov['deadline_years']}",
        f"- المصادر: {cov['sources']}",
        "",
        "## تغطية الحقول الحاسمة",
        "",
        "| الحقل | السجلات | التغطية |",
        "|---|---|---|",
        row("فائزون معروفون (winners)", w.get("has_winners", 0)),
        row("مبلغ ترسية لكل فائز (awardHalalas)", w.get("winner_award_amount", 0)),
        row("مبلغ إجمالي بالهللات (winAmountHalalas)", m.get("winAmountHalalas", 0)),
        row("تطابق مالي match", m.get("consistency_match", 0)),
        row("ترسية متعددة الفائزين", w.get("multi_winner", 0)),
        row("تاريخ إعلان الترسية (awardAnnouncedAt)", opt.get("awardAnnouncedAt", 0)),
        row("مدة العقد (duration/contractDuration)",
            opt.get("duration", 0) + opt.get("contractDuration", 0) + opt.get("executionDuration", 0)),
        row("componentDetails الرسمية", opt.get("componentDetails", 0)),
        "",
        "## الحكم على جاهزية ميزات الاستخبارات",
        "",
        f"1. **هيمنة الشركات لكل جهة (Buyer Intelligence — الفائزون):** {verdict_ready}.",
        f"2. **التسعير على مستوى العقد (نشاط × منطقة × جهة):** {verdict_ready}.",
        "3. **شدة المنافسة (عدد العروض لكل منافسة):** جاهزة — عدد العروض متوفر لكل السجلات.",
        "4. **شبكة مقاولي الباطن:** جاهزة — الفائزون الجدد بالمشاريع الكبرى قابلون للاستعلام فورًا.",
        "5. **سرعة الترسية لكل جهة:** ❌ **غير ممكنة من هذا المستودع** — لا يوجد تاريخ إعلان ترسية"
        " (awardAnnouncedAt = 0%). تتطلب الجلب الرسمي الدوري مستقبلًا.",
        "6. **التنبؤ بإعادة الطرح (Pre-RFP):** ❌ **غير ممكنة من هذا المستودع** — لا توجد مدد عقود"
        " (0%). تتطلب componentDetails من المسح الرسمي أو استخراجها من كراسات الشروط.",
        "",
        "> الخلاصة: أطلق الميزات 1–4 فورًا فوق هذا المستودع؛ الميزتان 5–6 تنتظران خط الجلب الرسمي.",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Load
# --------------------------------------------------------------------------- #
def chunks(rows: list[dict], size: int = BATCH) -> Iterator[list[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def load(engine, records_by_shard: list[tuple[str, list[dict]]], snapshot_id: str | None) -> dict[str, int]:
    stats = Counter()
    t0 = time.time()

    # ---- Pass 1: collect lookups + company registry across the corpus ------
    agencies: dict[str, None] = {}
    activities: dict[str, None] = {}
    ttypes: dict[str, None] = {}
    regions: dict[str, None] = {}
    companies: dict[str, str] = {}  # name_key -> display name (first seen)
    for _, records in records_by_shard:
        for r in records:
            if r.get("agency"):
                agencies.setdefault(str(r["agency"]).strip(), None)
            if r.get("activity"):
                activities.setdefault(str(r["activity"]).strip(), None)
            if r.get("type"):
                ttypes.setdefault(str(r["type"]).strip(), None)
            if r.get("region"):
                regions.setdefault(str(r["region"]).strip(), None)
            for b in (r.get("allBids") or []):
                if isinstance(b, dict) and b.get("company"):
                    key = str(b.get("key") or b["company"]).strip()
                    companies.setdefault(key, str(b["company"]).strip())

    with engine.begin() as conn:
        def upsert_named(table, names: list[str], conflict_col: str = "name_ar") -> None:
            rows = [{"name_ar": n} for n in names]
            for batch in chunks(rows):
                conn.execute(
                    pg_insert(table).values(batch).on_conflict_do_nothing(index_elements=[conflict_col])
                )

        upsert_named(Agency.__table__, list(agencies))
        upsert_named(Activity.__table__, list(activities))
        upsert_named(TenderType.__table__, list(ttypes))
        upsert_named(Region.__table__, list(regions))
        for batch in chunks([{"name_key": k, "name_ar": v} for k, v in companies.items()]):
            conn.execute(
                pg_insert(Company.__table__).values(batch).on_conflict_do_nothing(index_elements=["name_key"])
            )

        agency_ids = dict(conn.execute(select(Agency.name_ar, Agency.id)).all())
        activity_ids = dict(conn.execute(select(Activity.name_ar, Activity.id)).all())
        type_ids = dict(conn.execute(select(TenderType.name_ar, TenderType.id)).all())
        region_ids = dict(conn.execute(select(Region.name_ar, Region.id)).all())
        company_ids = dict(conn.execute(
            select(Company.name_key, Company.id).where(Company.name_key.is_not(None))
        ).all())
        stats.update(agencies=len(agency_ids), activities=len(activity_ids),
                     types=len(type_ids), regions=len(region_ids), companies=len(company_ids))

        # ---- Pass 2: tenders upsert ----------------------------------------
        all_refs: list[str] = []
        for shard_id, records in records_by_shard:
            rows = []
            for r in records:
                ref = str(r["ref"]).strip()
                all_refs.append(ref)
                rows.append({
                    "reference_number": ref,
                    "tender_number": r.get("num"),
                    "title": str(r.get("name") or "غير محدد"),
                    "details_url": r.get("url"),
                    "submitted_at": parse_ts(r.get("submit")),
                    "agency_id": agency_ids.get(str(r.get("agency") or "").strip()),
                    "activity_id": activity_ids.get(str(r.get("activity") or "").strip()),
                    "type_id": type_ids.get(str(r.get("type") or "").strip()),
                    "region_id": region_ids.get(str(r.get("region") or "").strip()),
                    "status_text": r.get("status"),
                    "deadline": parse_deadline(r.get("deadline")),
                    "lifecycle_snapshot": r.get("tenderCategory") or "awarded",
                    "lifecycle_basis": r.get("tenderCategoryBasis"),
                    "win_amount_halalas": r.get("winAmountHalalas"),
                    "currency": r.get("currency") or "SAR",
                    "bids_count": int(r.get("bids") or 0),
                    "has_winners": bool(r.get("winners")),
                    "component_details": {"branch": r.get("branch")} if r.get("branch") else None,
                    "freshness": {"firstSeen": r.get("firstSeen"), "lastSeen": r.get("lastSeen")},
                    "provenance": r.get("_provenance"),
                    "source_snapshot_id": snapshot_id,
                    "parser_version": "etl_historical_v1",
                })
            for batch in chunks(rows):
                ins = pg_insert(Tender.__table__).values(batch)
                upd = {c: ins.excluded[c] for c in (
                    "tender_number", "title", "details_url", "submitted_at", "agency_id",
                    "activity_id", "type_id", "region_id", "deadline", "lifecycle_snapshot",
                    "lifecycle_basis", "win_amount_halalas", "currency", "bids_count",
                    "has_winners", "component_details", "freshness", "provenance",
                    "source_snapshot_id", "parser_version",
                )}
                conn.execute(ins.on_conflict_do_update(index_elements=["reference_number"], set_=upd))
            stats["tenders"] += len(rows)
            print(f"  shard {shard_id}: {len(rows)} tenders upserted "
                  f"({stats['tenders']:,} total, {time.time()-t0:.0f}s)")

        tender_ids: dict[str, Any] = {}
        for batch in chunks([{"r": x} for x in all_refs], 10000):
            refs = [b["r"] for b in batch]
            tender_ids.update(conn.execute(
                select(Tender.reference_number, Tender.id).where(Tender.reference_number.in_(refs))
            ).all())

        # ---- Pass 3: awards / winners / bids (idempotent rebuild) ----------
        ids = list(tender_ids.values())
        for batch in chunks([{"i": x} for x in ids], 10000):
            sub = [b["i"] for b in batch]
            conn.execute(TenderBid.__table__.delete().where(TenderBid.tender_id.in_(sub)))
            conn.execute(AwardWinner.__table__.delete().where(AwardWinner.award_id.in_(
                select(Award.id).where(Award.tender_id.in_(sub))
            )))

        award_rows, seen_award_refs = [], set()
        for _, records in records_by_shard:
            for r in records:
                ref = str(r["ref"]).strip()
                if ref in seen_award_refs:
                    continue
                seen_award_refs.add(ref)
                award_rows.append({
                    "tender_id": tender_ids[ref],
                    "win_amount_halalas": r.get("winAmountHalalas"),
                    "currency": r.get("currency") or "SAR",
                    "money_consistency": r.get("moneyConsistency"),
                })
        for batch in chunks(award_rows):
            ins = pg_insert(Award.__table__).values(batch)
            conn.execute(ins.on_conflict_do_update(
                index_elements=["tender_id"],
                set_={c: ins.excluded[c] for c in ("win_amount_halalas", "currency", "money_consistency")},
            ))
        stats["awards"] = len(award_rows)

        award_ids = dict(conn.execute(select(Award.tender_id, Award.id)).all())

        winner_rows, bid_rows = [], []
        for _, records in records_by_shard:
            for r in records:
                ref = str(r["ref"]).strip()
                tid = tender_ids[ref]
                aid = award_ids.get(tid)
                for rank, wrec in enumerate((r.get("winners") or []), start=1):
                    if not isinstance(wrec, dict):
                        continue
                    key = str(wrec.get("key") or wrec.get("company") or "").strip()
                    winner_rows.append({
                        "award_id": aid,
                        "company_id": company_ids.get(key),
                        "award_halalas": wrec.get("awardHalalas"),
                        "rank": rank,
                        "raw": wrec,
                    })
                for brec in (r.get("allBids") or []):
                    if not isinstance(brec, dict):
                        continue
                    key = str(brec.get("key") or brec.get("company") or "").strip()
                    bid_rows.append({
                        "tender_id": tid,
                        "company_id": company_ids.get(key),
                        "bid_halalas": brec.get("bidHalalas"),
                        "is_winner": bool(brec.get("won")),
                        "raw": brec,
                    })
        for batch in chunks(winner_rows):
            conn.execute(AwardWinner.__table__.insert().values(batch))
        for batch in chunks(bid_rows):
            conn.execute(TenderBid.__table__.insert().values(batch))
        stats["award_winners"] = len(winner_rows)
        stats["tender_bids"] = len(bid_rows)

    stats["seconds"] = int(time.time() - t0)
    return dict(stats)


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, required=True, help="etimad-plus-viewer/data directory")
    ap.add_argument("--db", default=None, help="sync SQLAlchemy URL (default: settings.DATABASE_URL_SYNC)")
    ap.add_argument("--report-only", action="store_true", help="produce the coverage report, skip DB load")
    ap.add_argument("--report-out", type=Path, default=None, help="write the markdown report here")
    args = ap.parse_args()

    manifest = args.data_dir / "manifest.json"
    snapshot_id = None
    if manifest.is_file():
        snapshot_id = json.loads(manifest.read_text(encoding="utf-8")).get("snapshotId")

    print(f"reading shards from {args.data_dir/'awarded_details'} (snapshot={snapshot_id}) ...")
    records_by_shard = list(iter_shards(args.data_dir))
    cov = build_coverage(records_by_shard)
    report = render_report(cov)
    print(f"corpus: {cov['total']:,} tenders, {cov['bids_rows']:,} bids, "
          f"{cov['unique_companies']:,} companies")
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(report, encoding="utf-8")
        print(f"coverage report written to {args.report_out}")

    if args.report_only:
        print(report)
        return

    db_url = args.db
    if not db_url:
        from app.core.config import get_settings
        db_url = get_settings().DATABASE_URL_SYNC
    engine = create_engine(db_url)
    with engine.connect() as conn:
        missing = [t for t in ("tenders", "awards", "award_winners", "tender_bids")
                   if not conn.execute(text("SELECT to_regclass(:t)"), {"t": t}).scalar()]
    if missing:
        raise SystemExit(f"missing tables {missing}; run `alembic upgrade head` first")

    print("loading into database ...")
    stats = load(engine, records_by_shard, snapshot_id)
    print("\nDONE:", json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
