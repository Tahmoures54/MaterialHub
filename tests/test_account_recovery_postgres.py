"""PostgreSQL-only concurrency regression for single-use TOTP recovery links."""
import hashlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pyotp
import pytest
import pytz

from app import create_app
from extensions import db
from models import AccessLevel, AccountRecoveryToken, User


def test_concurrent_recovery_token_replay_succeeds_exactly_once():
    """Two independent PostgreSQL requests cannot redeem the same token."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        pytest.skip("Requires the PostgreSQL integration database")

    app = create_app("testing")
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=database_url,
    )
    unique = uuid.uuid4().hex
    email = f"recovery-race-{unique}@example.com"
    raw_token = f"single-use-{unique}"
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    user_id = None

    try:
        with app.app_context():
            user = User(
                company_name="Recovery Concurrency Test",
                company_email=email,
                company_phone=None,
                full_name="Concurrency Tester",
                company_address="CI Test Address",
                country="US",
                access_level=AccessLevel.project_manager,
                totp_secret=User.encrypt_totp_secret(pyotp.random_base32()),
                totp_confirmed=True,
            )
            db.session.add(user)
            db.session.flush()
            user_id = user.id
            db.session.add(
                AccountRecoveryToken(
                    user_id=user.id,
                    token_hash=token_hash,
                    expires_at=(datetime.now(pytz.UTC) + timedelta(minutes=30)).replace(tzinfo=None),
                )
            )
            db.session.commit()

        # Initialize the pending authenticator secret before racing the POSTs.
        with app.test_client() as setup_client:
            setup = setup_client.get(f"/auth/reset_totp?token={raw_token}")
            assert setup.status_code == 200

        with app.app_context():
            recovery = AccountRecoveryToken.query.filter_by(token_hash=token_hash).one()
            encrypted = recovery.pending_totp_secret
            assert encrypted and encrypted.startswith("enc:")
            new_secret = User._totp_cipher().decrypt(
                encrypted[4:].encode("ascii")
            ).decode("utf-8")
        code = pyotp.TOTP(new_secret).now()

        start = Barrier(2)

        def redeem(remote_addr):
            with app.test_client() as client:
                client.environ_base["REMOTE_ADDR"] = remote_addr
                start.wait(timeout=10)
                response = client.post(
                    "/auth/reset_totp",
                    data={"token": raw_token, "totp_code": code},
                    follow_redirects=True,
                )
                return response.status_code, response.get_data(as_text=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(redeem, "198.51.100.41"),
                pool.submit(redeem, "198.51.100.42"),
            ]
            responses = [future.result(timeout=30) for future in futures]

        successes = sum(
            status == 200 and "Your authenticator has been reset" in body
            for status, body in responses
        )
        assert successes == 1, [
            (status, "success" if "Your authenticator has been reset" in body else "not-success")
            for status, body in responses
        ]

        with app.app_context():
            recovery = AccountRecoveryToken.query.filter_by(token_hash=token_hash).one()
            user = db.session.get(User, user_id)
            assert recovery.used_at is not None
            assert recovery.pending_totp_secret is None
            assert user.auth_version == 1
            assert user.decrypt_totp_secret() == new_secret
    finally:
        if user_id is not None:
            with app.app_context():
                user = db.session.get(User, user_id)
                if user is not None:
                    db.session.delete(user)
                    db.session.commit()
                db.session.remove()
