"""APScheduler wiring for periodic extraction + enrichment."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tasks.scrape_task import run_digest_job, run_enrichment_job, run_ingest_job

logger = get_logger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def start_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        return
    scheduler.add_job(
        run_ingest_job, IntervalTrigger(minutes=settings.SCRAPER_INTERVAL_MINUTES),
        id="ingest_tenders", name="Ingest Etimad tenders (official API)",
        replace_existing=True, max_instances=1, kwargs={"incremental": True},
    )
    scheduler.add_job(
        run_enrichment_job, IntervalTrigger(minutes=max(settings.SCRAPER_INTERVAL_MINUTES // 2, 10)),
        id="enrich_tenders", name="AI enrichment", replace_existing=True, max_instances=1,
    )
    scheduler.add_job(
        run_digest_job, IntervalTrigger(hours=6),
        id="alert_digests", name="Tender-alert email digests",
        replace_existing=True, max_instances=1,
    )
    scheduler.start()
    logger.info("scheduler_started", interval=settings.SCRAPER_INTERVAL_MINUTES)


def stop_scheduler() -> None:
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown()
        logger.info("scheduler_stopped")
