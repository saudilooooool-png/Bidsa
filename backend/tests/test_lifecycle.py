"""Parity tests for the Python classify_tender port.

Mirrors the SQL parity cases in db/schema.sql validation. Pure stdlib —
run with: python -m pytest, or `python backend/tests/test_lifecycle.py`.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.lifecycle import TenderSignals, classify_tender  # noqa: E402

NOW = datetime(2026, 7, 26, tzinfo=timezone.utc)
FUTURE = NOW + timedelta(days=5)
PAST = NOW - timedelta(days=5)

CASES = [
    ("future deadline, no proof -> open", TenderSignals("active", 4, FUTURE, None, False, None, 0), "open"),
    ("past deadline, no proof -> examination", TenderSignals("active", 4, PAST, None, False, None, 0), "examination"),
    ("winners present -> awarded", TenderSignals("active", 4, FUTURE, None, True, None, 1), "awarded"),
    ("winAmount present -> awarded", TenderSignals("active", 4, FUTURE, None, False, 100000, 2), "awarded"),
    ("future deadline + winAmount -> awarded", TenderSignals("active", 4, FUTURE, None, False, 500, 0), "awarded"),
    ("arabic cancelled -> cancelled", TenderSignals("ملغاة", None, FUTURE, None, False, None, 0), "cancelled"),
    ("arabic awarded -> awarded", TenderSignals("تمت الترسية", None, None, None, False, None, 0), "awarded"),
    ("arabic awarding -> awarding", TenderSignals("مرحلة الترسية", None, None, None, False, None, 0), "awarding"),
    ("examination term overrides open", TenderSignals("فتح العروض", None, FUTURE, None, False, None, 0), "examination"),
    ("open term no deadline -> open", TenderSignals("نشط", None, None, None, False, None, 0), "open"),
    ("statusId=4 no deadline -> open", TenderSignals("somethingelse", 4, None, None, False, None, 0), "open"),
    ("no evidence -> unknown", TenderSignals("weird", None, None, None, False, None, 0), "unknown"),
    ("diacritics -> awarded", TenderSignals("تَمّت الترسية", None, None, None, False, None, 0), "awarded"),
]


def test_lifecycle_parity():
    for label, sig, expected in CASES:
        got, _basis = classify_tender(sig, as_of=NOW)
        assert got == expected, f"{label}: expected {expected}, got {got}"


if __name__ == "__main__":
    failures = 0
    for label, sig, expected in CASES:
        got, basis = classify_tender(sig, as_of=NOW)
        ok = got == expected
        failures += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {got:<12} {label}")
    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)
