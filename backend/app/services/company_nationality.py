"""Company nationality enrichment.

The historical Etimad corpus records bidder NAMES only — no nationality field
exists anywhere in it (verified). So local-vs-foreign questions need
companies.nationality / companies.is_local filled from an authoritative source.
Three mechanisms, most-trustworthy first:

  1. import_from_file()  — authoritative mapping (name_key/cr -> nationality)
     obtained from Etimad's supplier registry or another official source.
  2. enrich_from_etimad() — pull each supplier's nationality from the
     authenticated supplier profile via a live --session (KSA IP). The exact
     endpoint/field is candidate-mapped and MUST be verified against a live
     response before trusting it (same discipline as etimad_api.FIELD_MAP).
  3. classify_by_name()  — offline bootstrap. ONLY flags near-certain foreign
     firms (Latin-script names). It never asserts "local" from an Arabic name,
     because Arabic-named ≠ Saudi (foreign firms register locally, and Saudi
     brands use words like «الأمريكية»/«الدولية»). Low coverage by design.

is_local semantics: True = Saudi, False = foreign, NULL = unknown (not yet
enriched). Analyses must treat NULL as unknown, never as local.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.lookup import Company

logger = get_logger(__name__)

_LATIN = re.compile(r"[A-Za-z]")


# --- 3. offline bootstrap (near-certain foreign only) ------------------------
def classify_by_name(name: str) -> dict[str, Any] | None:
    """Return {'nationality','is_local','confidence'} only when near-certain.

    Latin-script company names are foreign firms bidding under their own name.
    Everything else returns None (unknown) — deliberately, to avoid the false
    positives that make name-based nationality guessing unreliable.
    """
    if name and _LATIN.search(name):
        return {"nationality": "FOREIGN", "is_local": False, "confidence": "high"}
    return None


async def enrich_offline(session: AsyncSession) -> dict[str, int]:
    """Flag Latin-named companies as foreign; leave everyone else unknown."""
    rows = (await session.execute(
        select(Company.id, Company.name_ar, Company.name_en)
        .where(Company.is_local.is_(None))
    )).all()
    flagged = 0
    for cid, name_ar, name_en in rows:
        verdict = classify_by_name(name_ar or "") or classify_by_name(name_en or "")
        if verdict:
            await session.execute(update(Company).where(Company.id == cid).values(
                nationality=verdict["nationality"], is_local=verdict["is_local"]))
            flagged += 1
    await session.commit()
    logger.info("nationality_offline_enriched", flagged=flagged, scanned=len(rows))
    return {"flagged_foreign": flagged, "scanned": len(rows)}


# --- 1. authoritative import from a mapping file -----------------------------
async def import_from_file(session: AsyncSession, path: str | Path) -> dict[str, int]:
    """Apply an authoritative nationality mapping.

    File is JSON: a list of {"name_key"|"cr_number": ..., "nationality": "SA"|...,
    "is_local": true|false}. Matches by cr_number first, else name_key.
    """
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    applied = 0
    for r in records:
        nat, is_local = r.get("nationality"), r.get("is_local")
        if is_local is None and nat:
            is_local = str(nat).upper() in ("SA", "SAU", "SAUDI", "SAUDI ARABIA", "المملكة العربية السعودية")
        cond = None
        if r.get("cr_number"):
            cond = Company.cr_number == str(r["cr_number"])
        elif r.get("name_key"):
            cond = Company.name_key == str(r["name_key"])
        if cond is None:
            continue
        res = await session.execute(
            update(Company).where(cond).values(nationality=nat, is_local=is_local))
        applied += res.rowcount or 0
    await session.commit()
    logger.info("nationality_imported", applied=applied, records=len(records))
    return {"applied": applied, "records": len(records)}


# --- 2. authoritative pull from Etimad supplier profiles (live, verify) ------
# Candidate keys for the nationality field on a supplier profile response.
# UNVERIFIED — confirm against a real logged-in response before trusting, then
# prune to the correct key (mirrors etimad_api.FIELD_MAP discipline).
SUPPLIER_NATIONALITY_KEYS: tuple[str, ...] = (
    "nationality", "nationalityName", "countryName", "country",
    "establishmentCountry", "isLocal", "isSaudi",
)
# Supplier-profile endpoint candidates (also verify against a live session).
SUPPLIER_PROFILE_PATHS: tuple[str, ...] = (
    "/SupplierProfile/GetSupplierProfile",
    "/Supplier/Details",
)


def _extract_nationality(payload: dict[str, Any]) -> dict[str, Any] | None:
    for key in SUPPLIER_NATIONALITY_KEYS:
        if key in payload and payload[key] not in (None, ""):
            val = payload[key]
            if isinstance(val, bool):  # isLocal/isSaudi style
                return {"nationality": "SA" if val else "FOREIGN", "is_local": val}
            is_local = str(val).strip() in ("SA", "سعودي", "سعودية", "المملكة العربية السعودية", "Saudi Arabia")
            return {"nationality": str(val).strip(), "is_local": is_local}
    return None


async def enrich_from_etimad(session: AsyncSession, session_client: Any,
                             limit: int | None = None) -> dict[str, int]:
    """Fill nationality from Etimad supplier profiles via an authenticated client.

    Requires a live SessionApiClient (see etimad_session.py) running from a KSA
    IP. The endpoint/field are candidate-mapped above and MUST be verified
    against a real response first — this raises if none of the candidates match,
    dumping the payload keys so the maps can be corrected, rather than writing
    wrong data.
    """
    rows = (await session.execute(
        select(Company.id, Company.cr_number, Company.name_ar)
        .where(Company.is_local.is_(None), Company.cr_number.is_not(None))
        .limit(limit or 100000)
    )).all()
    filled, misses = 0, 0
    for cid, cr, name in rows:
        payload = await session_client.fetch_supplier_profile(cr)  # type: ignore[attr-defined]
        if not payload:
            misses += 1
            continue
        verdict = _extract_nationality(payload)
        if verdict is None:
            raise RuntimeError(
                "supplier nationality field not found — verify SUPPLIER_NATIONALITY_KEYS "
                f"against this payload's keys: {sorted(payload.keys())}")
        await session.execute(update(Company).where(Company.id == cid).values(
            nationality=verdict["nationality"], is_local=verdict["is_local"]))
        filled += 1
    await session.commit()
    logger.info("nationality_etimad_enriched", filled=filled, misses=misses)
    return {"filled": filled, "no_profile": misses, "scanned": len(rows)}
