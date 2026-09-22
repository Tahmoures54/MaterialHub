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
    from flask import current_app
    from flask_migrate import stamp, upgrade
    from sqlalchemy import inspect, text
    import re
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit(
        "Required migration dependencies are not installed. "
        "Check requirements.txt and redeploy."
    ) from exc


BASELINE_REVISION = "20260901_0000"
BASELINE_MIGRATION = (
    PROJECT_ROOT
    / "migrations"
    / "versions"
    / "20260901_0000_baseline_initial_materialhub_schema.py"
)


def _baseline_tables() -> set[str]:
    """Return every table declared by the baseline migration."""
    if not BASELINE_MIGRATION.is_file():
        raise RuntimeError(f"Baseline migration not found: {BASELINE_MIGRATION}")

    content = BASELINE_MIGRATION.read_text(encoding="utf-8")
    tables = set(
        re.findall(r"op\.create_table\(\s*['\"]([^'\"]+)['\"]", content)
    )
    if not tables:
        raise RuntimeError(f"Could not determine baseline tables from {BASELINE_MIGRATION}")
    return tables


def _reconcile_existing_baseline() -> bool:
    """Stamp a complete pre-Alembic baseline instead of recreating its tables.

    This is intentionally conservative: stamping is allowed only when no
    Alembic revision is recorded and every table declared by the baseline
    migration already exists. A partial schema is left to Alembic so missing
    objects are not silently hidden.
    """
    engine = current_app.extensions["sqlalchemy"].engine
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    version_rows = []
    if "alembic_version" in existing_tables:
        with engine.connect() as conn:
            version_rows = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalars().all()

    if version_rows:
        return False

    baseline_tables = _baseline_tables()
    missing = sorted(baseline_tables - existing_tables)

    if missing:
        print(
            "[vercel_migrate] Existing schema is incomplete; "
            "Alembic will run normally. Missing baseline tables: "
            + ", ".join(missing)
        )
        return False

    print(
        "[vercel_migrate] Existing schema contains the complete baseline "
        f"({len(baseline_tables)} tables); stamping {BASELINE_REVISION}."
    )
    stamp(BASELINE_REVISION)
    return True


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
