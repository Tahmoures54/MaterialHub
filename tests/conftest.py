"""Shared pytest fixtures for Flask integration tests."""
import pytest

from app import create_app
from extensions import db


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
