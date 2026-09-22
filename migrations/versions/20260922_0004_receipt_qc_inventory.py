"""connect goods receipts to QC and split stock into available/quarantine

Revision ID: 20260922_0015
Revises: 20260922_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0015"
down_revision = "20260922_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("quality_control", sa.Column("goods_receipt_id", sa.Integer(), nullable=True))
    op.add_column("quality_control", sa.Column("receipt_line_id", sa.Integer(), nullable=True))
    op.add_column("quality_control", sa.Column("warehouse_id", sa.String(50), nullable=True))
    op.create_index("ix_quality_control_goods_receipt_id", "quality_control", ["goods_receipt_id"])
    op.create_index("ix_quality_control_receipt_line_id", "quality_control", ["receipt_line_id"])
    op.create_index("ix_quality_control_warehouse_id", "quality_control", ["warehouse_id"])

    op.add_column("warehouse_inventory", sa.Column("available_qty", sa.Float(), nullable=True, server_default="0"))
    op.add_column("warehouse_inventory", sa.Column("quarantine_qty", sa.Float(), nullable=True, server_default="0"))
    op.execute("UPDATE warehouse_inventory SET available_qty = received_qty, quarantine_qty = 0 WHERE available_qty IS NULL")
    op.alter_column("warehouse_inventory", "available_qty", nullable=False, server_default="0")
    op.alter_column("warehouse_inventory", "quarantine_qty", nullable=False, server_default="0")


def downgrade():
    op.drop_index("ix_quality_control_warehouse_id", table_name="quality_control")
    op.drop_index("ix_quality_control_receipt_line_id", table_name="quality_control")
    op.drop_index("ix_quality_control_goods_receipt_id", table_name="quality_control")
    op.drop_column("quality_control", "warehouse_id")
    op.drop_column("quality_control", "receipt_line_id")
    op.drop_column("quality_control", "goods_receipt_id")
    op.drop_column("warehouse_inventory", "quarantine_qty")
    op.drop_column("warehouse_inventory", "available_qty")
