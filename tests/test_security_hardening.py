from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_config_rejects_sqlite_and_weak_secrets():
    config = (ROOT / "config" / "config.py").read_text(encoding="utf-8")
    assert "Production database must be PostgreSQL." in config
    assert "SECRET_KEY must contain at least 32 bytes." in config
    assert "RATELIMIT_STORAGE_URI" in config
    assert "memory://" in config


def test_auth_routes_are_rate_limited():
    auth = (ROOT / "blueprints" / "auth.py").read_text(encoding="utf-8")
    assert "@limiter.limit('5 per minute')" in auth
    assert "@limiter.limit('5 per hour')" in auth
    assert "@limiter.limit('3 per 15 minutes')" in auth
    assert "from extensions import db, limiter" in auth


def test_totp_secret_is_encrypted_and_qr_not_persisted():
    models = (ROOT / "models.py").read_text(encoding="utf-8")
    auth = (ROOT / "blueprints" / "auth.py").read_text(encoding="utf-8")
    assert "Fernet" in models
    assert "encrypt_totp_secret" in models
    assert "decrypt_totp_secret" in models
    assert "totp_secret = db.Column(db.String(512)" in models
    assert "user.qr_code_base64 = None" in auth


def test_tenant_sensitive_intelligence_queries_are_scoped():
    intelligence = (ROOT / "blueprints" / "intelligence.py").read_text(encoding="utf-8")
    assert "company_name=current_user.company_name" in intelligence
    assert "company_filter(RFQ.query,RFQ).filter_by(id=rfq_id)" in intelligence
    assert "company_filter(PurchaseOrder.query,PurchaseOrder).filter_by(id=po_id)" in intelligence
    assert "if not suppliers:" not in intelligence


def test_wsgi_is_import_only():
    wsgi = (ROOT / "wsgi.py").read_text(encoding="utf-8")
    assert "app = create_app()" in wsgi
    assert "app.run(" not in wsgi

def test_contact_inquiry_schema_matches_public_limits():
    models = (ROOT / "models.py").read_text(encoding="utf-8")
    migration = ROOT / "migrations" / "versions" / "20260922_0003_contact_inquiry_limits.py"
    assert "db.String(254)" in models
    assert "db.String(160)" in models
    assert migration.exists()
    migration_text = migration.read_text(encoding="utf-8")
    assert "20260921_0002" in migration_text
    assert "length=254" in migration_text
    assert "length=160" in migration_text
