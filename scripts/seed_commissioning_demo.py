#!/usr/bin/env python3
"""Opt-in, idempotent OPERA commissioning demonstration seed."""
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.prod")

if os.getenv("SEED_COMMISSIONING_DEMO", "").lower() not in {"1", "true", "yes"} and "--force" not in sys.argv:
    raise SystemExit("Set SEED_COMMISSIONING_DEMO=1 or pass --force.")

from app import create_app
from extensions import db
from models import Project
from models_commissioning import (
    Certificate, CertificateStatus, CertificateType, CheckSheet, CheckSheetItem,
    CheckSheetItemResult, CheckSheetStatus, CheckSheetType, CommissioningStage,
    CommissioningSubsystem, CommissioningSystem, CommissioningSystemStatus,
    CommissioningTag, PunchCategory, PunchItem, PunchStatus,
    SystemizationStatus, TagValidationStatus,
)
from services.commissioning_number_service import (
    SEQUENCE_KEYS, format_checksheet_number, format_punch_number, next_commissioning_number,
)

COMPANY = os.getenv("OPERA_DEMO_COMPANY", "OPERA Demo EPC")
PROJECT_NO = os.getenv("OPERA_DEMO_PROJECT_NO", "OPERA-DEMO-001")


def seed():
    app = create_app(os.getenv("FLASK_ENV", "development"))
    with app.app_context():
        project = Project.query.filter_by(project_no=PROJECT_NO, company_name=COMPANY).first()
        if project and CommissioningSystem.query.filter_by(project_id=project.id, tenant_id=COMPANY).first():
            print("Demo project already seeded; no changes made.")
            return
        if project is None:
            project = Project(project_no=PROJECT_NO, project_name="OPERA Demonstration Project", company_name=COMPANY)
            db.session.add(project)
            db.session.flush()

        now = datetime.now(timezone.utc)
        systems = [
            CommissioningSystem(tenant_id=COMPANY, project_id=project.id, system_code="SYS-100",
                                name="Utilities and Offsites", status=CommissioningSystemStatus.ACTIVE),
            CommissioningSystem(tenant_id=COMPANY, project_id=project.id, system_code="SYS-200",
                                name="Process Area", status=CommissioningSystemStatus.ACTIVE),
        ]
        db.session.add_all(systems)
        db.session.flush()
        subsystems = [
            CommissioningSubsystem(tenant_id=COMPANY, system_id=systems[0].id, subsystem_code="SS-110",
                                   name="Instrument Air", weight_percent=60,
                                   lifecycle_stage=CommissioningStage.CERTIFICATION,
                                   systemization_status=SystemizationStatus.COMPLETE),
            CommissioningSubsystem(tenant_id=COMPANY, system_id=systems[0].id, subsystem_code="SS-120",
                                   name="Cooling Water", weight_percent=40,
                                   lifecycle_stage=CommissioningStage.CHECKSHEET_EXECUTION,
                                   systemization_status=SystemizationStatus.COMPLETE),
            CommissioningSubsystem(tenant_id=COMPANY, system_id=systems[1].id, subsystem_code="SS-210",
                                   name="Feed Gas", weight_percent=100,
                                   lifecycle_stage=CommissioningStage.SYSTEMIZATION,
                                   systemization_status=SystemizationStatus.COMPLETE),
        ]
        db.session.add_all(subsystems)
        db.session.flush()

        tag_data = [
            ("IA-COMP-001", "Instrument air compressor", 0),
            ("IA-DRY-001", "Instrument air dryer", 0),
            ("IA-REC-001", "Instrument air receiver", 0),
            ("IA-PSV-001", "Instrument air pressure safety valve", 0),
            ("CW-PMP-001", "Cooling water pump A", 1),
            ("CW-PMP-002", "Cooling water pump B", 1),
            ("CW-HX-001", "Cooling water heat exchanger", 1),
            ("FG-FCV-001", "Feed gas control valve", 2),
            ("FG-PT-001", "Feed gas pressure transmitter", 2),
            ("FG-ESD-001", "Feed gas ESD valve", 2),
        ]
        tags = [CommissioningTag(
            tenant_id=COMPANY, subsystem_id=subsystems[sub], tag_number=number,
            description=description, tag_type="EQUIPMENT", discipline="Mechanical",
            validation_status=TagValidationStatus.VALIDATED,
        ) for number, description, sub in tag_data]
        db.session.add_all(tags)
        db.session.flush()

        statuses = [CheckSheetStatus.SIGNED_OFF, CheckSheetStatus.SIGNED_OFF,
                    CheckSheetStatus.IN_PROGRESS, CheckSheetStatus.ISSUED, CheckSheetStatus.DRAFT]
        for sheet_type, count in ((CheckSheetType.A, 5), (CheckSheetType.B, 5), (CheckSheetType.C, 3)):
            for index in range(count):
                subsystem_index = 0 if index < 2 else (1 if index % 2 == 0 else 2)
                status = statuses[index]
                if sheet_type == CheckSheetType.C and status == CheckSheetStatus.SIGNED_OFF:
                    status = CheckSheetStatus.ISSUED
                sequence = next_commissioning_number(COMPANY, SEQUENCE_KEYS[sheet_type.value])
                sheet = CheckSheet(
                    tenant_id=COMPANY, subsystem_id=subsystems[subsystem_index].id,
                    tag_id=tags[(index + subsystem_index) % len(tags)].id,
                    sheet_number=format_checksheet_number(PROJECT_NO, sheet_type.value, sequence),
                    sheet_type=sheet_type, title=f"{sheet_type.value}-Sheet {index + 1}",
                    status=status, revision=0,
                    issued_at=now - timedelta(days=3) if status != CheckSheetStatus.DRAFT else None,
                    signed_off_at=now - timedelta(days=1) if status == CheckSheetStatus.SIGNED_OFF else None,
                )
                db.session.add(sheet)
                db.session.flush()
                for item_no in range(1, 4):
                    result = CheckSheetItemResult.OK if status == CheckSheetStatus.SIGNED_OFF else (
                        CheckSheetItemResult.PENDING if item_no == 3 else CheckSheetItemResult.NOK)
                    db.session.add(CheckSheetItem(
                        tenant_id=COMPANY, checksheet_id=sheet.id, item_number=f"{item_no:02d}",
                        description=f"Inspection / test point {item_no}",
                        acceptance_criteria="Meet approved project specification.",
                        result=result, sort_order=item_no,
                    ))

        punch_data = [
            (PunchCategory.A, PunchStatus.VERIFIED, 0, "Foundation grouting verified"),
            (PunchCategory.A, PunchStatus.OPEN, 1, "Access platform handrail incomplete"),
            (PunchCategory.B, PunchStatus.ASSIGNED, 0, "Calibration record pending"),
            (PunchCategory.B, PunchStatus.WAIVED, 1, "Minor insulation label correction"),
            (PunchCategory.C, PunchStatus.OPEN, 1, "Painting touch-up required"),
            (PunchCategory.C, PunchStatus.CLOSED, 2, "Cable tray identification"),
            (PunchCategory.D, PunchStatus.OPEN, 2, "Cosmetic coating mark"),
            (PunchCategory.D, PunchStatus.VERIFIED, 0, "Nameplate cleaning"),
        ]
        for category, status, sub_index, title in punch_data:
            seq = next_commissioning_number(COMPANY, SEQUENCE_KEYS[f"PUNCH-{category.value}"])
            db.session.add(PunchItem(
                tenant_id=COMPANY, subsystem_id=subsystems[sub_index].id,
                punch_number=format_punch_number(PROJECT_NO, category.value, seq),
                category=category, status=status, title=title,
                description=f"Demonstration punch: {title}.",
                due_date=date.today() + timedelta(days=7),
                closed_at=now - timedelta(days=1) if status in {
                    PunchStatus.CLOSED, PunchStatus.VERIFIED, PunchStatus.WAIVED} else None,
                verified_at=now - timedelta(hours=12) if status == PunchStatus.VERIFIED else None,
                waived_at=now - timedelta(hours=12) if status == PunchStatus.WAIVED else None,
                waiver_reason="Accepted for demo." if status == PunchStatus.WAIVED else None,
            ))

        db.session.add_all([
            Certificate(
                tenant_id=COMPANY, subsystem_id=subsystems[0].id,
                certificate_number=f"{PROJECT_NO}-MC-00001", cert_type=CertificateType.MC,
                revision=0, status=CertificateStatus.ISSUED, issued_at=now - timedelta(days=1),
                signed_by_client=True, signed_by_contractor=True,
            ),
            Certificate(
                tenant_id=COMPANY, subsystem_id=subsystems[0].id,
                certificate_number=f"{PROJECT_NO}-RFC-00001", cert_type=CertificateType.RFC,
                revision=0, status=CertificateStatus.PENDING,
                signed_by_client=False, signed_by_contractor=False,
            ),
        ])
        db.session.commit()
        print("Seeded 1 project, 2 systems, 3 subsystems, 10 tags, 5 A, 5 B, 3 C sheets, "
              "8 punches, 1 issued MC and 1 pending RFC.")


if __name__ == "__main__":
    seed()
