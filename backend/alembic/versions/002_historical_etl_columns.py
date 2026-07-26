"""historical ETL support columns

Adds fields present in the historical awarded corpus (etimad-plus-viewer
data shards) that the initial schema lacked:

- tenders.tender_number   : agency-side tender number ("num" in the shards)
- tenders.details_url     : Etimad DetailsForVisitor URL
- tenders.submitted_at    : official submission/publish timestamp ("submit")
- companies.name_key      : normalized company-name key used by the baseline
                            exporter to deduplicate hamza/teh-marbuta variants;
                            unique so ETL upserts converge on one company row
- unique(name_ar) on agencies/activities/tender_types: the historical corpus
  identifies these entities by Arabic name only, so the ETL needs name-level
  ON CONFLICT targets (regions already had one in the initial schema)

Revision ID: 002
Revises: 001
Create Date: 2026-07-26 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenders", sa.Column("tender_number", sa.Text(), nullable=True))
    op.add_column("tenders", sa.Column("details_url", sa.Text(), nullable=True))
    op.add_column("tenders", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("companies", sa.Column("name_key", sa.Text(), nullable=True))
    # plain unique indexes: Postgres treats NULLs as distinct, and ON CONFLICT
    # inference needs non-partial indexes
    op.create_index("uq_companies_name_key", "companies", ["name_key"], unique=True)
    op.create_index("uq_agencies_name_ar", "agencies", ["name_ar"], unique=True)
    op.create_index("uq_activities_name_ar", "activities", ["name_ar"], unique=True)
    op.create_index("uq_tender_types_name_ar", "tender_types", ["name_ar"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_tender_types_name_ar", table_name="tender_types")
    op.drop_index("uq_activities_name_ar", table_name="activities")
    op.drop_index("uq_agencies_name_ar", table_name="agencies")
    op.drop_index("uq_companies_name_key", table_name="companies")
    op.drop_column("companies", "name_key")
    op.drop_column("tenders", "submitted_at")
    op.drop_column("tenders", "details_url")
    op.drop_column("tenders", "tender_number")
