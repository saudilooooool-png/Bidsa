"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    alerts, auth, billing, ingest_push, intel, knowledge, proposals, team, tenders,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.tasks.scheduler import start_scheduler, stop_scheduler

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENABLE_SCHEDULER:
        start_scheduler()
    logger.info("app_started")
    yield
    stop_scheduler()
    logger.info("app_stopped")


app = FastAPI(title="Bidsa — Etimad Procurement Intelligence", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tenders.router)
app.include_router(intel.router)
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(team.router)
app.include_router(knowledge.router)
app.include_router(proposals.router)
app.include_router(ingest_push.router)
app.include_router(alerts.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
