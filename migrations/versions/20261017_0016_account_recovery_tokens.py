"""Add hashed, expiring TOTP recovery tokens.

Revision ID: 20261017_0016
Revises: 20260922_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20261017_0016"
down_revision = "20260922_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_recovery_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("pending_totp_secret", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_account_recovery_token_hash"),
    )
    op.create_index("ix_account_recovery_token_user_id", "account_recovery_token", ["user_id"])
    op.create_index("ix_account_recovery_token_token_hash", "account_recovery_token", ["token_hash"])
    op.create_index("ix_account_recovery_token_expires_at", "account_recovery_token", ["expires_at"])


def downgrade():
    op.drop_index("ix_account_recovery_token_expires_at", table_name="account_recovery_token")
    op.drop_index("ix_account_recovery_token_token_hash", table_name="account_recovery_token")
    op.drop_index("ix_account_recovery_token_user_id", table_name="account_recovery_token")
    op.drop_table("account_recovery_token")
