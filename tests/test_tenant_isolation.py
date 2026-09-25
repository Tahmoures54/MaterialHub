"""Regression tests for multi-tenant data isolation.

Covers:
- tenant-scoped document numbering (independent sequences)
- shared project numbers across companies
- API-level isolation (MR, inventory, reports)
- central tenant helpers (company_filter / tenant_query / require_same_tenant)
"""
import pytest

from extensions import db
from models import (
    User, AccessLevel, Project, MaterialRequisition, MaterialMaster,
    WarehouseInventory,
)
from utils import (
    generate_next_mr_no,
    company_filter,
    tenant_query,
    require_same_tenant,
)
from tests.test_app_integration import _persist_user, _authenticate_session, _ensure_test_material


def _create_mr(client, user, item, project_no="PRJ-SHARED"):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    with client.application.app_context():
        material = MaterialMaster(
            material_code=item, family_code="PIP", material_name=item,
            description=item, unit="EA", discipline="Piping",
            fingerprint=(f"test:{user.company_name}:{item}").encode().hex().ljust(64, "0")[:64],
            company_name=user.company_name, created_by=user.id,
            status="active", lifecycle_status="active",
        )
        db.session.add(material)
        db.session.commit()
        material_id = material.id
    return client.post("/material_requisitions/api/material_requisitions", json={
        "material_id": material_id,
        "item_code": item,
        "material_description": item,
        "quantity": 1,
        "project_no": project_no,
        "discipline": "Piping",
    })


def test_two_companies_can_share_project_number(client, app):
    """Same project_no across tenants must not collide (was a global UNIQUE)."""
    a = _persist_user(app, "shared-proj-a@example.com", AccessLevel.engineering, "Tenant A")
    b = _persist_user(app, "shared-proj-b@example.com", AccessLevel.engineering, "Tenant B")

    ra = _create_mr(client, a, "PIPE-A")
    rb = _create_mr(client, b, "PIPE-B")

    assert ra.status_code == 201, ra.get_json()
    assert rb.status_code == 201, rb.get_json()
    # Each tenant owns its own first number.
    assert ra.get_json()["mr_nos"] == ["MR-0001"]
    assert rb.get_json()["mr_nos"] == ["MR-0001"]

    with app.app_context():
        projects = Project.query.all()
        # Two rows, same project_no, different tenants.
        assert len(projects) == 2
        assert {p.project_no for p in projects} == {"PRJ-SHARED"}
        assert {p.company_name for p in projects} == {"Tenant A", "Tenant B"}


def test_document_numbers_are_independent_per_tenant(client, app):
    a = _persist_user(app, "seq-a@example.com", AccessLevel.engineering, "Seq A")
    b = _persist_user(app, "seq-b@example.com", AccessLevel.engineering, "Seq B")

    assert _create_mr(client, a, "A-1").status_code == 201
    assert _create_mr(client, a, "A-2").status_code == 201

    rb = _create_mr(client, b, "B-1")
    assert rb.status_code == 201
    # Tenant B is unaffected by Tenant A's consumption.
    assert rb.get_json()["mr_nos"] == ["MR-0001"]


def test_mr_sequence_increments_within_tenant(app):
    with app.app_context():
        assert generate_next_mr_no("Solo Co") == "MR-0001"
        assert generate_next_mr_no("Solo Co") == "MR-0002"
        assert generate_next_mr_no("Solo Co") == "MR-0003"
        # A different tenant starts its own sequence.
        assert generate_next_mr_no("Other Co") == "MR-0001"


