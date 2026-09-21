"""Add shareable reports and material requests."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0005"
down_revision = "20260922_0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_share",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=96), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("report_type", sa.String(length=30), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_report_share_token", "report_share", ["token"], unique=True)
    op.create_index("ix_report_share_company_name", "report_share", ["company_name"], unique=False)
    op.create_index("ix_report_share_expires_at", "report_share", ["expires_at"], unique=False)

    op.create_table(
        "material_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_no", sa.String(length=50), nullable=False),
        sa.Column("company_name", sa.String(length=100), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("request_no", "company_name", name="uq_material_request_no_company"),
    )
    op.create_index("ix_material_request_company_name", "material_request", ["company_name"], unique=False)
    op.create_index("ix_material_request_request_no", "material_request", ["request_no"], unique=False)
    op.create_index("ix_material_request_status", "material_request", ["status"], unique=False)


def downgrade():
    op.drop_table("material_request")
    op.drop_table("report_share")
