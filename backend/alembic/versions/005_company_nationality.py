"""company nationality enrichment columns

Adds nationality + is_local to companies. The historical Etimad corpus records
bidder NAMES only (no nationality anywhere), so local-vs-foreign analysis needs
these filled from an authoritative/external source — see
services/company_nationality.py.

Revision ID: 005
Revises: 004
Create Date: 2026-09-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("nationality", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("is_local", sa.Boolean(), nullable=True))
    # Partial index: analyses filter on classified rows, most stay NULL until enriched.
    op.create_index(
        "ix_companies_is_local", "companies", ["is_local"],
        postgresql_where=sa.text("is_local IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_companies_is_local", table_name="companies")
    op.drop_column("companies", "is_local")
    op.drop_column("companies", "nationality")
