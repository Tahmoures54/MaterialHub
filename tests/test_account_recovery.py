"""Security regression tests for TOTP recovery."""
import hashlib
import logging
from datetime import datetime, timedelta

import pyotp
import pytz

from extensions import db
from models import AccessLevel, AccountRecoveryToken, User


def _user():
    user = User(
        company_name="Recovery Test Co",
        company_email="recovery@example.com",
        company_phone="+15551234567",
        full_name="Recovery Tester",
        company_address="123 Test Street",
        country="US",
        access_level=AccessLevel.project_manager,
        totp_secret=User.encrypt_totp_secret(pyotp.random_base32()),
        totp_confirmed=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_recovery_request_response_does_not_disclose_account(client, app, monkeypatch):
    with app.app_context():
        _user()

    sent = []
    monkeypatch.setattr("blueprints.auth.send_totp_recovery_email", lambda email, token: sent.append((email, token)))
    existing = client.post("/auth/reset_password_request", data={"email": "recovery@example.com"}, follow_redirects=True)
    missing = client.post("/auth/reset_password_request", data={"email": "missing@example.com"}, follow_redirects=True)

    message = b"If the address matches an account and recovery email is configured"
    assert message in existing.data
    assert message in missing.data
    assert len(sent) == 1
    assert sent[0][0] == "recovery@example.com"
    assert len(sent[0][1]) >= 40


def test_recovery_email_failure_does_not_claim_success(client, app, monkeypatch):
    with app.app_context():
        _user()

    def fail_delivery(_email, _token):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr("blueprints.auth.send_totp_recovery_email", fail_delivery)
    response = client.post("/auth/reset_password_request", data={"email": "recovery@example.com"}, follow_redirects=True)
    assert b"If the address matches an account and recovery email is configured" in response.data
    with app.app_context():
        token = AccountRecoveryToken.query.first()
        assert token is not None
        assert token.used_at is not None


def test_recovery_token_never_appears_in_request_logs(client, app):
    class CaptureHandler(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    handler = CaptureHandler()
    app.logger.addHandler(handler)
    secret_path_token = "sensitive-recovery-token-value"
    try:
        response = client.get(f"/auth/reset_totp?token={secret_path_token}")
    finally:
        app.logger.removeHandler(handler)

    paths = [getattr(record, "path", "") for record in handler.records]
    assert "/auth/reset_totp" in paths
    assert all(secret_path_token not in path for path in paths)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_recovery_request_is_rate_limited(client):
    client.environ_base["REMOTE_ADDR"] = "198.51.100.15"
    responses = [
        client.post("/auth/reset_password_request", data={"email": "unknown@example.com"})
        for _ in range(4)
    ]
    assert [response.status_code for response in responses[:3]] == [302, 302, 302]
    assert responses[3].status_code == 429


def test_invalid_and_expired_recovery_tokens_are_rejected(client, app):
    invalid = client.get("/auth/reset_totp?token=not-a-valid-token", follow_redirects=True)
    assert b"invalid or expired" in invalid.data.lower()

    with app.app_context():
        user = _user()
        expired = AccountRecoveryToken(
            user_id=user.id,
            token_hash=hashlib.sha256(b"expired-token").hexdigest(),
            expires_at=(datetime.now(pytz.UTC) - timedelta(minutes=1)).replace(tzinfo=None),
        )
        db.session.add(expired)
        db.session.commit()

    response = client.get("/auth/reset_totp?token=expired-token", follow_redirects=True)
    assert b"invalid or expired" in response.data.lower()


def test_valid_recovery_rotates_totp_once_and_rejects_reuse(client, app):
    with app.app_context():
        user = _user()
        old_secret = user.decrypt_totp_secret()
        raw_token = "single-use-recovery-token"
        recovery = AccountRecoveryToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=(datetime.now(pytz.UTC) + timedelta(minutes=30)).replace(tzinfo=None),
        )
        db.session.add(recovery)
        db.session.commit()
        user_id = user.id

    setup = client.get(f"/auth/reset_totp?token={raw_token}")
    assert setup.status_code == 200
    invalid_code = client.post("/auth/reset_totp", data={"token": raw_token, "totp_code": "abcdef"})
    assert invalid_code.status_code == 302
    with app.app_context():
        still_unused = AccountRecoveryToken.query.filter_by(user_id=user_id).first()
        assert still_unused.used_at is None
    with app.app_context():
        recovery = AccountRecoveryToken.query.filter_by(user_id=user_id).first()
        new_secret = User._totp_cipher().decrypt(recovery.pending_totp_secret[4:].encode()).decode()
    code = pyotp.TOTP(new_secret).now()

    response = client.post("/auth/reset_totp", data={"token": raw_token, "totp_code": code}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = db.session.get(User, user_id)
        recovery = AccountRecoveryToken.query.filter_by(user_id=user_id).first()
        assert user.totp_confirmed is True
        assert user.decrypt_totp_secret() == new_secret
        assert user.decrypt_totp_secret() != old_secret
        assert recovery.used_at is not None
        assert recovery.pending_totp_secret is None

    reuse = client.get(f"/auth/reset_totp?token={raw_token}", follow_redirects=True)
    assert b"invalid or expired" in reuse.data.lower()
