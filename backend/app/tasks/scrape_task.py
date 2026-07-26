"""Background jobs: extract from the official API, ingest, and enrich."""
from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.tender import Tender
from app.services.enrich import TenderEnricher
from app.services.etimad_api import EtimadApiClient
from app.services.ingest import ingest_batch

logger = get_logger(__name__)


async def run_ingest_job(incremental: bool = True) -> dict:
    """Fetch tenders from Etimad's JSON API and upsert them."""
    async with AsyncSessionLocal() as session:
        known: set[str] = set()
        if incremental:
            known = set((await session.execute(select(Tender.reference_number))).scalars().all())

    async with EtimadApiClient() as client:
        items = await client.fetch_incremental(known) if incremental else await client.fetch_all()

    if not items:
        logger.info("ingest_no_new_items")
        return {"created": 0, "updated": 0, "total": 0}

    async with AsyncSessionLocal() as session:
        return await ingest_batch(session, items)


async def run_enrichment_job(limit: int = 50) -> dict:
    """Run AI enrichment on tenders that have no ai_summary yet."""
    enricher = TenderEnricher()
    if not enricher.enabled:
        logger.info("enrichment_skipped_no_openai_key")
        return {"enriched": 0}

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Tender).where(Tender.ai_summary.is_(None)).limit(limit)
        )).scalars().all()
        enriched = 0
        for tender in rows:
            if await enricher.enrich(tender):
                enriched += 1
        await session.commit()
    logger.info("enrichment_done", enriched=enriched)
    return {"enriched": enriched}
