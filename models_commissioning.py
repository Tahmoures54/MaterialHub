"""OPERA commissioning foundation; tenant_id aliases MaterialHub User.company_name."""
import enum
from datetime import datetime, timezone

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, event, inspect, select
from extensions import db


def utcnow():
    return datetime.now(timezone.utc)


def enum_type(cls, name):
    return db.Enum(cls, name=name, native_enum=False,
                   values_callable=lambda values: [item.value for item in values])


class CommissioningSystemStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class CommissioningStage(str, enum.Enum):
    SYSTEMIZATION = "SYSTEMIZATION"
    CHECKSHEET_EXECUTION = "CHECKSHEET_EXECUTION"
    PUNCH_CLEARANCE = "PUNCH_CLEARANCE"
    CERTIFICATION = "CERTIFICATION"
    HANDOVER = "HANDOVER"


class SystemizationStatus(str, enum.Enum):
    INCOMPLETE = "INCOMPLETE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"


class TagValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class CheckSheetType(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class CheckSheetStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    IN_PROGRESS = "IN_PROGRESS"
    SIGNED_OFF = "SIGNED_OFF"
    REJECTED = "REJECTED"


class CheckSheetItemResult(str, enum.Enum):
    PENDING = "PENDING"
    OK = "OK"
    NOK = "NOK"
    NA = "NA"


class PunchCategory(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PunchStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    CLOSED = "CLOSED"
    VERIFIED = "VERIFIED"
    WAIVED = "WAIVED"


class CertificateType(str, enum.Enum):
    MC = "MC"
    RFC = "RFC"
    RFSU = "RFSU"


class CertificateStatus(str, enum.Enum):
    PENDING = "PENDING"
    ISSUED = "ISSUED"
    REVOKED = "REVOKED"


class CommissioningSystem(db.Model):
    __tablename__ = "commissioning_system"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_system_id_tenant"),
        UniqueConstraint("tenant_id", "project_id", "system_code", name="uq_cs_system_code_tenant"),
        ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"],
                             name="fk_cs_system_project_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, nullable=False, index=True)
    system_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(enum_type(CommissioningSystemStatus, "commissioning_system_status"),
                       nullable=False, default=CommissioningSystemStatus.PLANNED)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    project = db.relationship("Project", viewonly=True)


class CommissioningSubsystem(db.Model):
    __tablename__ = "commissioning_subsystem"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_subsystem_id_tenant"),
        UniqueConstraint("tenant_id", "system_id", "subsystem_code", name="uq_cs_subsystem_code_tenant"),
        ForeignKeyConstraint(["system_id", "tenant_id"],
                             ["commissioning_system.id", "commissioning_system.tenant_id"],
                             name="fk_cs_subsystem_system_tenant", ondelete="RESTRICT"),
        db.CheckConstraint("weight_percent >= 0 AND weight_percent <= 100", name="ck_cs_subsystem_weight"),
        db.CheckConstraint(
            "weight_a_percent + weight_b_percent + weight_c_percent = 100",
            name="ck_cs_subsystem_sheet_weights"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    system_id = db.Column(db.Integer, nullable=False, index=True)
    subsystem_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    weight_percent = db.Column(db.Float, nullable=False, default=100.0)
    weight_a_percent = db.Column(db.Float, nullable=False, default=30.0)
    weight_b_percent = db.Column(db.Float, nullable=False, default=40.0)
    weight_c_percent = db.Column(db.Float, nullable=False, default=30.0)
    lifecycle_stage = db.Column(enum_type(CommissioningStage, "commissioning_stage"),
                                nullable=False, default=CommissioningStage.SYSTEMIZATION)
    systemization_status = db.Column(enum_type(SystemizationStatus, "systemization_status"),
                                     nullable=False, default=SystemizationStatus.INCOMPLETE)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    system = db.relationship("CommissioningSystem", viewonly=True)


class CommissioningTag(db.Model):
    __tablename__ = "commissioning_tag"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_tag_id_tenant"),
        UniqueConstraint("tenant_id", "tag_number", name="uq_cs_tag_number_tenant"),
        ForeignKeyConstraint(["subsystem_id", "tenant_id"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"],
                             name="fk_cs_tag_subsystem_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    subsystem_id = db.Column(db.Integer, nullable=False, index=True)
    tag_number = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    tag_type = db.Column(db.String(50))
    discipline = db.Column(db.String(50))
    validation_status = db.Column(enum_type(TagValidationStatus, "tag_validation_status"),
                                  nullable=False, default=TagValidationStatus.PENDING)
    validated_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    validated_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    subsystem = db.relationship("CommissioningSubsystem", viewonly=True)


class CommissioningAttachment(db.Model):
    __tablename__ = "commissioning_attachment"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_attachment_id_tenant"),
        UniqueConstraint("tenant_id", "storage_key", name="uq_cs_attachment_storage_tenant"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    storage_key = db.Column(db.String(500), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(120))
    size_bytes = db.Column(db.BigInteger)
    checksum_sha256 = db.Column(db.String(64))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)


class CheckSheet(db.Model):
    __tablename__ = "commissioning_checksheet"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_checksheet_id_tenant"),
        UniqueConstraint("tenant_id", "sheet_number", "revision", name="uq_cs_sheet_revision_tenant"),
        ForeignKeyConstraint(["subsystem_id", "tenant_id"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"],
                             name="fk_cs_checksheet_subsystem_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tag_id", "tenant_id"],
                             ["commissioning_tag.id", "commissioning_tag.tenant_id"],
                             name="fk_cs_checksheet_tag_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["supersedes_id", "tenant_id"],
                             ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"],
                             name="fk_cs_checksheet_supersedes_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    subsystem_id = db.Column(db.Integer, nullable=False, index=True)
    tag_id = db.Column(db.Integer, index=True)
    sheet_number = db.Column(db.String(100), nullable=False, index=True)
    sheet_type = db.Column(enum_type(CheckSheetType, "checksheet_type"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(enum_type(CheckSheetStatus, "checksheet_status"),
                       nullable=False, default=CheckSheetStatus.DRAFT, index=True)
    revision = db.Column(db.Integer, nullable=False, default=0)
    supersedes_id = db.Column(db.Integer)
    issued_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    issued_at = db.Column(db.DateTime(timezone=True))
    signed_off_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    signed_off_at = db.Column(db.DateTime(timezone=True))
    rejected_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    rejected_at = db.Column(db.DateTime(timezone=True))
    rejection_reason = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    subsystem = db.relationship("CommissioningSubsystem", viewonly=True)
    tag = db.relationship("CommissioningTag", viewonly=True)
    items = db.relationship("CheckSheetItem", back_populates="checksheet",
                            order_by="CheckSheetItem.sort_order")


class CheckSheetItem(db.Model):
    __tablename__ = "commissioning_checksheet_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "checksheet_id", "item_number", name="uq_cs_item_number_tenant"),
        ForeignKeyConstraint(["checksheet_id", "tenant_id"],
                             ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"],
                             name="fk_cs_item_checksheet_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["evidence_attachment_id", "tenant_id"],
                             ["commissioning_attachment.id", "commissioning_attachment.tenant_id"],
                             name="fk_cs_item_attachment_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    checksheet_id = db.Column(db.Integer, nullable=False, index=True)
    item_number = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=False)
    acceptance_criteria = db.Column(db.Text)
    result = db.Column(enum_type(CheckSheetItemResult, "checksheet_item_result"),
                       nullable=False, default=CheckSheetItemResult.PENDING)
    remarks = db.Column(db.Text)
    evidence_attachment_id = db.Column(db.Integer)
    checked_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    checked_at = db.Column(db.DateTime(timezone=True))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    checksheet = db.relationship("CheckSheet", back_populates="items")


class PunchItem(db.Model):
    __tablename__ = "commissioning_punch_item"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_punch_id_tenant"),
        UniqueConstraint("tenant_id", "punch_number", name="uq_cs_punch_number_tenant"),
        ForeignKeyConstraint(["subsystem_id", "tenant_id"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"],
                             name="fk_cs_punch_subsystem_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["checksheet_id", "tenant_id"],
                             ["commissioning_checksheet.id", "commissioning_checksheet.tenant_id"],
                             name="fk_cs_punch_checksheet_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    subsystem_id = db.Column(db.Integer, nullable=False, index=True)
    checksheet_id = db.Column(db.Integer, index=True)
    punch_number = db.Column(db.String(100), nullable=False, index=True)
    category = db.Column(enum_type(PunchCategory, "punch_category"), nullable=False)
    status = db.Column(enum_type(PunchStatus, "punch_status"), nullable=False,
                       default=PunchStatus.OPEN, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    assigned_to = db.Column(db.Integer, db.ForeignKey("user.id"))
    due_date = db.Column(db.Date)
    closed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    closed_at = db.Column(db.DateTime(timezone=True))
    verified_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    verified_at = db.Column(db.DateTime(timezone=True))
    waived_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    waived_at = db.Column(db.DateTime(timezone=True))
    waiver_reason = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class Certificate(db.Model):
    __tablename__ = "commissioning_certificate"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_cs_certificate_id_tenant"),
        UniqueConstraint("tenant_id", "certificate_number", name="uq_cs_certificate_number_tenant"),
        UniqueConstraint("tenant_id", "subsystem_id", "cert_type", "revision",
                         name="uq_cs_certificate_revision_tenant"),
        ForeignKeyConstraint(["subsystem_id", "tenant_id"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"],
                             name="fk_cs_certificate_subsystem_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["pdf_attachment_id", "tenant_id"],
                             ["commissioning_attachment.id", "commissioning_attachment.tenant_id"],
                             name="fk_cs_certificate_attachment_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    subsystem_id = db.Column(db.Integer, nullable=False, index=True)
    certificate_number = db.Column(db.String(100), nullable=False)
    cert_type = db.Column(enum_type(CertificateType, "certificate_type"), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(enum_type(CertificateStatus, "certificate_status"),
                       nullable=False, default=CertificateStatus.PENDING, index=True)
    issued_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    issued_at = db.Column(db.DateTime(timezone=True))
    signed_by_client = db.Column(db.Boolean, nullable=False, default=False)
    signed_by_contractor = db.Column(db.Boolean, nullable=False, default=False)
    client_signed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    client_signed_at = db.Column(db.DateTime(timezone=True))
    contractor_signed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    contractor_signed_at = db.Column(db.DateTime(timezone=True))
    pdf_attachment_id = db.Column(db.Integer)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProgressSnapshot(db.Model):
    __tablename__ = "commissioning_progress_snapshot"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"],
                             name="fk_cs_snapshot_project_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["system_id", "tenant_id"],
                             ["commissioning_system.id", "commissioning_system.tenant_id"],
                             name="fk_cs_snapshot_system_tenant", ondelete="RESTRICT"),
        ForeignKeyConstraint(["subsystem_id", "tenant_id"],
                             ["commissioning_subsystem.id", "commissioning_subsystem.tenant_id"],
                             name="fk_cs_snapshot_subsystem_tenant", ondelete="RESTRICT"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, nullable=False, index=True)
    system_id = db.Column(db.Integer, index=True)
    subsystem_id = db.Column(db.Integer, index=True)
    progress_percent = db.Column(db.Float, nullable=False, default=0.0)
    a_progress = db.Column(db.Float, nullable=False, default=0.0)
    b_progress = db.Column(db.Float, nullable=False, default=0.0)
    c_progress = db.Column(db.Float, nullable=False, default=0.0)
    punch_a_open_count = db.Column(db.Integer, nullable=False, default=0)
    punch_b_open_count = db.Column(db.Integer, nullable=False, default=0)
    captured_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))


class CommissioningAuditEvent(db.Model):
    __tablename__ = "commissioning_audit_event"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(80), nullable=False)
    before_json = db.Column(db.JSON)
    after_json = db.Column(db.JSON)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class CommissioningMembership(db.Model):
    __tablename__ = "commissioning_membership"
    __table_args__ = (
        UniqueConstraint("tenant_id", "project_id", "user_id", name="uq_cs_membership_user_project"),
        ForeignKeyConstraint(["project_id", "tenant_id"], ["project.id", "project.company_name"],
                             name="fk_cs_membership_project_tenant", ondelete="CASCADE"),
    )
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.String(100), nullable=False, index=True)
    project_id = db.Column(db.Integer, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    role = db.Column(db.String(40), nullable=False, default="viewer")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    user = db.relationship("User", viewonly=True)


def _reject_signed_checksheet_update(mapper, connection, target):
    history = inspect(target).attrs.status.history
    if history.deleted and history.deleted[0] == CheckSheetStatus.SIGNED_OFF:
        raise ValueError("Signed-off CheckSheets are immutable; create a new revision.")
    if not history.deleted:
        stored = connection.execute(
            select(CheckSheet.status).where(CheckSheet.id == target.id)
        ).scalar_one_or_none()
        if stored in (CheckSheetStatus.SIGNED_OFF, CheckSheetStatus.SIGNED_OFF.value):
            raise ValueError("Signed-off CheckSheets are immutable; create a new revision.")


def _reject_signed_checksheet_delete(mapper, connection, target):
    if target.status in (CheckSheetStatus.SIGNED_OFF, CheckSheetStatus.SIGNED_OFF.value):
        raise ValueError("Signed-off CheckSheets cannot be deleted.")


def _reject_item_mutation_after_signoff(mapper, connection, target):
    stored = connection.execute(
        select(CheckSheet.status).where(
            CheckSheet.id == target.checksheet_id,
            CheckSheet.tenant_id == target.tenant_id,
        )
    ).scalar_one_or_none()
    if stored in (CheckSheetStatus.SIGNED_OFF, CheckSheetStatus.SIGNED_OFF.value):
        raise ValueError("Items of a signed-off CheckSheet are immutable.")


def _reject_audit_mutation(mapper, connection, target):
    raise ValueError("Commissioning audit events are immutable.")


event.listen(CheckSheet, "before_update", _reject_signed_checksheet_update)
event.listen(CheckSheet, "before_delete", _reject_signed_checksheet_delete)
event.listen(CheckSheetItem, "before_update", _reject_item_mutation_after_signoff)
event.listen(CheckSheetItem, "before_delete", _reject_item_mutation_after_signoff)
event.listen(CommissioningAuditEvent, "before_update", _reject_audit_mutation)
event.listen(CommissioningAuditEvent, "before_delete", _reject_audit_mutation)
