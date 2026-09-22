"""Run database migrations during a Vercel production deployment.

Vercel serverless instances are intentionally not responsible for changing the
database schema at request time. The production deployment build is the single
migration point, so the live function only starts after Alembic is up to date.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) Make sure the project root is importable, regardless of how Vercel
#    invokes this script (sys.path[0] is normally the scripts/ directory).
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # .../scripts
PROJECT_ROOT = SCRIPT_DIR.parent                      # repository root

# Some projects keep the Flask entry under src/, backend/, server/, or api/.
CANDIDATE_ROOTS = [
    PROJECT_ROOT,
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "server",
    PROJECT_ROOT / "api",
]


def _find_app_root() -> Path:
    """Return the directory from which `import app` should succeed.

    Supports both layouts:
      - package:  <root>/app/__init__.py
      - module:   <root>/app.py
    """
    for candidate in CANDIDATE_ROOTS:
        if (candidate / "app" / "__init__.py").is_file():
            return candidate
        if (candidate / "app.py").is_file():
            return candidate
    return PROJECT_ROOT


APP_ROOT = _find_app_root()

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Relative paths (Alembic, migrations/, .env) must resolve from the repo root.
os.chdir(PROJECT_ROOT)

# ---------------------------------------------------------------------------
# 2) Debug output – useful when a Vercel build fails.
# ---------------------------------------------------------------------------
print(f"[vercel_migrate] script dir  : {SCRIPT_DIR}")
print(f"[vercel_migrate] project root: {PROJECT_ROOT}")
print(f"[vercel_migrate] app root    : {APP_ROOT}")
print(f"[vercel_migrate] app package : {(APP_ROOT / 'app' / '__init__.py').is_file()}")
print(f"[vercel_migrate] app module  : {(APP_ROOT / 'app.py').is_file()}")
print(f"[vercel_migrate] sys.path[0] : {sys.path[0]}")

# ---------------------------------------------------------------------------
# 3) Third-party imports (after sys.path is fixed).
# ---------------------------------------------------------------------------
try:
    from flask_migrate import upgrade

from flask import current_app
from flask_migrate import stamp
from sqlalchemy import inspect, text
import re

BASELINE_REVISION = "20260901_0000"
BASELINE_MIGRATION = (
    PROJECT_ROOT
    / "migrations"
    / "versions"
    / "20260901_0000_baseline_initial_materialhub_schema.py"
)


def _baseline_tables() -> set[str]:
    """Read the baseline migration and return every table it creates."""
    if not BASELINE_MIGRATION.is_file():
        raise RuntimeError(f"Baseline migration not found: {BASELINE_MIGRATION}")

    content = BASELINE_MIGRATION.read_text(encoding="utf-8")
    tables = set(re.findall(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]", content))
    if not tables:
        raise RuntimeError(
            f"Could not determine baseline tables from {BASELINE_MIGRATION}"
        )
    return tables


def _reconcile_existing_baseline() -> bool:
    """Stamp an already-provisioned baseline database instead of recreating it.

    Some existing production databases were created before the baseline Alembic
    revision was introduced. In that case the schema exists but alembic_version
    is empty/missing. We only stamp when *every* table declared by the baseline
    migration already exists, preventing a partial database from being marked
    as migrated.
    """
    engine = current_app.extensions["sqlalchemy"].engine
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    baseline_tables = _baseline_tables()

    version_rows = []
    if "alembic_version" in existing_tables:
        with engine.connect() as conn:
            version_rows = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()

    if version_rows:
        return False

    missing = sorted(baseline_tables - existing_tables)
    if missing:
        # No version is recorded and the schema is incomplete. Let Alembic
        # fail normally rather than silently stamping an unsafe database.
        print(
            "[vercel_migrate] Alembic history is empty and the existing schema "
            "is incomplete; missing baseline tables: "
            + ", ".join(missing)
        )
        return False

    print(
        "[vercel_migrate] Existing production schema already contains the "
        f"complete baseline ({len(baseline_tables)} tables); stamping "
        f"{BASELINE_REVISION} instead of recreating it."
    )
    stamp(BASELINE_REVISION)
    return True
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "flask_migrate is not installed. Add `Flask-Migrate` to "
        "requirements.txt and redeploy."
    ) from exc


def _resolve_database_url() -> str:
    """Return the first PostgreSQL URL provided by Vercel / the environment."""
    for key in (
        "DATABASE_URL",
        "material_DATABASE_URL",
        "POSTGRES_URL",
        "material_POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
        "material_POSTGRES_URL_NON_POOLING",
    ):
        value = os.getenv(key)
        if value:
            print(f"[vercel_migrate] using database URL from ${key}")
            return value
    raise RuntimeError(
        "Production Vercel build is missing a PostgreSQL database URL. "
        "Set DATABASE_URL (or a supported PostgreSQL URL) in Vercel "
        "Production Environment Variables before deploying."
    )


def main() -> None:
    # Only run migrations on production builds.
    if os.getenv("VERCEL_ENV") != "production":
        print("[vercel_migrate] VERCEL_ENV is not 'production'; skipping migrations.")
        return

    # Fail fast if the database URL is missing.
    _resolve_database_url()

    # Force production configuration even if Vercel tweaks the default env.
    os.environ["FLASK_ENV"] = "production"
    os.environ.setdefault("FLASK_DEBUG", "0")

    # Import the app factory *after* sys.path is prepared.
    try:
        from app import create_app  # type: ignore
    except ModuleNotFoundError as exc:
        listing = "\n  ".join(sorted(p.name for p in APP_ROOT.iterdir()))
        raise SystemExit(
            f"Could not import `app.create_app` from {APP_ROOT}.\n"
            f"Contents of {APP_ROOT}:\n  {listing}\n"
            f"Expected either app/__init__.py (package) or app.py (module) "
            f"that exports create_app, and that the file is not excluded "
            f"by .vercelignore."
        ) from exc

    app = create_app("production")

    with app.app_context():
        if not _reconcile_existing_baseline():
            print("[vercel_migrate] running Alembic upgrade()...")
            upgrade()
        print("[vercel_migrate] database migrations completed successfully.")


if __name__ == "__main__":
    main()
