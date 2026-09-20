"""Shared pytest fixtures for Flask integration tests."""
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-materialhub-0123456789abcdef")

import pytest

from app import create_app
from extensions import db


@pytest.fixture
def app():
    application = create_app("testing")
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    # Do NOT keep an app context pushed across the test: client requests must
    # push their own context so that per-request state (flask.g, including
    # flask-login's cached user) cannot leak between requests.
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
