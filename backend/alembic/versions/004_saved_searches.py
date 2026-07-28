"""saved searches (tender alerts)

An org-scoped alert: a named set of filters (keywords/activity/region) that a
digest job runs to email new matching open tenders.

Revision ID: 004
Revises: 003
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_searches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("organization_id", UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=True),
        sa.Column("activity_id", sa.BigInteger(), nullable=True),
        sa.Column("region_id", sa.Integer(), nullable=True),
        sa.Column("notify_email", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_saved_searches_org", "saved_searches", ["organization_id"])

    op.execute("ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY org_isolation_saved_searches ON saved_searches "
        "USING (organization_id = current_setting('app.current_org', true)::uuid)"
    )


def downgrade() -> None:
    op.drop_table("saved_searches")
