"""SaaS auth + trial columns

- users.password_hash / users.is_active : credential storage (scrypt)
- organizations.trial_ends_at           : 14-day free trial deadline
- organizations.plan_activated_at       : when a paid plan started

Revision ID: 003
Revises: 002
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=False, server_default=""))
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("organizations", sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("organizations", sa.Column("plan_activated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "plan_activated_at")
    op.drop_column("organizations", "trial_ends_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
