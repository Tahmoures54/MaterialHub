"""Make Goods Receipt POST retries idempotent.

Revision ID: 20261017_0017
Revises: 20261017_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20261017_0017"
down_revision = "20261017_0016"
branch_labels = None
depends_on = None


def upgrade():
    # Batch mode supports SQLite schema upgrades as well as PostgreSQL ALTER TABLE.
    with op.batch_alter_table("goods_receipt") as batch_op:
        batch_op.add_column(sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_goods_receipt_company_request_fingerprint",
            ["company_name", "request_fingerprint"],
        )


def downgrade():
    with op.batch_alter_table("goods_receipt") as batch_op:
        batch_op.drop_constraint(
            "uq_goods_receipt_company_request_fingerprint",
            type_="unique",
        )
        batch_op.drop_column("request_fingerprint")
