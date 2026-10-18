"""Security regression tests for TOTP recovery."""
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

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

    message = b"If the address matches an account and recovery email is available"
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
    assert b"If the address matches an account and recovery email is available" in response.data
    with app.app_context():
        token = AccountRecoveryToken.query.first()
        assert token is not None
        assert token.used_at is not None


def test_recovery_tokens_are_redacted_from_access_logs():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app.py").read_text(encoding="utf-8")
    nginx_source = (root / "nginx" / "nginx.conf").read_text(encoding="utf-8")
    production_docker = (root / "Dockerfile.production").read_text(encoding="utf-8")
    production_compose = (root / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "'path': route_template" in app_source
    assert "'path': request.path" not in app_source
    assert '"request":"$request"' not in nginx_source
    assert '"method":"$request_method"' in nginx_source
    assert '"--access-logfile","/dev/null"' in production_docker
    assert '"--access-logfile","/dev/null"' in production_compose

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
        old_code = pyotp.TOTP(old_secret).now()
        raw_token = "single-use-recovery-token"
        recovery = AccountRecoveryToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=(datetime.now(pytz.UTC) + timedelta(minutes=30)).replace(tzinfo=None),
        )
        db.session.add(recovery)
        db.session.commit()
        user_id = user.id

    stale_client = app.test_client()
    with stale_client.session_transaction() as stale_session:
        stale_session["_user_id"] = str(user_id)
        stale_session["_fresh"] = True
        stale_session["auth_version"] = 0

    setup = client.get(f"/auth/reset_totp?token={raw_token}")
    assert setup.status_code == 200
    assert setup.headers["Cache-Control"] == "no-store"
    assert setup.headers["Referrer-Policy"] == "no-referrer"
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

    stale_session_response = stale_client.get("/auth/change_password")
    assert stale_session_response.status_code == 302

    reuse = client.get(f"/auth/reset_totp?token={raw_token}", follow_redirects=True)
    assert b"invalid or expired" in reuse.data.lower()

    old_login = client.post("/auth/login", data={
        "email": "recovery@example.com",
        "totp_code": old_code,
        "submit": "Login",
    })
    assert old_login.status_code == 200
    assert b"Unable to sign in with those details" in old_login.data

    new_login = client.post("/auth/login", data={
        "email": "recovery@example.com",
        "totp_code": pyotp.TOTP(new_secret).now(),
        "submit": "Login",
    })
    assert new_login.status_code == 302

    reuse = client.get(f"/auth/reset_totp?token={raw_token}", follow_redirects=True)
    assert b"invalid or expired" in reuse.data.lower()



def test_login_rejects_valid_totp_until_enrollment_is_confirmed(client, app):
    """A valid code must not bypass the mandatory TOTP enrollment confirmation."""
    with app.app_context():
        user = _user()
        user.totp_confirmed = False
        db.session.commit()
        email = user.company_email
        code = pyotp.TOTP(user.decrypt_totp_secret()).now()

    response = client.post("/auth/login", data={
        "email": email,
        "totp_code": code,
        "submit": "Login",
    })

    assert response.status_code == 200
    assert b"Unable to sign in with those details" in response.data
    protected = client.get("/auth/change_password", follow_redirects=False)
    assert protected.status_code == 302
    assert "/auth/login" in protected.headers["Location"]
