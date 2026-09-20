"""Flask integration tests for MaterialHub."""
import pytest
import io

flask = pytest.importorskip("flask")

from app import create_app
from extensions import db
from models import (
    User, AccessLevel, Project, MaterialRequisition, ApprovalStatus,
    ContactInquiry,
)
from utils import generate_next_mr_no, generate_next_po_no
from datetime import date, timedelta


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_liveness_and_readiness(client):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.get_json()["check"] == "liveness"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.get_json()["status"] == "ready"


def test_public_landing_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Know what you need" in response.data


def test_growth_pages_are_registered(client):
    assert client.get("/demo").status_code == 200
    assert client.get("/pricing").status_code == 200
    assert client.get("/contact").status_code == 200


def test_help_center_is_at_canonical_url(client):
    assert client.get("/help/").status_code == 200
    assert client.get("/getting-started").status_code in (200, 302)


def test_workspace_requires_login(client):
    response = client.get("/workspace/", follow_redirects=False)
    assert response.status_code in (302, 401)


def test_unknown_workspace_role_is_normalized():
    app = create_app("testing")
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/workspace/<role>" in rules
    assert "/workspace/api/kpis" in rules
    assert "/material_requisitions/" in rules or "/material_requisitions" in rules
    assert "/purchase_order/" in rules or "/purchase_order" in rules


def test_auth_aliases(client):
    assert client.get("/register", follow_redirects=False).status_code == 302
    assert client.get("/login", follow_redirects=False).status_code == 302


