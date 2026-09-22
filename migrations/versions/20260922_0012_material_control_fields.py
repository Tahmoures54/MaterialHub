"""Add industrial material control and traceability fields.

Revision ID: 20260922_0012
Revises: 20260922_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0012"
down_revision = "20260922_0011"
branch_labels = None
depends_on = None

TABLE = "material_master"

COLUMNS = {
    "supplier_material_no": sa.String(100),
    "revision": sa.String(30),
    "certificate_required": sa.Boolean(),
    "inspection_required": sa.Boolean(),
    "lot_control": sa.Boolean(),
    "heat_control": sa.Boolean(),
    "serial_control": sa.Boolean(),
    "quarantine_allowed": sa.Boolean(),
    "project_peg_required": sa.Boolean(),
    "lifecycle_status": sa.String(20),
}

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(TABLE)}
    for name, typ in COLUMNS.items():
        if name in existing:
            continue
        kwargs = {"nullable": True}
        if name in {
            "certificate_required", "inspection_required", "lot_control",
            "heat_control", "serial_control", "quarantine_allowed",
            "project_peg_required"
        }:
            kwargs["server_default"] = sa.text("false")
        if name == "lifecycle_status":
            kwargs["server_default"] = sa.text("'active'")
        op.add_column(TABLE, sa.Column(name, typ, **kwargs))
    # Backfill then enforce defaults/nullability for the control flags.
    for name in (
        "certificate_required", "inspection_required", "lot_control",
        "heat_control", "serial_control", "quarantine_allowed",
        "project_peg_required"
    ):
        op.execute(sa.text(f"UPDATE {TABLE} SET {name}=false WHERE {name} IS NULL"))
        with op.batch_alter_table(TABLE) as batch:
            batch.alter_column(name, nullable=False, server_default=sa.text("false"))
    op.execute(sa.text(f"UPDATE {TABLE} SET lifecycle_status='active' WHERE lifecycle_status IS NULL"))
    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column("lifecycle_status", nullable=False, server_default=sa.text("'active'"))

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {c["name"] for c in inspector.get_columns(TABLE)}
    for name in reversed(list(COLUMNS)):
        if name in existing:
            op.drop_column(TABLE, name)
