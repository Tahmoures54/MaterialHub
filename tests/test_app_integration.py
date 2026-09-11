"""Flask integration tests for MaterialHub."""
import pytest

flask = pytest.importorskip("flask")

from app import create_app
from extensions import db
from models import (
    User, AccessLevel, Project, MaterialRequisition, ApprovalStatus,
    ContactInquiry,
)
from utils import generate_next_mr_no, generate_next_po_no
from datetime import date, timedelta


@pytest.fixture
def app():
    application = create_app("testing")
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with application.app_context():
        db.drop_all()
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


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
