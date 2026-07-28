"""Application settings loaded from environment / .env via pydantic-settings."""
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Managed Postgres providers (Neon, Supabase, Railway) hand out one libpq URL:
#   postgresql://user:pass@host/db?sslmode=require&channel_binding=require
# psycopg2 speaks libpq and accepts it as-is, but asyncpg.connect() has no
# sslmode/channel_binding parameters and no **kwargs catch-all, so passing that
# URL through the asyncpg driver raises TypeError at connect time. Normalising
# here means operators can paste the provider's URL into either variable.
_ASYNC_DROP = {"channel_binding", "sslmode", "options"}


def normalize_db_url(url: str, *, driver: str) -> str:
    """Return `url` bound to `driver` with driver-appropriate SSL parameters."""
    if not url:
        return url
    parts = urlsplit(url)
    scheme = parts.scheme
    if "+" not in scheme and scheme.startswith(("postgres", "postgresql")):
        scheme = f"postgresql+{driver}"
    elif scheme.startswith("postgres://"):
        scheme = f"postgresql+{driver}"

    query = parse_qsl(parts.query, keep_blank_values=True)
    if scheme.endswith("+asyncpg"):
        sslmode = next((v for k, v in query if k == "sslmode"), None)
        query = [(k, v) for k, v in query if k not in _ASYNC_DROP]
        # asyncpg's equivalent of libpq sslmode=require/verify-* is ssl=
        if sslmode and not any(k == "ssl" for k, _ in query):
            query.append(("ssl", "require" if sslmode == "require" else sslmode))
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database (UTF8 database is REQUIRED: norm_status() uses normalize()) ---
    # A provider URL (postgresql://...?sslmode=require) may be pasted into either
    # variable; the validators below bind the right driver and fix SSL params.
    DATABASE_URL: str = "postgresql+asyncpg://bidsa:bidsa@localhost:5432/bidsa"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://bidsa:bidsa@localhost:5432/bidsa"

    @field_validator("DATABASE_URL")
    @classmethod
    def _async_url(cls, v: str) -> str:
        return normalize_db_url(v, driver="asyncpg")

    @field_validator("DATABASE_URL_SYNC")
    @classmethod
    def _sync_url(cls, v: str) -> str:
        return normalize_db_url(v, driver="psycopg2")

    # --- Etimad official API (primary extraction source) ---
    ETIMAD_BASE_URL: str = "https://tenders.etimad.sa"
    # AllSupplierTendersForVisitorAsync returns structured JSON (not HTML).
    ETIMAD_LIST_PATH: str = "/Tender/AllSupplierTendersForVisitorAsync"
    ETIMAD_PAGE_SIZE: int = 50
    ETIMAD_PUBLISH_DATE_ID: int = 5          # relative publish-date window filter
    ETIMAD_TENDER_CATEGORY: str = ""         # "" = all categories
    ETIMAD_TIMEOUT_SECONDS: float = 30.0
    ETIMAD_MAX_PAGES: int = 200              # safety ceiling per run
    ETIMAD_PAGE_DELAY_SECONDS: float = 3.0   # pacing between pages (WAF-friendly)

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
