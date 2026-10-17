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
    op.add_column("goods_receipt", sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
    op.create_unique_constraint(
        "uq_goods_receipt_company_request_fingerprint",
        "goods_receipt",
        ["company_name", "request_fingerprint"],
    )


def downgrade():
    op.drop_constraint(
        "uq_goods_receipt_company_request_fingerprint",
        "goods_receipt",
        type_="unique",
    )
    op.drop_column("goods_receipt", "request_fingerprint")
