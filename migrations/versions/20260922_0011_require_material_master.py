"""Make Material Master identity mandatory across the core workflow.

Revision ID: 20260922_0011
Revises: 20260922_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0011"
down_revision = "20260922_0010"
branch_labels = None
depends_on = None

TABLES = ("material_requisition", "purchase_order_item", "delivery", "quality_control", "warehouse_inventory", "warehouse_transaction")

def upgrade():
    bind = op.get_bind()
    ins = sa.inspect(bind)
    # This release intentionally requires a clean database: all new workflow
    # records must have a Material Master identity.
    for table in TABLES:
        if not ins.has_table(table):
            continue
        missing = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE material_id IS NULL")).scalar() or 0
        if missing:
            raise RuntimeError(
                f"{table} contains {missing} record(s) without material_id. "
                "Material Master identity is now mandatory; clean/migrate those records before upgrading."
            )
        with op.batch_alter_table(table) as batch:
            batch.alter_column("material_id", existing_type=sa.Integer(), nullable=False)

def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("material_id", existing_type=sa.Integer(), nullable=True)