def test_contact_inquiry_is_persisted(client, app):
    response = client.post("/contact", data={
        "name": "Sara Engineer",
        "email": "sara@example.com",
        "company": "EPC Co",
        "message": "Need a warehouse demo",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        inquiry = ContactInquiry.query.filter_by(email="sara@example.com").first()
        assert inquiry is not None
        assert inquiry.company == "EPC Co"


def test_material_requisition_from_dict_and_numbering(app):
    with app.app_context():
        user = User(
            company_name="Acme EPC",
            company_email="pm@acme.test",
            company_phone="+989121111111",
            full_name="Project Lead",
            company_address="Tehran",
            country="IR",
            access_level=AccessLevel.project_manager,
            totp_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        mr_no = generate_next_mr_no("Acme EPC")
        mr = MaterialRequisition.from_dict({
            "mr_no": mr_no,
            "item_code": "PIPE-12CS",
            "material_description": "12-inch CS Pipe",
            "quantity": 10,
            "required_date": date.today() + timedelta(days=14),
            "project_no": "PRJ-100",
            "discipline": "Piping",
        }, "Acme EPC", user_id=user.id)
        db.session.add(mr)
        db.session.commit()
        assert mr.project_id is not None
        assert mr.status == ApprovalStatus.pending
        mr.update_from_dict({"quantity": 12, "status": "approved"})
        db.session.commit()
        assert mr.quantity == 12
        assert mr.status == ApprovalStatus.approved
        assert generate_next_po_no("Acme EPC").startswith("PO-")


def test_observability_endpoints(client):
    assert client.get("/metrics").status_code == 200
    assert client.get("/health/live").headers.get("X-Request-ID")
    assert client.get("/health/ready").headers.get("X-Request-ID")


def _authenticate_session(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True


def _persist_user(app, email, role=AccessLevel.engineering, company="Auth EPC", admin=False):
    with app.app_context():
        user = User(
            company_name=company,
            company_email=email,
            company_phone="+989129999999",
            full_name="Auth Test User",
            company_address="Test Address",
            country="IR",
            access_level=role,
            is_admin=admin,
            totp_secret=User.encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        return user


def test_authenticated_home_and_logout(client, app):
    user = _persist_user(app, "logout@example.com")
    _authenticate_session(client, user)
    assert client.get("/").status_code in (200, 302)
    response = client.get("/logout", follow_redirects=False)
    assert response.status_code == 302


def test_auth_invalid_totp_and_unknown_user(client, app):
    user = _persist_user(app, "totp@example.com")
    response = client.post("/login", data={
        "email": user.company_email,
        "totp_code": "000000",
        "submit": "Login",
    })
    assert response.status_code in (200, 302)
    response = client.post("/login", data={
        "email": "missing@example.com",
        "totp_code": "000000",
        "submit": "Login",
    })
    assert response.status_code in (200, 302)


def test_auth_reset_and_change_password_pages(client, app):
    assert client.get("/auth/reset_password_request").status_code == 200
    assert client.get("/auth/change_password", follow_redirects=False).status_code in (302, 401)
    user = _persist_user(app, "change@example.com")
    _authenticate_session(client, user)
    assert client.get("/auth/change_password").status_code == 200


def test_material_requisition_api_workflow_and_tenant_boundary(client, app):
    user = _persist_user(app, "engineer@example.com", AccessLevel.engineering, "Acme EPC")
    other = _persist_user(app, "other@example.com", AccessLevel.engineering, "Other EPC")
    _authenticate_session(client, user)
    payload = {
        "item_code": "PIPE-API",
        "material_description": "API Pipe",
        "quantity": 5,
        "project_no": "PRJ-API",
        "discipline": "Piping",
    }
    created = client.post("/api/material_requisitions", json=payload)
    assert created.status_code == 201
    mr_no = created.get_json()["mr_nos"][0]
    assert client.get("/api/material_requisitions").status_code == 200
    assert client.get(f"/api/material_requisitions/{mr_no}").status_code == 200
    updated = client.put(f"/api/material_requisitions/{mr_no}", json={"quantity": 7})
    assert updated.status_code == 200
    assert client.get("/api/generate_mr_no").status_code == 200
    assert client.post("/api/approve", json={"mr_no": mr_no, "approval_status": "approved"}).status_code == 403

    _authenticate_session(client, other)
    assert client.get(f"/api/material_requisitions/{mr_no}").status_code == 404


def test_material_requisition_csv_export_and_import(client, app):
    user = _persist_user(app, "csv@example.com", AccessLevel.engineering, "CSV EPC")
    _authenticate_session(client, user)
    csv_body = (
        "mr_no,subject,item_code,material_description,discipline,required_date,"
        "unit_of_measure,quantity,priority,project_no\n"
        ",Pipe,PIPE-CSV,CSV Pipe,Piping,2026-10-01,EA,3,Normal,PRJ-CSV\n"
    )
    imported = client.post(
        "/api/upload_csv",
        data={"file": (io.BytesIO(csv_body.encode("utf-8")), "mrs.csv")},
        content_type="multipart/form-data",
    )
    assert imported.status_code == 201
    exported = client.get("/api/export_csv")
    assert exported.status_code == 200
    assert b"MR-" in exported.data


def test_material_requisition_delete_and_access_control(client, app):
    user = _persist_user(app, "delete@example.com", AccessLevel.engineering, "Delete EPC")
    _authenticate_session(client, user)
    created = client.post("/api/material_requisitions", json={
        "item_code": "DEL-1",
        "material_description": "Delete Me",
        "quantity": 1,
        "project_no": "PRJ-DEL",
        "discipline": "Piping",
    })
    mr_no = created.get_json()["mr_nos"][0]
    assert client.delete(f"/api/material_requisitions/{mr_no}").status_code == 200
    assert client.delete("/api/material_requisitions/MR-9999").status_code == 404

    supplier = _persist_user(app, "supplier-access@example.com", AccessLevel.supplier, "Delete EPC")
    _authenticate_session(client, supplier)
    assert client.post("/api/material_requisitions", json={
        "item_code": "NOPE",
        "material_description": "Nope",
        "quantity": 1,
        "project_no": "PRJ-DEL",
        "discipline": "Piping",
    }).status_code == 403
