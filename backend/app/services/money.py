"""Exact money handling — mirrors export_warehouse.to_halalas().

Currency is stored as integer halalas (1 SAR = 100 halalas). Never use float
for money; parse via Decimal(str(value)) to avoid binary-float drift.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_halalas(value: object) -> int | None:
    """Convert a decimal-like value to exact integer halalas, or None."""
    if value in (None, "", "****") or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def halalas_to_sar(halalas: int | None) -> Decimal | None:
    if halalas is None:
        return None
    return (Decimal(halalas) / 100).quantize(Decimal("0.01"))
