"""Add 45-day trial and subscription state to users.

Revision ID: 20260922_0004
Revises: 20260922_0003
"""
from datetime import datetime, timedelta, timezone

from alembic import op
import sqlalchemy as sa

revision = "20260922_0004"
down_revision = "20260922_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trial_started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("trial_ends_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("subscription_plan", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("subscription_status", sa.String(length=20), nullable=True))
        batch_op.create_index("ix_user_trial_started_at", ["trial_started_at"], unique=False)
        batch_op.create_index("ix_user_trial_ends_at", ["trial_ends_at"], unique=False)

    bind = op.get_bind()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    end = now + timedelta(days=45)
    bind.execute(
        sa.text(
            'UPDATE "user" SET trial_started_at = :started, trial_ends_at = :ended, '
            "subscription_plan = 'trial', subscription_status = 'trial' "
            "WHERE trial_started_at IS NULL OR trial_ends_at IS NULL "
            "OR subscription_plan IS NULL OR subscription_status IS NULL"
        ),
        {"started": now, "ended": end},
    )

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column("subscription_plan", existing_type=sa.String(length=30), nullable=False, server_default="trial")
        batch_op.alter_column("subscription_status", existing_type=sa.String(length=20), nullable=False, server_default="trial")


def downgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_index("ix_user_trial_ends_at")
        batch_op.drop_index("ix_user_trial_started_at")
        batch_op.drop_column("subscription_status")
        batch_op.drop_column("subscription_plan")
        batch_op.drop_column("trial_ends_at")
        batch_op.drop_column("trial_started_at")
