"""Faithful Python port of etimad-plus-viewer's ``classify_tender``.

Kept dependency-free and side-effect-free so it can be reused by the ingest
pipeline, the API layer, and tests. The equivalent SQL lives in
``db/schema.sql`` (``classify_tender_lifecycle`` + the ``tenders_live`` view);
both implementations were verified to agree on the same parity cases.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone

# --- Status-term sets (verbatim from scripts/export_warehouse.py) -------------
AWARDED_STATUS_TERMS = ("awarded", "award announced", "تمت الترسية", "تم الترسية", "مرساة")
AWARDING_STATUS_TERMS = ("awarding stage", "award stage", "مرحلة الترسية", "تحت الترسية")
CANCELLED_STATUS_TERMS = ("cancelled", "canceled", "withdrawn", "ملغ", "الغيت", "سحبت")
EXAMINATION_STATUS_TERMS = (
    "closed", "expired", "evaluation", "examination", "under review",
    "مغلق", "منته", "فحص", "تقييم", "فتح العروض", "تحت المراجعة",
)
OPEN_STATUS_TERMS = ("active", "open", "published", "نشط", "مفتوح")

_DIACRITICS = re.compile(r"[ً-ٰٟ]")
_WHITESPACE = re.compile(r"\s+")

LIFECYCLE_VALUES = ("open", "awarding", "examination", "awarded", "cancelled", "unknown")


def normalized_status(value: object) -> str:
    """NFC-normalise, lowercase, strip Arabic diacritics, collapse whitespace."""
    text = unicodedata.normalize("NFC", str(value or "")).lower()
    text = _DIACRITICS.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def _has_term(status: str, terms: tuple[str, ...]) -> bool:
    return any(term in status for term in terms)


@dataclass
class TenderSignals:
    """Minimal inputs the classifier needs (mirrors the SQL function params)."""
    status_text: str | None = None
    status_id: int | None = None
    deadline: datetime | None = None
    award_state: str | None = None
    has_winners: bool = False
    win_amount_halalas: int | None = None
    bids_count: int = 0


def classify_tender(sig: TenderSignals, *, as_of: datetime | None = None) -> tuple[str, str]:
    """Return ``(lifecycle_category, evidence_basis)``.

    Precedence matches the source exactly:
    award proof -> cancelled -> awarded -> awarding -> deadline vs as_of ->
    examination -> open -> unknown.
    """
    as_of = as_of or datetime.now(timezone.utc)
    s = normalized_status(sig.status_text)

    bid_zero = sig.bids_count == 0 and not sig.has_winners and sig.win_amount_halalas is None
    future_no_proof = (
        sig.deadline is not None
        and sig.deadline >= as_of
        and sig.win_amount_halalas is None
        and bid_zero
    )
    award_announced = (
        sig.award_state == "announced"
        or sig.has_winners
        or sig.win_amount_halalas is not None
        or _has_term(s, AWARDED_STATUS_TERMS)
    ) and not future_no_proof

    if award_announced:
        return "awarded", "award_evidence"
    if _has_term(s, CANCELLED_STATUS_TERMS):
        return "cancelled", "official_status_cancelled"
    if _has_term(s, AWARDED_STATUS_TERMS):
        return "awarded", "official_status_awarded"
    if _has_term(s, AWARDING_STATUS_TERMS):
        return "awarding", "official_status_awarding_stage"
    if sig.deadline is not None:
        if sig.deadline >= as_of and not _has_term(s, EXAMINATION_STATUS_TERMS):
            return "open", "deadline_not_elapsed"
        return "examination", "deadline_elapsed_or_terminal_status"
    if _has_term(s, EXAMINATION_STATUS_TERMS):
        return "examination", "official_status_terminal"
    if _has_term(s, OPEN_STATUS_TERMS) or sig.status_id == 4:
        return "open", "official_active_status_without_deadline"
    return "unknown", "insufficient_lifecycle_evidence"
