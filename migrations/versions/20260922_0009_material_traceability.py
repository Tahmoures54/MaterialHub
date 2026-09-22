"""Add Material Master links to PO items, deliveries and QC.

Revision ID: 20260922_0009
Revises: 20260922_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0009"
down_revision = "20260922_0008"
branch_labels = None
depends_on = None

def _cols(inspector, table):
    return {x["name"] for x in inspector.get_columns(table)}

def _idx(inspector, table):
    return {x["name"] for x in inspector.get_indexes(table)}

def _add(table):
    bind = op.get_bind(); ins = sa.inspect(bind)
    if not ins.has_table(table): return
    if "material_id" not in _cols(ins, table):
        op.add_column(table, sa.Column("material_id", sa.Integer(), nullable=True))
    ins = sa.inspect(bind)
    name = f"ix_{table}_material_id"
    if name not in _idx(ins, table):
        op.create_index(name, table, ["material_id"], unique=False)
    ins = sa.inspect(bind)
    fks = {x.get("name") for x in ins.get_foreign_keys(table)}
    fk = f"fk_{table}_material_id"
    if fk not in fks:
        op.create_foreign_key(fk, table, "material_master", ["material_id"], ["id"])

def upgrade():
    for table in ("purchase_order_item", "delivery", "quality_control"):
        _add(table)

def downgrade():
    bind = op.get_bind(); ins = sa.inspect(bind)
    for table in ("quality_control", "delivery", "purchase_order_item"):
        if not ins.has_table(table): continue
        fk = f"fk_{table}_material_id"
        fks = {x.get("name") for x in ins.get_foreign_keys(table)}
        if fk in fks: op.drop_constraint(fk, table, type_="foreignkey")
        ins = sa.inspect(bind)
        name = f"ix_{table}_material_id"
        if name in _idx(ins, table): op.drop_index(name, table_name=table)
        ins = sa.inspect(bind)
        if "material_id" in _cols(ins, table): op.drop_column(table, "material_id")
