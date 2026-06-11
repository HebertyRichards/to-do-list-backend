"""add daily_reminder notification type

Revision ID: c058c6555be3
Revises: affa0a6a8be1
Create Date: 2026-06-09 23:14:18.223043

"""
from alembic import op
import sqlalchemy as sa


revision = 'c058c6555be3'
down_revision = 'affa0a6a8be1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    schema = conn.execute(
        sa.text(
            "SELECT n.nspname FROM pg_type t "
            "JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE t.typname = 'notification_type'"
        )
    ).scalar()
    with op.get_context().autocommit_block():
        op.execute(
            f'ALTER TYPE "{schema}".notification_type ADD VALUE IF NOT EXISTS \'daily_reminder\''
        )


def downgrade() -> None:
    # Postgres nao suporta remover valores de enum; nada a fazer.
    pass
