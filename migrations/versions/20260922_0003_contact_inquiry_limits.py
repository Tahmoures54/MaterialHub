"""Align public contact inquiry columns with route validation limits.

Revision ID: 20260922_0003
Revises: 20260921_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0003"
down_revision = "20260921_0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("contact_inquiry", schema=None) as batch_op:
        batch_op.alter_column("email", existing_type=sa.String(length=120), type_=sa.String(length=254), existing_nullable=False)
        batch_op.alter_column("company", existing_type=sa.String(length=120), type_=sa.String(length=160), existing_nullable=True)


def downgrade():
    with op.batch_alter_table("contact_inquiry", schema=None) as batch_op:
        batch_op.alter_column("company", existing_type=sa.String(length=160), type_=sa.String(length=120), existing_nullable=True)
        batch_op.alter_column("email", existing_type=sa.String(length=254), type_=sa.String(length=120), existing_nullable=False)
