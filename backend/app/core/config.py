"""Application settings loaded from environment / .env via pydantic-settings."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database (UTF8 database is REQUIRED: norm_status() uses normalize()) ---
    DATABASE_URL: str = "postgresql+asyncpg://bidsa:bidsa@localhost:5432/bidsa"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://bidsa:bidsa@localhost:5432/bidsa"

    # --- Etimad official API (primary extraction source) ---
    ETIMAD_BASE_URL: str = "https://tenders.etimad.sa"
    # AllSupplierTendersForVisitorAsync returns structured JSON (not HTML).
    ETIMAD_LIST_PATH: str = "/Tender/AllSupplierTendersForVisitorAsync"
    ETIMAD_PAGE_SIZE: int = 50
    ETIMAD_PUBLISH_DATE_ID: int = 5          # relative publish-date window filter
    ETIMAD_TENDER_CATEGORY: str = ""         # "" = all categories
    ETIMAD_TIMEOUT_SECONDS: float = 30.0
    ETIMAD_MAX_PAGES: int = 200              # safety ceiling per run

    # --- AI / matching ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"   # 1536 dims -> matches vector(1536)
    RELEVANCE_THRESHOLD: float = 0.6

    # --- Company profile (keyword fallback when no OpenAI key) ---
    COMPANY_NAME: str = ""
    COMPANY_ACTIVITIES: str = ""             # comma-separated keywords

    # --- Scheduler ---
    SCRAPER_INTERVAL_MINUTES: int = 60
    ENABLE_SCHEDULER: bool = True

    SECRET_KEY: str = "change-me-in-production"

    @property
    def company_activities_list(self) -> list[str]:
        return [a.strip() for a in self.COMPANY_ACTIVITIES.split(",") if a.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
