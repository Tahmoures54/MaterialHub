"""Link warehouse inventory and transactions to Material Master.

Revision ID: 20260922_0008
Revises: 20260922_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0008"
down_revision = "20260922_0007"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def _add_column(inspector, table, column):
    """Add a SQLAlchemy Column only when the database does not have it."""
    if column.name not in _columns(inspector, table):
        op.add_column(table, column)


def _index_names(inspector, table):
    return {i["name"] for i in inspector.get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("warehouse_inventory"):
        _add_column(
            inspector,
            "warehouse_inventory",
            sa.Column("material_id", sa.Integer(), nullable=True),
        )
        inspector = sa.inspect(bind)
        if "ix_warehouse_inventory_material_id" not in _index_names(inspector, "warehouse_inventory"):
            op.create_index(
                "ix_warehouse_inventory_material_id",
                "warehouse_inventory",
                ["material_id"],
                unique=False,
            )
        # Existing rows remain valid through nullable material_id. New UI flows
        # populate it from Material Master.

        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("warehouse_inventory")}
        if "fk_warehouse_inventory_material_id" not in fk_names:
            op.create_foreign_key(
                "fk_warehouse_inventory_material_id",
                "warehouse_inventory",
                "material_master",
                ["material_id"],
                ["id"],
            )

    if inspector.has_table("warehouse_transaction"):
        _add_column(
            inspector,
            "warehouse_transaction",
            sa.Column("material_id", sa.Integer(), nullable=True),
        )
        inspector = sa.inspect(bind)
        if "ix_warehouse_transaction_material_id" not in _index_names(inspector, "warehouse_transaction"):
            op.create_index(
                "ix_warehouse_transaction_material_id",
                "warehouse_transaction",
                ["material_id"],
                unique=False,
            )
        if "balance_before" not in _columns(inspector, "warehouse_transaction"):
            op.add_column("warehouse_transaction", sa.Column("balance_before", sa.Float(), nullable=True))
        if "balance_after" not in _columns(inspector, "warehouse_transaction"):
            op.add_column("warehouse_transaction", sa.Column("balance_after", sa.Float(), nullable=True))
        if "destination_warehouse_id" not in _columns(inspector, "warehouse_transaction"):
            op.add_column("warehouse_transaction", sa.Column("destination_warehouse_id", sa.String(length=50), nullable=True))
            inspector = sa.inspect(bind)
            if "ix_warehouse_transaction_destination_warehouse_id" not in _index_names(inspector, "warehouse_transaction"):
                op.create_index(
                    "ix_warehouse_transaction_destination_warehouse_id",
                    "warehouse_transaction",
                    ["destination_warehouse_id"],
                    unique=False,
                )
        inspector = sa.inspect(bind)
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("warehouse_transaction")}
        if "fk_warehouse_transaction_material_id" not in fk_names:
            op.create_foreign_key(
                "fk_warehouse_transaction_material_id",
                "warehouse_transaction",
                "material_master",
                ["material_id"],
                ["id"],
            )


def downgrade():
    # Keep the migration reversible while preserving legacy inventory rows.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("warehouse_transaction"):
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("warehouse_transaction")}
        if "fk_warehouse_transaction_material_id" in fk_names:
            op.drop_constraint("fk_warehouse_transaction_material_id", "warehouse_transaction", type_="foreignkey")
        for name in ("ix_warehouse_transaction_destination_warehouse_id", "ix_warehouse_transaction_material_id"):
            if name in _index_names(inspector, "warehouse_transaction"):
                op.drop_index(name, table_name="warehouse_transaction")
        for col in ("destination_warehouse_id", "balance_after", "balance_before", "material_id"):
            if col in _columns(inspector, "warehouse_transaction"):
                op.drop_column("warehouse_transaction", col)
    inspector = sa.inspect(bind)
    if inspector.has_table("warehouse_inventory"):
        fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("warehouse_inventory")}
        if "fk_warehouse_inventory_material_id" in fk_names:
            op.drop_constraint("fk_warehouse_inventory_material_id", "warehouse_inventory", type_="foreignkey")
        if "ix_warehouse_inventory_material_id" in _index_names(inspector, "warehouse_inventory"):
            op.drop_index("ix_warehouse_inventory_material_id", table_name="warehouse_inventory")
        if "material_id" in _columns(inspector, "warehouse_inventory"):
            op.drop_column("warehouse_inventory", "material_id")
