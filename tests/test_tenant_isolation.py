"""Regression tests for tenant-scoped document numbering.

These cover the multi-tenant defects where document numbers (and shared
project numbers) were globally unique, so the second tenant's first MR/PO/
DLV/WH — or a project number reused by two companies — failed with a
unique-constraint error.
"""
import pytest

from extensions import db
from models import (
    User, AccessLevel, Project, MaterialRequisition,
)
from utils import generate_next_mr_no
from tests.test_app_integration import _persist_user


def _create_mr(client, user, item, project_no="PRJ-SHARED"):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)
        session["_fresh"] = True
    return client.post("/material_requisitions/api/material_requisitions", json={
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
        db.session.add(MaterialRequisition.from_dict({
            "mr_no": "MR-0042",
            "item_code": "LEG-1",
            "material_description": "Legacy pipe",
            "quantity": 1,
            "discipline": "Piping",
            "project_no": "PRJ-L",
        }, "Legacy Co", user_id=user.id))
        db.session.commit()
        assert generate_next_mr_no("Legacy Co") == "MR-0043"
