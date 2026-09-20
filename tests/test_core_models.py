"""Core domain model regression tests for validation, serialization, and security."""
import pytest
import pyotp
from werkzeug.security import generate_password_hash

from extensions import db
from models import (
    AccessLevel,
    Approval,
    ApprovalStatus,
    Bid,
    BidStatus,
    Delivery,
    DeliveryStatus,
    InspectionStatus,
    MaterialRequisition,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseOrderStatus,
    Project,
    QualityControl,
    SupplierMaterial,
    Tender,
    TenderStatus,
    User,
    ValidationError,
    WarehouseInventory,
    WorkflowStatus,
)
from utils import (
    generate_next_delivery_id,
    generate_next_mr_no,
    generate_next_po_no,
    parse_enum,
)


def make_user(company, email, role=AccessLevel.engineering):
    return User(
        company_name=company,
        company_email=email,
        company_phone="+989121234567",
        full_name="Test User",
        company_address="Test Address",
        country="IR",
        access_level=role,
        totp_confirmed=True,
    )


def test_user_validation_password_totp_and_serialization(app):
    with app.app_context():
        user = make_user("Acme", "core-user@example.com")
        user.set_password("StrongPassword123")
        assert user.check_password("StrongPassword123")
        assert not user.check_password("wrong")
        secret = pyotp.random_base32()
        user.set_totp_secret(secret)
        assert user.totp_secret.startswith("enc:")
        assert user.decrypt_totp_secret() == secret
        assert secret not in user.totp_secret
        assert "company_email" in user.to_dict()
        assert secret not in str(user.to_dict())


def test_user_legacy_werkzeug_hash_is_rehashed(app):
    with app.app_context():
        user = make_user("Acme", "legacy@example.com")
        user.password_hash = generate_password_hash("LegacyPassword123")
        assert user.check_password("LegacyPassword123")
        assert user.password_hash.startswith("$argon2")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"company_email": "bad"},
        {"company_phone": "0"},
        {"full_name": ""},
        {"company_address": ""},
        {"country": ""},
    ],
)
def test_user_rejects_invalid_identity_data(app, kwargs):
    with app.app_context():
        base = dict(
            company_name="Acme",
            company_email="valid@example.com",
            company_phone="+989121234567",
            full_name="Valid User",
            company_address="Address",
            country="IR",
            access_level=AccessLevel.engineering,
        )
        base.update(kwargs)
        with pytest.raises(ValidationError):
            User(**base)


def test_project_and_material_requisition_round_trip(app):
    with app.app_context():
        project = Project(project_no="PRJ-100", project_name="Main Project", company_name="Acme")
        db.session.add(project)
        user = make_user("Acme", "mr-user@example.com")
        db.session.add(user)
        db.session.flush()
        mr = MaterialRequisition.from_dict(
            {
                "mr_no": "MR-1000",
                "subject": "Pipe",
                "item_code": "PIPE-CS",
                "material_description": "Carbon steel pipe",
                "quantity": 10,
                "required_date": "2026-10-01",
                "project_no": "PRJ-100",
                "discipline": "Piping",
                "priority": "High",
            },
            "Acme",
            user.id,
        )
        db.session.add(mr)
        db.session.commit()
        payload = mr.to_dict()
        assert payload["mr_no"] == "MR-1000"
        assert payload["quantity"] == 10
        mr.update_from_dict({"quantity": 12, "status": "approved", "remarks": "Approved"})
        assert mr.quantity == 12
        assert mr.status == ApprovalStatus.approved
        assert mr.remarks == "Approved"


@pytest.mark.parametrize(
    "factory, kwargs",
    [
        (Project, {"project_no": "bad space", "project_name": "P", "company_name": "C"}),
        (MaterialRequisition, {"mr_no": "BAD", "quantity": 1, "item_code": "X", "material_description": "X"}),
        (PurchaseOrder, {"order_no": "BAD", "total_price": 1}),
        (PurchaseOrderItem, {"quantity": 0, "unit_price": 1}),
        (SupplierMaterial, {"price": 0, "available_qty": 1, "material_name": "M", "material_type": "T", "unit": "EA"}),
        (Tender, {"tender_no": "BAD"}),
        (Bid, {"bid_amount": 0}),
        (WarehouseInventory, {"warehouse_id": "BAD", "received_qty": 1, "item_code": "X", "material_description": "X"}),
    ],
)
def test_domain_models_reject_invalid_values(factory, kwargs):
    with pytest.raises(ValidationError):
        factory(**kwargs)


