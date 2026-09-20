#!/usr/bin/env python3
"""
MaterialHub Demo Seed Script
============================
Creates realistic multi-tenant demo data for demos, onboarding and first-launch.

Usage (from project root, with venv + DATABASE_URL / SECRET_KEY set):
    export SEED_DEMO=1
    export FLASK_APP=wsgi.py
    python scripts/seed_demo.py

Inside Docker production stack (after migrate):
    docker compose -f docker-compose.production.yml exec -e SEED_DEMO=1 web \
        python scripts/seed_demo.py

Safety:
- Only runs when SEED_DEMO=1 (or --force)
- Skips if any User already exists (unless --force)
- Never intended for accidental production runs
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.prod")

if os.getenv("SEED_DEMO", "").strip().lower() not in ("1", "true", "yes") and "--force" not in sys.argv:
    print("Refusing to seed. Set SEED_DEMO=1 or pass --force")
    sys.exit(1)

import pyotp
from app import create_app
from extensions import db
from models import (
    AccessLevel,
    ApprovalStatus,
    Bid,
    BidStatus,
    ContactInquiry,
    Delivery,
    DeliveryStatus,
    MaterialRequisition,
    Project,
    PurchaseOrder,
    PurchaseOrderStatus,
    SupplierMaterial,
    Tender,
    TenderStatus,
    User,
    WarehouseInventory,
    WorkflowStatus,
)

DEMO_PASSWORD = "Demo@MaterialHub2026!"  # nosec B105  # Deliberate non-production demo credential; seed is opt-in and docs require rotation.


def create_user(**kwargs) -> User:
    password = kwargs.pop("password", DEMO_PASSWORD)
    user = User(**kwargs)
    user.set_password(password)
    secret = pyotp.random_base32()
    user.set_totp_secret(secret)
    user.totp_confirmed = True
    user.qr_code_base64 = None
    return user


def seed() -> None:
    config_name = os.getenv("FLASK_ENV", "development")
    app = create_app(config_name)

    with app.app_context():
        if User.query.first() and "--force" not in sys.argv:
            print("Database already has users. Aborting (use --force to override).")
            return

        print("Seeding MaterialHub demo data...")

        # ---------- Company A: Persian Gulf Engineering ----------
        company_a = "Persian Gulf Engineering"
        proj_a = Project(
            project_no="PGE-2026-001",
            project_name="South Pars Phase 19 Expansion",
            company_name=company_a,
        )
        db.session.add(proj_a)
        db.session.flush()

        users_a = [
            create_user(
                company_name=company_a,
                company_email="pm@pge.demo",
                full_name="Ali Rezaei",
                company_address="Tehran, Iran",
                country="IR",
                access_level=AccessLevel.project_manager,
                is_admin=True,
                project_id=proj_a.id,
            ),
            create_user(
                company_name=company_a,
                company_email="purchase@pge.demo",
                full_name="Sara Mohammadi",
                company_address="Tehran, Iran",
                country="IR",
                access_level=AccessLevel.purchase,
                project_id=proj_a.id,
            ),
            create_user(
                company_name=company_a,
                company_email="qc@pge.demo",
                full_name="Reza Karimi",
                company_address="Assaluyeh, Iran",
                country="IR",
                access_level=AccessLevel.quality,
                project_id=proj_a.id,
            ),
            create_user(
                company_name=company_a,
                company_email="warehouse@pge.demo",
                full_name="Hossein Ahmadi",
                company_address="Assaluyeh, Iran",
                country="IR",
                access_level=AccessLevel.warehouse,
                project_id=proj_a.id,
            ),
        ]
        db.session.add_all(users_a)
        db.session.flush()
        pm, purchase_user, _qc, warehouse_user = users_a

        mrs = [
            MaterialRequisition(
                mr_no="MR-1001",
                subject="Carbon Steel Pipe for Process Line",
                item_code="PIPE-CS-6IN-SCH40",
                material_description="Seamless Carbon Steel Pipe 6\" SCH40 ASTM A106 Gr.B",
                category="Piping",
                discipline="Piping",
                added_by=pm.full_name,
                edited_by=pm.full_name,
                required_date=date.today() + timedelta(days=30),
                unit_of_measure="m",
                quantity=240.0,
                priority="High",
                project_no=proj_a.project_no,
                project_id=proj_a.id,
                company_name=company_a,
                status=ApprovalStatus.approved,
                user_id=pm.id,
                estimated_cost=18500.0,
            ),
            MaterialRequisition(
                mr_no="MR-1002",
                subject="Gate Valves 4 inch Class 300",
                item_code="VLV-GT-4IN-CL300",
                material_description="Cast Steel Gate Valve 4\" Class 300 RF API 600",
                category="Valves",
                discipline="Piping",
                added_by=pm.full_name,
                edited_by=pm.full_name,
                required_date=date.today() + timedelta(days=45),
                unit_of_measure="pcs",
                quantity=12.0,
                priority="Medium",
                project_no=proj_a.project_no,
                project_id=proj_a.id,
                company_name=company_a,
                status=ApprovalStatus.pending,
                user_id=pm.id,
                estimated_cost=9600.0,
            ),
        ]
        db.session.add_all(mrs)
        db.session.flush()

        # ---------- Company B: Caspian Steel Supply (Supplier) ----------
        company_b = "Caspian Steel Supply"
        supplier_user = create_user(
            company_name=company_b,
            company_email="sales@caspiansteel.demo",
            full_name="Navid Ghorbani",
            company_address="Rasht, Iran",
            country="IR",
            access_level=AccessLevel.supplier,
            store_name="Caspian Main Warehouse",
        )
        db.session.add(supplier_user)
        db.session.flush()

        materials = [
            SupplierMaterial(
                user_id=supplier_user.id,
                material_name="Carbon Steel Pipe 6\" SCH40",
                material_type="Piping",
                price=72.5,
                available_qty=5000.0,
                unit="m",
                delivery_time_days=14,
                country_code="IR",
                company_name=company_b,
            ),
            SupplierMaterial(
                user_id=supplier_user.id,
                material_name="Gate Valve 4\" Class 300",
                material_type="Valves",
                price=780.0,
                available_qty=120.0,
                unit="pcs",
                delivery_time_days=21,
                country_code="IR",
                company_name=company_b,
            ),
            SupplierMaterial(
                user_id=supplier_user.id,
                material_name="Stainless Steel Flange 6\" 150#",
                material_type="Fittings",
                price=95.0,
                available_qty=800.0,
                unit="pcs",
                delivery_time_days=10,
                country_code="IR",
                company_name=company_b,
            ),
        ]
        db.session.add_all(materials)

        # Purchase Order (linked to supplier)
        po = PurchaseOrder(
            order_no="PO-2026-001",
            project_id=proj_a.id,
            user_id=purchase_user.id,
            supplier_id=supplier_user.id,
            status=PurchaseOrderStatus.issued,
            total_price=19200.0,
            issued_date=date.today() - timedelta(days=5),
            company_name=company_a,
            remarks="CS Pipe supply for South Pars Phase 19",
        )
        db.session.add(po)
        db.session.flush()

        # Delivery against the PO
        dlv = Delivery(
            order_id=po.id,
            user_id=warehouse_user.id,
            delivery_id="DLV-2026-001",
            status=DeliveryStatus.in_transit,
            company_name=company_a,
            remarks="In transit via Iranian Shipping Line, tracking ISL-77821",
        )
        db.session.add(dlv)
        db.session.flush()

        # Warehouse inventory
        inv = WarehouseInventory(
            warehouse_id="WH-ASP-01",
            delivery_id=dlv.id,
            item_code="PIPE-CS-6IN-SCH40",
            material_description="Seamless Carbon Steel Pipe 6\" SCH40",
            material_category="Piping",
            received_qty=85.0,
            unit="m",
            storage_location_id="Aisle-B-Rack-12",
            receipt_date=date.today() - timedelta(days=2),
            project_no=proj_a.project_no,
            workflow_status=WorkflowStatus.warehouse,
            company_name=company_a,
            user_id=warehouse_user.id,
        )
        db.session.add(inv)

        # Tender + Bid
        tender = Tender(
            tender_no="TND-2026-001",
            project_id=proj_a.id,
            material_requisition_id=mrs[1].id,
            status=TenderStatus.open,
            created_by=pm.id,
            company_name=company_a,
        )
        db.session.add(tender)
        db.session.flush()

        bid = Bid(
            tender_id=tender.id,
            supplier_id=supplier_user.id,
            bid_amount=28500.0,
            status=BidStatus.pending,
            company_name=company_b,
        )
        db.session.add(bid)

        # Growth / contact inquiry
        inquiry = ContactInquiry(
            name="Demo Visitor",
            email="visitor@example.com",
            company="Future Client Co.",
            message="Interested in a live demo for our EPC project.",
            source="seed",
        )
        db.session.add(inquiry)

        db.session.commit()

        print("✓ Demo data seeded successfully.")
        print()
        print("Demo accounts (password for all: Demo@MaterialHub2026!)")
        print("-" * 60)
        print("  Project Manager : pm@pge.demo")
        print("  Purchase        : purchase@pge.demo")
        print("  Quality         : qc@pge.demo")
        print("  Warehouse       : warehouse@pge.demo")
        print("  Supplier        : sales@caspiansteel.demo")
        print("-" * 60)
        print("IMPORTANT: Change passwords and rotate TOTP after first real use.")
        print("TOTP is pre-confirmed for demo convenience only.")


if __name__ == "__main__":
    seed()
