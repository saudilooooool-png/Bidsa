"""Pydantic response schemas for the API."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TenderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_number: str
    title: str
    status_text: str | None = None
    deadline: datetime | None = None
    lifecycle_snapshot: str | None = None
    win_amount_halalas: int | None = None
    currency: str | None = None
    ai_summary: str | None = None
    risk_flags: list | None = None
    created_at: datetime


class TenderPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TenderOut]
