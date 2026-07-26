"""initial schema — applies the canonical db/schema.sql

``db/schema.sql`` (repo root) is the single source of truth for the DDL:
enums, the classify_tender_lifecycle() function, the tenders_live view,
generated tsvector column, pgvector columns + HNSW indexes, and RLS policies —
none of which Alembic autogenerate handles well. So this migration executes
that file verbatim (minus its outer BEGIN/COMMIT, since Alembic manages the
transaction).

Requires the `vector` extension (pgvector) to be installed on the server.

Revision ID: 001
Revises:
Create Date: 2026-07-26 00:00:00.000000
"""
import os
from pathlib import Path
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_HERE = Path(__file__).resolve()


def _find_schema_sql() -> Path:
    """Locate db/schema.sql across local (repo root) and Docker (/app/db) layouts."""
    if os.environ.get("BIDSA_SCHEMA_SQL"):
        return Path(os.environ["BIDSA_SCHEMA_SQL"])
    candidates = [
        _HERE.parents[3] / "db" / "schema.sql",   # local: <repo>/backend/alembic/versions -> <repo>/db
        _HERE.parents[2] / "db" / "schema.sql",   # docker: /app/alembic/versions -> /app/db (mounted)
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "db/schema.sql not found; set BIDSA_SCHEMA_SQL or mount it. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


def _load_ddl() -> str:
    raw = _find_schema_sql().read_text(encoding="utf-8")
    # Alembic runs inside its own transaction; drop the file's own BEGIN/COMMIT.
    lines = [
        ln for ln in raw.splitlines()
        if ln.strip().upper() not in ("BEGIN;", "COMMIT;")
    ]
    return "\n".join(lines)


def upgrade() -> None:
    op.execute(_load_ddl())


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS tenders_live;
        DROP TABLE IF EXISTS bid_proposals CASCADE;
        DROP TABLE IF EXISTS knowledge_chunks CASCADE;
        DROP TABLE IF EXISTS knowledge_documents CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS organizations CASCADE;
        DROP TABLE IF EXISTS tender_bids CASCADE;
        DROP TABLE IF EXISTS award_winners CASCADE;
        DROP TABLE IF EXISTS awards CASCADE;
        DROP TABLE IF EXISTS tenders CASCADE;
        DROP TABLE IF EXISTS companies CASCADE;
        DROP TABLE IF EXISTS tender_types CASCADE;
        DROP TABLE IF EXISTS activities CASCADE;
        DROP TABLE IF EXISTS agencies CASCADE;
        DROP TABLE IF EXISTS regions CASCADE;
        DROP FUNCTION IF EXISTS classify_tender_lifecycle(text, integer, timestamptz, text, boolean, bigint, integer, timestamptz);
        DROP FUNCTION IF EXISTS norm_status(text);
        DROP FUNCTION IF EXISTS set_updated_at();
        DROP TYPE IF EXISTS tender_lifecycle;
        """
    )
