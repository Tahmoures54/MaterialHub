"""OPERA Phase 1 model, tenant-boundary, numbering and immutability tests."""
import pytest
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Project, DocumentSequence, User, AccessLevel
from models_commissioning import (
    CheckSheet, CheckSheetItem, CheckSheetItemResult, CheckSheetStatus, CheckSheetType,
    CommissioningMembership, CommissioningSubsystem, CommissioningSystem, CommissioningSystemStatus, SystemizationStatus,
)
from services.commissioning_number_service import next_commissioning_number, format_checksheet_number


def hierarchy(company, project_no):
    project = Project(project_no=project_no, project_name=project_no, company_name=company)
    db.session.add(project)
    db.session.flush()
    system = CommissioningSystem(tenant_id=company, project_id=project.id,
                                 system_code="SYS-01", name="System 01",
                                 status=CommissioningSystemStatus.ACTIVE)
    db.session.add(system)
    db.session.flush()
    subsystem = CommissioningSubsystem(tenant_id=company, system_id=system.id,
                                       subsystem_code="SS-01", name="Subsystem 01",
                                       systemization_status=SystemizationStatus.COMPLETE)
    db.session.add(subsystem)
    db.session.flush()
    return project, system, subsystem


def test_opera_hierarchy_uses_existing_project_and_tenant_alias(app):
    with app.app_context():
        _, system, subsystem = hierarchy("Tenant A", "TA-01")
        db.session.commit()
        assert system.tenant_id == subsystem.tenant_id == "Tenant A"
        assert system.project.project_no == "TA-01"


def test_system_cannot_reference_another_tenant_project(app):
    with app.app_context():
        project_a, _, _ = hierarchy("Tenant A", "TA-02")
        db.session.add(Project(project_no="TB-02", project_name="TB-02", company_name="Tenant B"))
        db.session.flush()
        db.session.add(CommissioningSystem(tenant_id="Tenant B", project_id=project_a.id,
                                           system_code="SYS-X", name="Cross-tenant"))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_numbering_is_atomic_sequence_per_tenant(app):
    with app.app_context():
        assert [next_commissioning_number("Tenant A", "CS-A") for _ in range(2)] == [1, 2]
        assert next_commissioning_number("Tenant B", "CS-A") == 1
        assert format_checksheet_number("P-01", "A", 2) == "P-01-A-00002"
        assert DocumentSequence.query.filter_by(key="CS-A", company_name="Tenant A").one().last_value == 2


def test_signed_off_checksheet_and_items_cannot_be_modified(app):
    with app.app_context():
        _, _, subsystem = hierarchy("Tenant A", "TA-03")
        sheet = CheckSheet(tenant_id="Tenant A", subsystem_id=subsystem.id,
                           sheet_number="TA-03-A-00001", sheet_type=CheckSheetType.A,
                           title="Signed", status=CheckSheetStatus.SIGNED_OFF, revision=0)
        db.session.add(sheet)
        db.session.flush()
        item = CheckSheetItem(tenant_id="Tenant A", checksheet_id=sheet.id,
                              item_number="01", description="Inspect", result=CheckSheetItemResult.OK)
        db.session.add(item)
        db.session.commit()
        sheet.title = "Tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.session.flush()
        db.session.rollback()
        item = CheckSheetItem.query.one()
        item.remarks = "Tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.session.flush()
        db.session.rollback()


def test_checksheet_revision_key_is_unique(app):
    with app.app_context():
        _, _, subsystem = hierarchy("Tenant A", "TA-04")
        db.session.add_all([
            CheckSheet(tenant_id="Tenant A", subsystem_id=subsystem.id, sheet_number="TA-04-A-1",
                       sheet_type=CheckSheetType.A, title="Rev 0", revision=0),
            CheckSheet(tenant_id="Tenant A", subsystem_id=subsystem.id, sheet_number="TA-04-A-1",
                       sheet_type=CheckSheetType.A, title="Duplicate", revision=0),
        ])
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()


def test_membership_rejects_user_from_another_tenant(app):
    with app.app_context():
        project, _, _ = hierarchy("Tenant A", "TA-05")
        foreign_user = User(
            company_name="Tenant B",
            company_email="tenant-b-user@example.com",
            company_phone="+989121234567",
            full_name="Tenant B User",
            company_address="Test",
            country="IR",
            access_level=AccessLevel.engineering,
            totp_confirmed=True,
        )
        db.session.add(foreign_user)
        db.session.flush()
        db.session.add(CommissioningMembership(
            tenant_id="Tenant A", project_id=project.id, user_id=foreign_user.id, role="viewer"
        ))
        with pytest.raises(IntegrityError):
            db.session.flush()
        db.session.rollback()
