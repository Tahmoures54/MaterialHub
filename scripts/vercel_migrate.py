"""Run database migrations during a Vercel production deployment.

Vercel serverless instances are intentionally not responsible for changing the
database schema at request time. The production deployment build is the single
migration point, so the live function only starts after Alembic is up to date.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1) Make sure the project root (the directory that contains the `app` package)
#    is importable, regardless of how Vercel invokes this script.
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # .../scripts
PROJECT_ROOT = SCRIPT_DIR.parent                      # repository root

# Some projects keep the Flask package under `src/`, `backend/`, or `server/`.
# We try each candidate and pick the first one that actually contains `app/`.
CANDIDATE_ROOTS = [
    PROJECT_ROOT,
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "backend",
    PROJECT_ROOT / "server",
    PROJECT_ROOT / "api",
]

def _find_app_root() -> Path:
    """Return the directory that contains the `app` package."""
    for candidate in CANDIDATE_ROOTS:
        if (candidate / "app" / "__init__.py").is_file():
            return candidate
    # Fall back to project root so the error message is still meaningful.
    return PROJECT_ROOT


APP_ROOT = _find_app_root()

# Insert the discovered root at the front of sys.path so `import app` resolves.
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

# Change working directory to the project root so relative paths (e.g. Alembic
# config, .env, migrations/) keep working.
os.chdir(PROJECT_ROOT)

# ---------------------------------------------------------------------------
# 2) Debug output – extremely useful when a Vercel build fails.
# ---------------------------------------------------------------------------
print(f"[vercel_migrate] script dir  : {SCRIPT_DIR}")
print(f"[vercel_migrate] project root: {PROJECT_ROOT}")
print(f"[vercel_migrate] app root    : {APP_ROOT}")
print(f"[vercel_migrate] app package : {(APP_ROOT / 'app').is_dir()}")
print(f"[vercel_migrate] sys.path[0] : {sys.path[0]}")

# ---------------------------------------------------------------------------
# 3) Third-party imports (after sys.path is fixed).
# ---------------------------------------------------------------------------
try:
    from flask_migrate import upgrade
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
            f"Make sure `app/__init__.py` exists and exports `create_app`, "
            f"and that the folder is not excluded by .vercelignore."
        ) from exc

    app = create_app("production")

    with app.app_context():
        print("[vercel_migrate] running Alembic upgrade()...")
        upgrade()
        print("[vercel_migrate] database migrations completed successfully.")


if __name__ == "__main__":
    main()
