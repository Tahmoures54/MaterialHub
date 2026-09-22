"""Add packing list and receiving control fields to warehouse transactions.

Revision ID: 20260922_0013
Revises: 20260922_0012
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260922_0013"
down_revision = "20260922_0012"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def _add_column(inspector, table, column):
    if column.name not in _columns(inspector, table):
        op.add_column(table, column)


def upgrade():
    inspector = inspect(op.get_bind())
    table = "warehouse_transaction"
    _add_column(inspector, table, sa.Column("packing_list_no", sa.String(100), nullable=True))
    _add_column(inspector, table, sa.Column("packing_list_date", sa.Date(), nullable=True))
    _add_column(inspector, table, sa.Column("packing_list_document", sa.String(500), nullable=True))
    _add_column(inspector, table, sa.Column("supplier_name", sa.String(150), nullable=True))
    _add_column(inspector, table, sa.Column("discrepancy_type", sa.String(40), nullable=True))
    _add_column(inspector, table, sa.Column("discrepancy_details", sa.Text(), nullable=True))

    inspector = inspect(op.get_bind())
    indexes = {i["name"] for i in inspector.get_indexes(table)}
    if "ix_warehouse_transaction_packing_list_no" not in indexes:
        op.create_index(
            "ix_warehouse_transaction_packing_list_no",
            table,
            ["packing_list_no"],
        )
    if "ix_warehouse_transaction_supplier_name" not in indexes:
        op.create_index(
            "ix_warehouse_transaction_supplier_name",
            table,
            ["supplier_name"],
        )


def downgrade():
    inspector = inspect(op.get_bind())
    table = "warehouse_transaction"
    indexes = {i["name"] for i in inspector.get_indexes(table)}
    for name in (
        "ix_warehouse_transaction_supplier_name",
        "ix_warehouse_transaction_packing_list_no",
    ):
        if name in indexes:
            op.drop_index(name, table_name=table)
    cols = _columns(inspector, table)
    for name in (
        "discrepancy_details",
        "discrepancy_type",
        "supplier_name",
        "packing_list_document",
        "packing_list_date",
        "packing_list_no",
    ):
        if name in cols:
            op.drop_column(table, name)
