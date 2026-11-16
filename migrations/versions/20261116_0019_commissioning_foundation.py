"""Create OPERA commissioning foundation.

Revision ID: 20261116_0019
Revises: 20261017_0018
"""
from alembic import op
import sqlalchemy as sa

revision = "20261116_0019"
down_revision = "20261017_0018"
branch_labels = None
depends_on = None


def E(*values, name):
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade():
    op.create_index("uq_project_id_company", "project", ["id", "company_name"], unique=True)
    op.create_index("uq_user_id_company", "user", ["id", "company_name"], unique=True)

    op.create_table("commissioning_system",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("system_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", E("PLANNED", "ACTIVE", "COMPLETED", name="commissioning_system_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_system_id_tenant"),
        sa.UniqueConstraint("tenant_id", "project_id", "system_code", name="uq_cs_system_code_tenant"),
        sa.ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"], name="fk_cs_system_project_tenant", ondelete="RESTRICT"))
    op.create_index("ix_commissioning_system_tenant_id", "commissioning_system", ["tenant_id"])
    op.create_index("ix_commissioning_system_project_id", "commissioning_system", ["project_id"])

    op.create_table("commissioning_subsystem",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("system_id", sa.Integer(), nullable=False),
        sa.Column("subsystem_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("weight_percent", sa.Float(), nullable=False),
        sa.Column("weight_a_percent", sa.Float(), nullable=False),
        sa.Column("weight_b_percent", sa.Float(), nullable=False),
        sa.Column("weight_c_percent", sa.Float(), nullable=False),
        sa.Column("lifecycle_stage", E("SYSTEMIZATION", "CHECKSHEET_EXECUTION", "PUNCH_CLEARANCE", "CERTIFICATION", "HANDOVER", name="commissioning_stage"), nullable=False),
        sa.Column("systemization_status", E("INCOMPLETE", "IN_PROGRESS", "COMPLETE", name="systemization_status"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_subsystem_id_tenant"),
        sa.UniqueConstraint("tenant_id", "system_id", "subsystem_code", name="uq_cs_subsystem_code_tenant"),
        sa.ForeignKeyConstraint(["system_id", "tenant_id"], ["commissioning_system.id", "commissioning_system.tenant_id"], name="fk_cs_subsystem_system_tenant", ondelete="RESTRICT"),
        sa.CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", name="ck_cs_subsystem_weight"),
        sa.CheckConstraint("weight_a_percent + weight_b_percent + weight_c_percent = 100", name="ck_cs_subsystem_sheet_weights"))
    op.create_index("ix_commissioning_subsystem_tenant_id", "commissioning_subsystem", ["tenant_id"])
    op.create_index("ix_commissioning_subsystem_system_id", "commissioning_subsystem", ["system_id"])

    op.create_table("commissioning_tag",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("tag_number", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("tag_type", sa.String(50)),
        sa.Column("discipline", sa.String(50)),
        sa.Column("validation_status", E("PENDING", "VALIDATED", "REJECTED", name="tag_validation_status"), nullable=False),
        sa.Column("validated_by", sa.Integer()),
        sa.Column("validated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_tag_id_tenant"),
        sa.UniqueConstraint("tenant_id", "tag_number", name="uq_cs_tag_number_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id", "tenant_id"], ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"], name="fk_cs_tag_subsystem_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["validated_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_tag_validator_tenant"))
    op.create_index("ix_commissioning_tag_tenant_id", "commissioning_tag", ["tenant_id"])
    op.create_index("ix_commissioning_tag_subsystem_id", "commissioning_tag", ["subsystem_id"])

    op.create_table("commissioning_attachment",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120)),
        sa.Column("size_bytes", sa.BigInteger()),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("uploaded_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_attachment_id_tenant"),
        sa.UniqueConstraint("tenant_id", "storage_key", name="uq_cs_attachment_storage_tenant"),
        sa.ForeignKeyConstraint(["uploaded_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_attachment_uploader_tenant"))
    op.create_index("ix_commissioning_attachment_tenant_id", "commissioning_attachment", ["tenant_id"])

    op.create_table("commissioning_checksheet",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer()),
        sa.Column("sheet_number", sa.String(100), nullable=False),
        sa.Column("sheet_type", E("A", "B", "C", name="checksheet_type"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", E("DRAFT", "ISSUED", "IN_PROGRESS", "SIGNED_OFF", "REJECTED", name="checksheet_status"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_id", sa.Integer()),
        sa.Column("issued_by", sa.Integer()),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("signed_off_by", sa.Integer()),
        sa.Column("signed_off_at", sa.DateTime(timezone=True)),
        sa.Column("rejected_by", sa.Integer()),
        sa.Column("rejected_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("created_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_checksheet_id_tenant"),
        sa.UniqueConstraint("tenant_id", "sheet_number", "revision", name="uq_cs_sheet_revision_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id", "tenant_id"], ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"], name="fk_cs_checksheet_subsystem_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tag_id", "tenant_id"], ["commissioning_tag.id", "commissioning_tag.tenant_id"], name="fk_cs_checksheet_tag_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id", "tenant_id"], ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"], name="fk_cs_checksheet_supersedes_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_checksheet_issuer_tenant"),
        sa.ForeignKeyConstraint(["signed_off_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_checksheet_signer_tenant"),
        sa.ForeignKeyConstraint(["rejected_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_checksheet_rejector_tenant"),
        sa.ForeignKeyConstraint(["created_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_checksheet_creator_tenant"))
    for column in ("tenant_id", "subsystem_id", "tag_id", "sheet_number", "status"):
        op.create_index("ix_commissioning_checksheet_" + column, "commissioning_checksheet", [column])

    op.create_table("commissioning_checksheet_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("checksheet_id", sa.Integer(), nullable=False),
        sa.Column("item_number", sa.String(30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", sa.Text()),
        sa.Column("result", E("PENDING", "OK", "NOK", "NA", name="checksheet_item_result"), nullable=False),
        sa.Column("remarks", sa.Text()),
        sa.Column("evidence_attachment_id", sa.Integer()),
        sa.Column("checked_by", sa.Integer()),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "checksheet_id", "item_number", name="uq_cs_item_number_tenant"),
        sa.ForeignKeyConstraint(["checksheet_id", "tenant_id"], ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"], name="fk_cs_item_checksheet_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["evidence_attachment_id", "tenant_id"], ["commissioning_attachment.id", "commissioning_attachment.tenant_id"], name="fk_cs_item_attachment_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checked_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_item_checker_tenant"))
    op.create_index("ix_commissioning_checksheet_item_tenant_id", "commissioning_checksheet_item", ["tenant_id"])
    op.create_index("ix_commissioning_checksheet_item_checksheet_id", "commissioning_checksheet_item", ["checksheet_id"])

    op.create_table("commissioning_punch_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("checksheet_id", sa.Integer()),
        sa.Column("punch_number", sa.String(100), nullable=False),
        sa.Column("category", E("A", "B", "C", "D", name="punch_category"), nullable=False),
        sa.Column("status", E("OPEN", "ASSIGNED", "CLOSED", "VERIFIED", "WAIVED", name="punch_status"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("assigned_to", sa.Integer()),
        sa.Column("due_date", sa.Date()),
        sa.Column("closed_by", sa.Integer()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("verified_by", sa.Integer()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("waived_by", sa.Integer()),
        sa.Column("waived_at", sa.DateTime(timezone=True)),
        sa.Column("waiver_reason", sa.Text()),
        sa.Column("created_by", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_punch_id_tenant"),
        sa.UniqueConstraint("tenant_id", "punch_number", name="uq_cs_punch_number_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id", "tenant_id"], ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"], name="fk_cs_punch_subsystem_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checksheet_id", "tenant_id"], ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"], name="fk_cs_punch_checksheet_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_punch_assignee_tenant"),
        sa.ForeignKeyConstraint(["closed_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_punch_closer_tenant"),
        sa.ForeignKeyConstraint(["verified_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_punch_verifier_tenant"),
        sa.ForeignKeyConstraint(["waived_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_punch_waiver_tenant"),
        sa.ForeignKeyConstraint(["created_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_punch_creator_tenant"))
    for column in ("tenant_id", "subsystem_id", "checksheet_id", "punch_number", "status"):
        op.create_index("ix_commissioning_punch_item_" + column, "commissioning_punch_item", [column])

    op.create_table("commissioning_certificate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("subsystem_id", sa.Integer(), nullable=False),
        sa.Column("certificate_number", sa.String(100), nullable=False),
        sa.Column("cert_type", E("MC", "RFC", "RFSU", name="certificate_type"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", E("PENDING", "ISSUED", "REVOKED", name="certificate_status"), nullable=False),
        sa.Column("issued_by", sa.Integer()),
        sa.Column("issued_at", sa.DateTime(timezone=True)),
        sa.Column("signed_by_client", sa.Boolean(), nullable=False),
        sa.Column("signed_by_contractor", sa.Boolean(), nullable=False),
        sa.Column("client_signed_by", sa.Integer()),
        sa.Column("client_signed_at", sa.DateTime(timezone=True)),
        sa.Column("contractor_signed_by", sa.Integer()),
        sa.Column("contractor_signed_at", sa.DateTime(timezone=True)),
        sa.Column("pdf_attachment_id", sa.Integer()),
        sa.Column("remarks", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_cs_certificate_id_tenant"),
        sa.UniqueConstraint("tenant_id", "certificate_number", name="uq_cs_certificate_number_tenant"),
        sa.UniqueConstraint("tenant_id", "subsystem_id", "cert_type", "revision", name="uq_cs_certificate_revision_tenant"),
        sa.ForeignKeyConstraint(["subsystem_id", "tenant_id"], ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"], name="fk_cs_certificate_subsystem_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pdf_attachment_id", "tenant_id"], ["commissioning_attachment.id", "commissioning_attachment.tenant_id"], name="fk_cs_certificate_attachment_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_certificate_issuer_tenant"),
        sa.ForeignKeyConstraint(["client_signed_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_certificate_client_signer_tenant"),
        sa.ForeignKeyConstraint(["contractor_signed_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_certificate_contractor_signer_tenant"))
    for column in ("tenant_id", "subsystem_id", "status"):
        op.create_index("ix_commissioning_certificate_" + column, "commissioning_certificate", [column])

    op.create_table("commissioning_progress_snapshot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("system_id", sa.Integer()),
        sa.Column("subsystem_id", sa.Integer()),
        sa.Column("progress_percent", sa.Float(), nullable=False),
        sa.Column("a_progress", sa.Float(), nullable=False),
        sa.Column("b_progress", sa.Float(), nullable=False),
        sa.Column("c_progress", sa.Float(), nullable=False),
        sa.Column("punch_a_open_count", sa.Integer(), nullable=False),
        sa.Column("punch_b_open_count", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Integer()),
        sa.ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"], name="fk_cs_snapshot_project_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["system_id", "tenant_id"], ["commissioning_system.id", "commissioning_system.tenant_id"], name="fk_cs_snapshot_system_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subsystem_id", "tenant_id"], ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"], name="fk_cs_snapshot_subsystem_tenant", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_snapshot_creator_tenant"))
    for column in ("tenant_id", "project_id", "system_id", "subsystem_id", "captured_at"):
        op.create_index("ix_commissioning_progress_snapshot_" + column, "commissioning_progress_snapshot", [column])

    op.create_table("commissioning_audit_event",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("before_json", sa.JSON()),
        sa.Column("after_json", sa.JSON()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_audit_actor_tenant"))
    for column in ("tenant_id", "actor_user_id", "entity_type", "entity_id", "created_at"):
        op.create_index("ix_commissioning_audit_event_" + column, "commissioning_audit_event", [column])

    op.create_table("commissioning_membership",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(100), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "project_id", "user_id", name="uq_cs_membership_user_project"),
        sa.ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"], name="fk_cs_membership_project_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id", "tenant_id"], ["user.id", "user.company_name"], name="fk_cs_membership_user_tenant"))
    for column in ("tenant_id", "project_id", "user_id"):
        op.create_index("ix_commissioning_membership_" + column, "commissioning_membership", [column])


def downgrade():
    for table in (
        "commissioning_membership", "commissioning_audit_event",
        "commissioning_progress_snapshot", "commissioning_certificate",
        "commissioning_punch_item", "commissioning_checksheet_item",
        "commissioning_checksheet", "commissioning_attachment",
        "commissioning_tag", "commissioning_subsystem", "commissioning_system",
    ):
        op.drop_table(table)
    op.drop_index("uq_user_id_company", table_name="user")
    op.drop_index("uq_project_id_company", table_name="project")
