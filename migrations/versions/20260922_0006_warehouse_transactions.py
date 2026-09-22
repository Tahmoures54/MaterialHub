"""Add warehouse transaction audit ledger.

Idempotent for deployments where the table may already exist.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260922_0006"
down_revision = "20260922_0005"
branch_labels = None
depends_on = None


def _ensure_index(name, table_name, columns, unique=False):
    inspector = inspect(op.get_bind())
    existing = {item.get("name") for item in inspector.get_indexes(table_name)}
    if name not in existing:
        op.create_index(name, table_name, columns, unique=unique)


def upgrade():
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "warehouse_transaction" not in tables:
        op.create_table(
            "warehouse_transaction",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("transaction_no", sa.String(length=50), nullable=False),
            sa.Column("transaction_type", sa.String(length=30), nullable=False),
            sa.Column("warehouse_id", sa.String(length=50), nullable=False),
            sa.Column("item_code", sa.String(length=50), nullable=False),
            sa.Column("material_description", sa.Text(), nullable=False),
            sa.Column("quantity", sa.Float(), nullable=False),
            sa.Column("unit", sa.String(length=50), nullable=False),
            sa.Column("project_no", sa.String(length=50), nullable=True),
            sa.Column("delivery_id", sa.String(length=50), nullable=True),
            sa.Column("contractor", sa.String(length=150), nullable=True),
            sa.Column("storage_location_id", sa.String(length=100), nullable=True),
            sa.Column("reference_no", sa.String(length=100), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("company_name", sa.String(length=100), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("transaction_no", "company_name", name="uq_warehouse_transaction_no_company"),
        )
    _ensure_index("ix_warehouse_transaction_transaction_no", "warehouse_transaction", ["transaction_no"])
    _ensure_index("ix_warehouse_transaction_type", "warehouse_transaction", ["transaction_type"])
    _ensure_index("ix_warehouse_transaction_warehouse_id", "warehouse_transaction", ["warehouse_id"])
    _ensure_index("ix_warehouse_transaction_item_code", "warehouse_transaction", ["item_code"])
    _ensure_index("ix_warehouse_transaction_company_name", "warehouse_transaction", ["company_name"])
    _ensure_index("ix_warehouse_transaction_created_at", "warehouse_transaction", ["created_at"])


def downgrade():
    op.drop_table("warehouse_transaction")