def test_sequence_seeds_from_existing_documents(app):
    """Legacy data (documents without a sequence row) keeps numbering."""
    with app.app_context():
        user = User(
            company_name="Legacy Co",
            company_email="legacy@example.com",
            company_phone="+989130000001",
            full_name="Legacy",
            company_address="A",
            country="IR",
            access_level=AccessLevel.engineering,
            totp_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        material = MaterialMaster(
            material_code="LEG-1", family_code="PIP", material_name="Legacy pipe",
            description="Legacy pipe", unit="EA", discipline="Piping",
            fingerprint=("test:Legacy Co:LEG-1").encode().hex().ljust(64, "0")[:64],
            company_name="Legacy Co", created_by=user.id,
            status="active", lifecycle_status="active",
        )
        db.session.add(material)
        db.session.flush()
        db.session.add(MaterialRequisition.from_dict({
            "mr_no": "MR-0042",
            "material_id": material.id,
            "item_code": "LEG-1",
            "material_description": "Legacy pipe",
            "quantity": 1,
            "discipline": "Piping",
            "project_no": "PRJ-L",
        }, "Legacy Co", user_id=user.id))
        db.session.commit()
        assert generate_next_mr_no("Legacy Co") == "MR-0043"


# ---------------------------------------------------------------------------
# API-level cross-tenant isolation
# ---------------------------------------------------------------------------

def test_mr_api_hides_foreign_tenant_records(client, app):
    """Tenant B must receive 404 for Tenant A's MR number."""
    owner = _persist_user(app, "mr-owner@example.com", AccessLevel.engineering, "Owner Co")
    stranger = _persist_user(app, "mr-stranger@example.com", AccessLevel.engineering, "Stranger Co")

    created = _create_mr(client, owner, "ISO-PIPE")
    assert created.status_code == 201
    mr_no = created.get_json()["mr_nos"][0]

    _authenticate_session(client, stranger)
    assert client.get(f"/material_requisitions/api/material_requisitions/{mr_no}").status_code == 404
    assert client.put(
        f"/material_requisitions/api/material_requisitions/{mr_no}",
        json={"quantity": 99},
    ).status_code == 404
    assert client.delete(
        f"/material_requisitions/api/material_requisitions/{mr_no}"
    ).status_code == 404

    # Listing must only return the stranger's own (empty) set.
    listing = client.get("/material_requisitions/api/material_requisitions")
    assert listing.status_code == 200
    assert listing.get_json() == []


def test_warehouse_inventory_is_tenant_scoped(client, app):
    """Inventory rows created for one company are invisible to another."""
    from datetime import date

    warehouse_user = _persist_user(
        app, "wh-owner@example.com", AccessLevel.warehouse, "WH Owner"
    )
    other = _persist_user(
        app, "wh-other@example.com", AccessLevel.warehouse, "WH Other"
    )

    with app.app_context():
        material = MaterialMaster(
            material_code="WH-ISO", family_code="PIP", material_name="ISO Pipe",
            description="ISO Pipe", unit="EA", discipline="Piping",
            fingerprint=("test:WH Owner:WH-ISO").encode().hex().ljust(64, "0")[:64],
            company_name="WH Owner", created_by=warehouse_user.id,
            status="active", lifecycle_status="active",
        )
        db.session.add(material)
        db.session.flush()
        inv = WarehouseInventory(
            warehouse_id="WH-ISO-0001",
            delivery_id="DLV-ISO",
            material_id=material.id,
            item_code="WH-ISO",
            material_description="ISO Pipe",
            received_qty=50,
            available_qty=50,
            unit="EA",
            receipt_date=date.today(),
            project_no="PRJ-ISO",
            company_name="WH Owner",
            user_id=warehouse_user.id,
        )
        db.session.add(inv)
        db.session.commit()

    _authenticate_session(client, warehouse_user)
    own = client.get("/warehouse/api/inventory")
    assert own.status_code == 200
    payload = own.get_json()
    assert any(row.get("item_code") == "WH-ISO" for row in payload)

    _authenticate_session(client, other)
    foreign = client.get("/warehouse/api/inventory")
    assert foreign.status_code == 200
    assert foreign.get_json() == []


# ---------------------------------------------------------------------------
# Central helper behaviour
# ---------------------------------------------------------------------------

def test_company_filter_and_tenant_query(app):
    """Helpers must restrict results to the active tenant."""
    from flask_login import login_user

    with app.app_context():
        a = User(
            company_name="Helper A",
            company_email="helper-a@example.com",
            company_phone="+989131111111",
            full_name="Helper A",
            company_address="A",
            country="IR",
            access_level=AccessLevel.engineering,
            totp_confirmed=True,
        )
        b = User(
            company_name="Helper B",
            company_email="helper-b@example.com",
            company_phone="+989132222222",
            full_name="Helper B",
            company_address="B",
            country="IR",
            access_level=AccessLevel.engineering,
            totp_confirmed=True,
        )
        db.session.add_all([a, b])
        db.session.commit()

        mat_a = MaterialMaster(
            material_code="HA-1", family_code="PIP", material_name="A",
            description="A", unit="EA", discipline="Piping",
            fingerprint=("test:Helper A:HA-1").encode().hex().ljust(64, "0")[:64],
            company_name="Helper A", created_by=a.id,
            status="active", lifecycle_status="active",
        )
        mat_b = MaterialMaster(
            material_code="HB-1", family_code="PIP", material_name="B",
            description="B", unit="EA", discipline="Piping",
            fingerprint=("test:Helper B:HB-1").encode().hex().ljust(64, "0")[:64],
            company_name="Helper B", created_by=b.id,
            status="active", lifecycle_status="active",
        )
        db.session.add_all([mat_a, mat_b])
        db.session.commit()

        # Simulate request context for current_user
        with app.test_request_context():
            login_user(a)
            rows = tenant_query(MaterialMaster).all()
            assert len(rows) == 1
            assert rows[0].company_name == "Helper A"

            filtered = company_filter(MaterialMaster.query, MaterialMaster).all()
            assert len(filtered) == 1
            assert filtered[0].material_code == "HA-1"

            # require_same_tenant accepts own record
            assert require_same_tenant(mat_a) is mat_a

            # Foreign record must abort with 404
            with pytest.raises(Exception) as exc_info:
                require_same_tenant(mat_b)
            # Flask abort raises werkzeug.exceptions.NotFound
            assert getattr(exc_info.value, "code", None) == 404


def test_admin_can_bypass_tenant_filter_when_allowed(app):
    """allow_admin=True must open the query for administrators only."""
    from flask_login import login_user

    with app.app_context():
        admin = User(
            company_name="Admin Co",
            company_email="admin-tenant@example.com",
            company_phone="+989133333333",
            full_name="Admin",
            company_address="HQ",
            country="IR",
            access_level=AccessLevel.project_manager,
            is_admin=True,
            totp_confirmed=True,
        )
        other = User(
            company_name="Other Admin Co",
            company_email="other-admin@example.com",
            company_phone="+989134444444",
            full_name="Other",
            company_address="Branch",
            country="IR",
            access_level=AccessLevel.engineering,
            totp_confirmed=True,
        )
        db.session.add_all([admin, other])
        db.session.commit()

        for company, code, uid in (
            ("Admin Co", "ADM-1", admin.id),
            ("Other Admin Co", "OAC-1", other.id),
        ):
            db.session.add(MaterialMaster(
                material_code=code, family_code="PIP", material_name=code,
                description=code, unit="EA", discipline="Piping",
                fingerprint=(f"test:{company}:{code}").encode().hex().ljust(64, "0")[:64],
                company_name=company, created_by=uid,
                status="active", lifecycle_status="active",
            ))
        db.session.commit()

        with app.test_request_context():
            login_user(admin)
            # Default behaviour still scopes to admin's own company
            scoped = tenant_query(MaterialMaster).all()
            assert all(r.company_name == "Admin Co" for r in scoped)

            # Explicit allow_admin opens the full set
            all_rows = tenant_query(MaterialMaster, allow_admin=True).all()
            assert {r.company_name for r in all_rows} >= {"Admin Co", "Other Admin Co"}
