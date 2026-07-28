"""Authenticated bulk-ingest endpoint for the bookmarklet bridge.

The bookmarklet runs inside the operator's real, logged-in Etimad browser
session (where the WAF does not block them), reads the tenders JSON the page
already has, and POSTs it here with a shared secret. The server normalizes and
upserts exactly like the automated fetcher.

This is an OPERATOR tool, not a per-user feature: one secret, held by whoever
runs the imports. It is a bridge until a lawful central feed is in place.
"""
from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.etimad_api import normalize_item
from app.services.ingest import ingest_batch

logger = get_logger(__name__)
settings = get_settings()
router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


class PushIn(BaseModel):
    # The raw Etimad item objects, exactly as the page received them.
    items: list[dict[str, Any]]
    snapshot_id: str | None = None


def _authorized(token: str | None) -> bool:
    expected = settings.INGEST_TOKEN
    if not expected:
        return False  # feature disabled until a token is configured
    return bool(token) and hmac.compare_digest(token, expected)


@router.post("/push")
async def push(body: PushIn, x_ingest_token: str | None = Header(default=None)):
    if not _authorized(x_ingest_token):
        raise HTTPException(401, "invalid or missing ingest token")

    normalized = [n for n in (normalize_item(i) for i in body.items) if n]
    if not normalized:
        # Surface field-map drift instead of silently importing nothing.
        sample_keys = list(body.items[0].keys())[:20] if body.items else []
        raise HTTPException(
            422,
            f"received {len(body.items)} items but normalized 0 — field names "
            f"may have changed. First item keys: {sample_keys}",
        )

    async with AsyncSessionLocal() as session:
        stats = await ingest_batch(session, normalized, snapshot_id=body.snapshot_id)
    logger.info("ingest_push", received=len(body.items), **stats)
    return {"received": len(body.items), "normalized": len(normalized), **stats}
