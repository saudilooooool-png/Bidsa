# Bidsa Backend — Etimad Procurement Intelligence

FastAPI backend built around the deep data contract in [`../db/schema.sql`](../db/schema.sql).
It merges the strengths of two reference projects:

- **Product skeleton** (API, scheduler, jobs, Docker) — adapted from the shape of
  `qusai132/etimad`, but around a much deeper schema.
- **Data depth** (lifecycle classification, exact halalas money, awards/winners,
  provenance, pgvector/RAG) — ported from `etimad-plus-viewer`.

## What's different from a plain scraper

| Concern | This backend |
|---|---|
| Extraction | **Official JSON API** (`AllSupplierTendersForVisitorAsync`) via `httpx`, not HTML scraping. Playwright kept only as an optional fallback. |
| Lifecycle | `classify_tender` ported to `app/services/lifecycle.py` **and** SQL (`tenders_live` view). 13/13 parity tests pass. |
| Money | Exact integer **halalas** via `Decimal(str(v))` (`app/services/money.py`) — never float. |
| Search | Postgres GIN full-text + trigram; `lifecycle` filter uses the live SQL view. |
| AI | `ai_summary`, `mandatory_requirements`, `local_content_requirements`, `risk_flags` + pgvector embeddings (RAG-ready). |

## Layout

```
backend/
├── app/
│   ├── core/        config + structured logging
│   ├── db/          async engine + declarative base
│   ├── models/      SQLAlchemy models (mirror db/schema.sql)
│   ├── schemas/     Pydantic response models
│   ├── services/    etimad_api · ingest · lifecycle · money · enrich
│   ├── api/         REST endpoints
│   └── tasks/       APScheduler jobs (ingest + enrichment)
├── alembic/         migration 001 applies db/schema.sql verbatim
└── tests/           lifecycle parity tests
```

## Run

```bash
# From the repo root — brings up pgvector-enabled Postgres + backend + migrations
docker compose up --build
# API:  http://localhost:8000      docs: http://localhost:8000/docs
```

Local dev:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill DB URLs, optional OPENAI_API_KEY
alembic upgrade head            # applies ../db/schema.sql (needs pgvector + UTF8 DB)
uvicorn app.main:app --reload
python tests/test_lifecycle.py  # 13/13 parity
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/tenders` | list; filters: `search`, `lifecycle`, `agency_id`, `activity_id`, `page`, `page_size` |
| GET | `/api/v1/tenders/{id}` | single tender |
| POST | `/api/v1/ingest/run?incremental=true` | trigger extraction+ingest (background) |
| GET | `/health` | health check |

## Notes / TODO before production

- **Verify Etimad JSON field names** against a live response and adjust
  `FIELD_MAP` in `app/services/etimad_api.py` (the sandbox couldn't reach the API).
- The DB **must be UTF8** — `norm_status()` uses `normalize()`.
- Awards/winners/bids tables exist in the schema; wire their population once the
  award-detail endpoint mapping is confirmed.
- Restrict CORS `allow_origins` and set a real `SECRET_KEY`.
