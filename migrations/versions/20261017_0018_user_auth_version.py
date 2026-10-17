"""Add session revocation version to users.

Revision ID: 20261017_0018
Revises: 20261017_0017
"""
from alembic import op
import sqlalchemy as sa

revision = "20261017_0018"
down_revision = "20261017_0017"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("auth_version")
