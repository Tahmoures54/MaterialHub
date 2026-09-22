"""Create tenant-scoped Material Master for industrial item coding.

The internal material code is intentionally stable and independent from
project, vendor and warehouse location. Industry classifications remain
optional mappings (UNSPSC/eCl@ss/ETIM).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260922_0007"
down_revision = "20260922_0006"
branch_labels = None
depends_on = None


def _index(name, table, columns):
    inspector = inspect(op.get_bind())
    if name not in {i.get("name") for i in inspector.get_indexes(table)}:
        op.create_index(name, table, columns)


def upgrade():
    inspector = inspect(op.get_bind())
    if "material_master" not in set(inspector.get_table_names()):
        op.create_table(
            "material_master",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("material_code", sa.String(50), nullable=False),
            sa.Column("family_code", sa.String(20), nullable=False),
            sa.Column("material_name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("unit", sa.String(20), nullable=False, server_default="EA"),
            sa.Column("material_group", sa.String(100), nullable=True),
            sa.Column("discipline", sa.String(50), nullable=True),
            sa.Column("unspsc_code", sa.String(20), nullable=True),
            sa.Column("eclass_code", sa.String(50), nullable=True),
            sa.Column("etim_class", sa.String(50), nullable=True),
            sa.Column("standard", sa.String(100), nullable=True),
            sa.Column("grade", sa.String(100), nullable=True),
            sa.Column("size", sa.String(50), nullable=True),
            sa.Column("schedule", sa.String(50), nullable=True),
            sa.Column("manufacturer", sa.String(150), nullable=True),
            sa.Column("manufacturer_part_no", sa.String(100), nullable=True),
            sa.Column("attributes", sa.Text(), nullable=True),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("company_name", sa.String(100), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("material_code", "company_name", name="uq_material_master_code_company"),
            sa.UniqueConstraint("fingerprint", "company_name", name="uq_material_master_fingerprint_company"),
        )
    _index("ix_material_master_material_code", "material_master", ["material_code"])
    _index("ix_material_master_family_code", "material_master", ["family_code"])
    _index("ix_material_master_material_group", "material_master", ["material_group"])
    _index("ix_material_master_discipline", "material_master", ["discipline"])
    _index("ix_material_master_unspsc_code", "material_master", ["unspsc_code"])
    _index("ix_material_master_eclass_code", "material_master", ["eclass_code"])
    _index("ix_material_master_etim_class", "material_master", ["etim_class"])
    _index("ix_material_master_fingerprint", "material_master", ["fingerprint"])
    _index("ix_material_master_status", "material_master", ["status"])
    _index("ix_material_master_company_name", "material_master", ["company_name"])


def downgrade():
    op.drop_table("material_master")
