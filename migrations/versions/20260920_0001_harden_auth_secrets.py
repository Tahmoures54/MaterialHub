"""Harden authentication secret storage.

Revision ID: 20260920_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "20260920_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "user",
        "totp_secret",
        existing_type=sa.String(length=32),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.execute(sa.text('UPDATE "user" SET qr_code_base64 = NULL'))


def downgrade():
    op.alter_column(
        "user",
        "totp_secret",
        existing_type=sa.String(length=512),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
