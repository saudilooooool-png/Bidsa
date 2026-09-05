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
    # Nullable columns with no default are a metadata-only change (no table
    # rewrite, no extra storage) — safe even on a capped/full tier. We
    # intentionally do NOT create an index here: a new index allocates new pages
    # and would extend the cluster past Neon free-tier's 512 MB (DiskFull), and
    # at ~22K companies the analysis scans fine without one. Add the index after
    # the DB has real headroom (upgraded tier, or VACUUM FULL when it fits).
    op.add_column("companies", sa.Column("nationality", sa.Text(), nullable=True))
    op.add_column("companies", sa.Column("is_local", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "is_local")
    op.drop_column("companies", "nationality")
