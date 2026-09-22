"""Allow multiple Material Master items in the same warehouse.

Revision ID: 20260922_0010
Revises: 20260922_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0010"
down_revision = "20260922_0009"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    ins = sa.inspect(bind)
    if not ins.has_table("warehouse_inventory"):
        return
    uniques = {x.get("name") for x in ins.get_unique_constraints("warehouse_inventory")}
    if "uq_wh_warehouse_id_company" in uniques:
        op.drop_constraint("uq_wh_warehouse_id_company", "warehouse_inventory", type_="unique")
    ins = sa.inspect(bind)
    uniques = {x.get("name") for x in ins.get_unique_constraints("warehouse_inventory")}
    if "uq_wh_warehouse_material_company" not in uniques:
        op.create_unique_constraint("uq_wh_warehouse_material_company", "warehouse_inventory", ["warehouse_id", "material_id", "company_name"])

def downgrade():
    bind = op.get_bind()
    ins = sa.inspect(bind)
    if ins.has_table("warehouse_inventory"):
        uniques = {x.get("name") for x in ins.get_unique_constraints("warehouse_inventory")}
        if "uq_wh_warehouse_material_company" in uniques:
            op.drop_constraint("uq_wh_warehouse_material_company", "warehouse_inventory", type_="unique")
        ins = sa.inspect(bind)
        uniques = {x.get("name") for x in ins.get_unique_constraints("warehouse_inventory")}
        if "uq_wh_warehouse_id_company" not in uniques:
            op.create_unique_constraint("uq_wh_warehouse_id_company", "warehouse_inventory", ["warehouse_id", "company_name"])
