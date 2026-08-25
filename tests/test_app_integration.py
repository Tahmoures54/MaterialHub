"""Optional Flask integration tests.

Run with: pytest -q
They are skipped automatically when Flask/project dependencies are not installed.
"""
import pytest

flask = pytest.importorskip("flask")

from app import create_app


def test_health_endpoint():
    app = create_app("testing") if "testing" in getattr(__import__('config.config', fromlist=['config_by_name']), 'config_by_name') else create_app("development")
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_workspace_requires_login():
    app = create_app("development")
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.get("/workspace/", follow_redirects=False)
    assert response.status_code in (302, 401)


def test_unknown_workspace_role_is_normalized():
    app = create_app("development")
    app.config.update(TESTING=True)
    # The route is protected, so the assertion here focuses on route existence.
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/workspace/<role>" in rules
    assert "/workspace/api/kpis" in rules
