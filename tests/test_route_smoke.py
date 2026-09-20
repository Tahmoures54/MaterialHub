"""Authenticated route smoke coverage for production-facing Flask blueprints."""
import re

import pytest

from extensions import db
from models import AccessLevel, User


@pytest.fixture
def admin_user(app):
    with app.app_context():
        user = User(
            company_name="Smoke EPC",
            company_email="admin-smoke@example.com",
            company_phone="+989121234567",
            full_name="Smoke Admin",
            company_address="Test Address",
            country="IR",
            access_level=AccessLevel.project_manager,
            is_admin=True,
            totp_confirmed=True,
        )
        db.session.add(user)
        db.session.commit()
        return user.id


def authenticate(client, user):
    user_id = getattr(user, "id", user)
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def materialize_rule(rule):
    def replace(match):
        converter = match.group(1) or ""
        if converter.startswith("int"):
            return "1"
        if converter.startswith("path"):
            return "test"
        return "1"

    return re.sub(r"<(?:(\\w+):)?[^>]+>", replace, rule.rule)


def test_all_get_routes_are_smoke_tested(client, app, admin_user):
    """Exercise every registered GET endpoint and fail on unexpected server errors."""
    authenticate(client, admin_user)
    seen = set()
    failures = []

    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        path = materialize_rule(rule)
        if path in seen or path.startswith("/static/"):
            continue
        seen.add(path)
        response = client.get(path, follow_redirects=False)
        if response.status_code >= 500:
            failures.append(f"{rule.endpoint} {path}: {response.status_code}")

    assert not failures, "\\n".join(failures)
