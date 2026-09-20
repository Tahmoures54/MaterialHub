"""Unit tests for shared authorization, numbering, enum, and CSRF helpers."""
from flask import jsonify

from models import AccessLevel, ApprovalStatus, User
from utils import (
    _next_from_last_value,
    csrf_token_from_request,
    generate_document_number,
    generate_next_delivery_id,
    generate_next_mr_no,
    generate_next_po_no,
    generate_next_warehouse_id,
    parse_enum,
    role_required,
)


def test_document_number_helpers():
    assert generate_document_number("MR") == "MR-0001"
    assert generate_document_number("PO", 12) == "PO-0013"
    assert _next_from_last_value("MR", "MR-0042") == "MR-0043"
    assert _next_from_last_value("MR", "legacy") == "MR-0001"


def test_next_document_numbers_are_tenant_scoped(app):
    with app.app_context():
        assert generate_next_mr_no("NoRows") == "MR-0001"
        assert generate_next_po_no("NoRows") == "PO-0001"
        assert generate_next_delivery_id("NoRows") == "DLV-0001"
        assert generate_next_warehouse_id("NoRows") == "WH-0001"


def test_parse_enum_handles_all_supported_inputs():
    assert parse_enum(ApprovalStatus, ApprovalStatus.approved) is ApprovalStatus.approved
    assert parse_enum(ApprovalStatus, "approved") is ApprovalStatus.approved
    assert parse_enum(ApprovalStatus, "APPROVED") is ApprovalStatus.approved
    assert parse_enum(ApprovalStatus, None, ApprovalStatus.pending) is ApprovalStatus.pending
    assert parse_enum(ApprovalStatus, "unknown", ApprovalStatus.pending) is ApprovalStatus.pending


def test_role_required_allows_admin_and_rejects_wrong_role(app, client):
    with app.app_context():
        admin = User(
            company_name="Utils EPC",
            company_email="utils-admin@example.com",
            company_phone="+989121111222",
            full_name="Admin",
            company_address="Address",
            country="IR",
            access_level=AccessLevel.engineering,
            is_admin=True,
            totp_confirmed=True,
        )
        buyer = User(
            company_name="Utils EPC",
            company_email="utils-buyer@example.com",
            company_phone="+989121111223",
            full_name="Buyer",
            company_address="Address",
            country="IR",
            access_level=AccessLevel.purchase,
            totp_confirmed=True,
        )
        from extensions import db
        db.session.add_all([admin, buyer])
        db.session.commit()

        @role_required(AccessLevel.purchase)
        def protected():
            return jsonify({"ok": True})

        from flask_login import login_user, logout_user

        with client:
            with client.session_transaction() as session:
                session["_user_id"] = str(admin.id)
                session["_fresh"] = True
            assert client.get("/").status_code in (200, 302)

        with app.test_request_context("/protected"):
            login_user(buyer)
            response = protected()
            assert response.get_json()["ok"] is True
            logout_user()


def test_csrf_token_reader(app):
    with app.test_request_context("/x", headers={"X-CSRFToken": "header-token"}):
        assert csrf_token_from_request() == "header-token"
    with app.test_request_context("/x", method="POST", data={"csrf_token": "form-token"}):
        assert csrf_token_from_request() == "form-token"
    with app.test_request_context("/x", method="POST", json={"csrf_token": "json-token"}):
        assert csrf_token_from_request() == "json-token"
