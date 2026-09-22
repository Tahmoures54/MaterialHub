"""add packing list, goods receipt, receipt line and OS&D workflow

Revision ID: 20260922_0003
Revises: 20260921_0002
Create Date: 2026-09-22
"""
from alembic import op
import sqlalchemy as sa


revision = "20260922_0003"
down_revision = "20260921_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "packing_list",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("packing_list_no", sa.String(80), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("purchase_order.id"), nullable=True),
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("delivery.id"), nullable=True),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("packing_list_date", sa.Date(), nullable=False),
        sa.Column("vehicle_no", sa.String(80), nullable=True),
        sa.Column("package_count", sa.Integer(), nullable=True),
        sa.Column("gross_weight", sa.Float(), nullable=True),
        sa.Column("net_weight", sa.Float(), nullable=True),
        sa.Column("document_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="received"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("packing_list_no", "company_name", name="uq_packing_list_no_company"),
    )
    op.create_index("ix_packing_list_packing_list_no", "packing_list", ["packing_list_no"])
    op.create_index("ix_packing_list_order_id", "packing_list", ["order_id"])
    op.create_index("ix_packing_list_delivery_id", "packing_list", ["delivery_id"])
    op.create_index("ix_packing_list_supplier_id", "packing_list", ["supplier_id"])
    op.create_index("ix_packing_list_company_name", "packing_list", ["company_name"])

    op.create_table(
        "packing_list_line",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("packing_list_id", sa.Integer(), sa.ForeignKey("packing_list.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_master.id"), nullable=False),
        sa.Column("item_code", sa.String(50), nullable=False),
        sa.Column("material_description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("package_no", sa.String(80), nullable=True),
        sa.Column("lot_no", sa.String(100), nullable=True),
        sa.Column("heat_no", sa.String(100), nullable=True),
        sa.Column("serial_no", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    op.create_index("ix_packing_list_line_packing_list_id", "packing_list_line", ["packing_list_id"])
    op.create_index("ix_packing_list_line_material_id", "packing_list_line", ["material_id"])
    op.create_index("ix_packing_list_line_item_code", "packing_list_line", ["item_code"])

    op.create_table(
        "goods_receipt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_no", sa.String(80), nullable=False),
        sa.Column("packing_list_id", sa.Integer(), sa.ForeignKey("packing_list.id"), nullable=False),
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("delivery.id"), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("purchase_order.id"), nullable=True),
        sa.Column("warehouse_id", sa.String(50), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("received_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="posted"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("receipt_no", "company_name", name="uq_goods_receipt_no_company"),
    )
    op.create_index("ix_goods_receipt_receipt_no", "goods_receipt", ["receipt_no"])
    op.create_index("ix_goods_receipt_packing_list_id", "goods_receipt", ["packing_list_id"])
    op.create_index("ix_goods_receipt_delivery_id", "goods_receipt", ["delivery_id"])
    op.create_index("ix_goods_receipt_order_id", "goods_receipt", ["order_id"])
    op.create_index("ix_goods_receipt_warehouse_id", "goods_receipt", ["warehouse_id"])
    op.create_index("ix_goods_receipt_company_name", "goods_receipt", ["company_name"])

    op.create_table(
        "goods_receipt_line",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipt.id"), nullable=False),
        sa.Column("packing_list_line_id", sa.Integer(), sa.ForeignKey("packing_list_line.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_master.id"), nullable=False),
        sa.Column("item_code", sa.String(50), nullable=False),
        sa.Column("material_description", sa.Text(), nullable=False),
        sa.Column("expected_qty", sa.Float(), nullable=False),
        sa.Column("received_qty", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("storage_location_id", sa.String(100), nullable=True),
        sa.Column("inspection_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("lot_no", sa.String(100), nullable=True),
        sa.Column("heat_no", sa.String(100), nullable=True),
        sa.Column("serial_no", sa.String(100), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
    )
    op.create_index("ix_goods_receipt_line_goods_receipt_id", "goods_receipt_line", ["goods_receipt_id"])
    op.create_index("ix_goods_receipt_line_packing_list_line_id", "goods_receipt_line", ["packing_list_line_id"])
    op.create_index("ix_goods_receipt_line_material_id", "goods_receipt_line", ["material_id"])
    op.create_index("ix_goods_receipt_line_item_code", "goods_receipt_line", ["item_code"])

    op.create_table(
        "osd_report",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("osd_no", sa.String(80), nullable=False),
        sa.Column("goods_receipt_id", sa.Integer(), sa.ForeignKey("goods_receipt.id"), nullable=False),
        sa.Column("packing_list_id", sa.Integer(), sa.ForeignKey("packing_list.id"), nullable=False),
        sa.Column("delivery_id", sa.Integer(), sa.ForeignKey("delivery.id"), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("company_name", sa.String(100), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("osd_no", "company_name", name="uq_osd_no_company"),
    )
    op.create_index("ix_osd_report_osd_no", "osd_report", ["osd_no"])
    op.create_index("ix_osd_report_goods_receipt_id", "osd_report", ["goods_receipt_id"])
    op.create_index("ix_osd_report_packing_list_id", "osd_report", ["packing_list_id"])
    op.create_index("ix_osd_report_delivery_id", "osd_report", ["delivery_id"])
    op.create_index("ix_osd_report_company_name", "osd_report", ["company_name"])

    op.create_table(
        "osd_report_line",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("osd_report_id", sa.Integer(), sa.ForeignKey("osd_report.id"), nullable=False),
        sa.Column("goods_receipt_line_id", sa.Integer(), sa.ForeignKey("goods_receipt_line.id"), nullable=False),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("material_master.id"), nullable=False),
        sa.Column("discrepancy_type", sa.String(40), nullable=False),
        sa.Column("expected_qty", sa.Float(), nullable=False),
        sa.Column("received_qty", sa.Float(), nullable=False),
        sa.Column("variance_qty", sa.Float(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("action_required", sa.String(200), nullable=True),
    )
    op.create_index("ix_osd_report_line_osd_report_id", "osd_report_line", ["osd_report_id"])
    op.create_index("ix_osd_report_line_goods_receipt_line_id", "osd_report_line", ["goods_receipt_line_id"])
    op.create_index("ix_osd_report_line_material_id", "osd_report_line", ["material_id"])

    op.add_column("warehouse_transaction", sa.Column("goods_receipt_id", sa.Integer(), nullable=True))
    op.add_column("warehouse_transaction", sa.Column("receipt_line_id", sa.Integer(), nullable=True))
    op.add_column("warehouse_transaction", sa.Column("packing_list_id", sa.Integer(), nullable=True))
    op.create_index("ix_warehouse_transaction_goods_receipt_id", "warehouse_transaction", ["goods_receipt_id"])
    op.create_index("ix_warehouse_transaction_receipt_line_id", "warehouse_transaction", ["receipt_line_id"])
    op.create_index("ix_warehouse_transaction_packing_list_id", "warehouse_transaction", ["packing_list_id"])


def downgrade():
    op.drop_index("ix_warehouse_transaction_packing_list_id", table_name="warehouse_transaction")
    op.drop_index("ix_warehouse_transaction_receipt_line_id", table_name="warehouse_transaction")
    op.drop_index("ix_warehouse_transaction_goods_receipt_id", table_name="warehouse_transaction")
    op.drop_column("warehouse_transaction", "packing_list_id")
    op.drop_column("warehouse_transaction", "receipt_line_id")
    op.drop_column("warehouse_transaction", "goods_receipt_id")

    for table in ("osd_report_line", "osd_report", "goods_receipt_line", "goods_receipt", "packing_list_line", "packing_list"):
        op.drop_table(table)
