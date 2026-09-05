"""Answer: which tenders had exactly ONE local bidder but MORE THAN ONE foreign
bidder, before the award (i.e. among all bidders on the competition).

This needs companies.is_local populated (see services/company_nationality.py);
the historical corpus has no nationality of its own. The query is exact: a
tender qualifies only when local_n == 1 AND foreign_n > 1 AND unknown_n == 0 —
otherwise "exactly one local" cannot be asserted. A coverage report prints
first so you can see whether enrichment is sufficient to trust the answer.

Usage:
    python scripts/analyze_local_vs_foreign.py --db postgresql+psycopg2://...
    python scripts/analyze_local_vs_foreign.py --db ... --include-unknowns  # looser
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

COVERAGE_SQL = text("""
    SELECT
      count(*)                                   AS companies,
      count(*) FILTER (WHERE is_local IS NOT NULL) AS classified,
      count(*) FILTER (WHERE is_local IS TRUE)   AS local,
      count(*) FILTER (WHERE is_local IS FALSE)  AS foreign
    FROM companies
""")

BID_COVERAGE_SQL = text("""
    SELECT count(*) AS bid_rows,
           count(*) FILTER (WHERE c.is_local IS NOT NULL) AS bids_classified
    FROM tender_bids tb JOIN companies c ON c.id = tb.company_id
""")

RESULT_SQL = """
    WITH per AS (
      SELECT tb.tender_id,
             count(*) FILTER (WHERE c.is_local IS TRUE)  AS local_n,
             count(*) FILTER (WHERE c.is_local IS FALSE) AS foreign_n,
             count(*) FILTER (WHERE c.is_local IS NULL)  AS unknown_n
      FROM tender_bids tb JOIN companies c ON c.id = tb.company_id
      GROUP BY tb.tender_id
    )
    SELECT t.reference_number, t.title, ag.name_ar AS agency,
           per.local_n, per.foreign_n, per.unknown_n
    FROM per
    JOIN tenders t ON t.id = per.tender_id
    LEFT JOIN agencies ag ON ag.id = t.agency_id
    WHERE per.local_n = 1 AND per.foreign_n > 1
      {unknown_clause}
    ORDER BY per.foreign_n DESC, t.reference_number
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=None, help="sync SQLAlchemy URL (default: settings.DATABASE_URL_SYNC)")
    ap.add_argument("--include-unknowns", action="store_true",
                    help="looser: allow tenders with unknown-nationality bidders (result is a lower bound)")
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    db_url = args.db
    if not db_url:
        from app.core.config import get_settings
        db_url = get_settings().DATABASE_URL_SYNC
    engine = create_engine(db_url)

    with engine.connect() as c:
        cov = c.execute(COVERAGE_SQL).one()
        bc = c.execute(BID_COVERAGE_SQL).one()
        print("=== nationality coverage ===")
        print(f"companies: {cov.companies:,} | classified: {cov.classified:,} "
              f"({100*cov.classified/max(cov.companies,1):.1f}%) | "
              f"local: {cov.local:,} | foreign: {cov.foreign:,}")
        print(f"bid rows: {bc.bid_rows:,} | with known nationality: {bc.bids_classified:,} "
              f"({100*bc.bids_classified/max(bc.bid_rows,1):.1f}%)")
        if cov.classified == 0:
            print("\n⚠ لا توجد جنسيات مُدخلة بعد — شغّل الإثراء أولًا "
                  "(services/company_nationality.py) ثم أعد التحليل.")
            return
        if not args.include_unknowns and bc.bids_classified < bc.bid_rows:
            print("\nملاحظة: بعض العارضين مجهولو الجنسية؛ النتيجة الصارمة تشمل فقط المنافسات "
                  "التي كل عارضيها معروفو الجنسية. استخدم --include-unknowns لحد أدنى تقريبي.")

        clause = "" if args.include_unknowns else "AND per.unknown_n = 0"
        rows = c.execute(text(RESULT_SQL.format(unknown_clause=clause))).all()

    print(f"\n=== المنافسات: محلية==1 و أجنبية>1 "
          f"({'يشمل مجهولين' if args.include_unknowns else 'صارم — بلا مجهولين'}) ===")
    print(f"العدد: {len(rows)}\n")
    for r in rows[: args.limit]:
        extra = f" | مجهول: {r.unknown_n}" if args.include_unknowns else ""
        print(f"- {r.reference_number} | {(r.agency or '—')[:40]}")
        print(f"    {(r.title or '')[:70]}")
        print(f"    محلية: {r.local_n} | أجنبية: {r.foreign_n}{extra}")


if __name__ == "__main__":
    main()