def test_procurement_models_serialize(app):
    with app.app_context():
        project = Project(project_no="PRJ-200", project_name="Project 200", company_name="Acme")
        buyer = make_user("Acme", "buyer@example.com", AccessLevel.purchase)
        supplier = make_user("Acme", "supplier@example.com", AccessLevel.supplier)
        db.session.add_all([project, buyer, supplier])
        db.session.flush()
        po = PurchaseOrder(
            order_no="PO-1000",
            project_id=project.id,
            user_id=buyer.id,
            supplier_id=supplier.id,
            total_price=1250,
            company_name="Acme",
            status=PurchaseOrderStatus.issued,
        )
        db.session.add(po)
        db.session.flush()
        item = PurchaseOrderItem(
            purchase_order_id=po.id,
            material_requisition_id=1,
            quantity=5,
            unit_price=250,
        )
        # Relationship serialization is independently covered even when the MR FK
        # is supplied by a test fixture in a later transaction.
        assert item.to_dict()["unit_price"] == 250
        assert po.to_dict()["order_no"] == "PO-1000"


def test_quality_delivery_warehouse_serialization(app):
    with app.app_context():
        project = Project(project_no="PRJ-300", project_name="Project 300", company_name="Acme")
        user = make_user("Acme", "ops@example.com", AccessLevel.warehouse)
        supplier = make_user("Acme", "supplier2@example.com", AccessLevel.supplier)
        db.session.add_all([project, user, supplier])
        db.session.flush()
        po = PurchaseOrder(
            order_no="PO-2000", project_id=project.id, user_id=user.id,
            supplier_id=supplier.id, total_price=500, company_name="Acme",
        )
        db.session.add(po)
        db.session.flush()
        qc = QualityControl(
            order_id=po.id, user_id=user.id, status=InspectionStatus.passed,
            company_name="Acme",
        )
        delivery = Delivery(
            order_id=po.id, user_id=user.id, delivery_id="DLV-1000",
            status=DeliveryStatus.delivered, company_name="Acme",
        )
        db.session.add_all([qc, delivery])
        db.session.flush()
        warehouse = WarehouseInventory(
            warehouse_id="WH-1000", delivery_id=delivery.delivery_id,
            item_code="PIPE", material_description="Pipe", received_qty=10,
            unit="EA", receipt_date=__import__("datetime").date.today(),
            project_no="PRJ-300", company_name="Acme", user_id=user.id,
        )
        db.session.add(warehouse)
        db.session.commit()
        assert qc.to_dict()["status"] == "passed"
        assert delivery.to_dict()["status"] == "delivered"
        assert warehouse.to_dict()["workflow_status"] == WorkflowStatus.warehouse.value


def test_tender_bid_and_approval_serialization(app):
    with app.app_context():
        project = Project(project_no="PRJ-400", project_name="Project 400", company_name="Acme")
        creator = make_user("Acme", "creator@example.com")
        supplier = make_user("Acme", "supplier3@example.com", AccessLevel.supplier)
        db.session.add_all([project, creator, supplier])
        db.session.flush()
        mr = MaterialRequisition.from_dict(
            {"mr_no": "MR-4000", "item_code": "VALVE", "material_description": "Valve",
             "quantity": 2, "project_no": "PRJ-400", "discipline": "Mechanical"},
            "Acme", creator.id,
        )
        db.session.add(mr)
        db.session.flush()
        tender = Tender(
            tender_no="TND-4000", project_id=project.id,
            material_requisition_id=mr.id, created_by=creator.id,
            company_name="Acme", status=TenderStatus.open,
        )
        db.session.add(tender)
        db.session.flush()
        bid = Bid(
            tender_id=tender.id, supplier_id=supplier.id, bid_amount=100,
            company_name="Acme", status=BidStatus.accepted,
        )
        approval = Approval(
            requisition_id=mr.id, approver_id=creator.id,
            status=ApprovalStatus.approved, company_name="Acme",
        )
        db.session.add_all([bid, approval])
        db.session.commit()
        assert tender.to_dict()["status"] == "open"
        assert bid.to_dict()["status"] == "accepted"
        assert approval.to_dict()["status"] == "approved"


def test_identifier_generators_and_enum_parser(app):
    with app.app_context():
        assert generate_next_mr_no("Acme").startswith("MR-")
        assert generate_next_po_no("Acme").startswith("PO-")
        assert generate_next_delivery_id("Acme").startswith("DLV-")
        assert parse_enum(ApprovalStatus, "approved", ApprovalStatus.pending) == ApprovalStatus.approved
        assert parse_enum(ApprovalStatus, "unknown", ApprovalStatus.pending) == ApprovalStatus.pending
