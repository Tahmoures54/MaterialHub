"""Run database migrations during a Vercel production deployment.

Vercel serverless instances are intentionally not responsible for changing the
database schema at request time. The production deployment build is the single
migration point, so the live function only starts after Alembic is up to date.
"""

import os
import sys
from pathlib import Path

# When this file is executed as `python scripts/vercel_migrate.py`, Python puts
# `scripts/` (not the repository root) on sys.path. Add the project root so
# the Flask application package can be imported reliably in Vercel builds.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)
print(f"MaterialHub migration script root: {PROJECT_ROOT}")

from flask_migrate import upgrade


def main() -> None:
    if os.getenv("VERCEL_ENV") != "production":
        print("Vercel environment is not production; skipping database migration.")
        return

    database_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("material_DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("material_POSTGRES_URL")
        or os.getenv("POSTGRES_PRISMA_URL")
    )
    if not database_url:
        raise RuntimeError(
            "Production Vercel build is missing a PostgreSQL database URL. "
            "Set DATABASE_URL (or a supported PostgreSQL URL) in Vercel "
            "Production Environment Variables before deploying."
        )

    # Force the production configuration even if Vercel changes the default
    # Flask environment used while building the project.
    os.environ["FLASK_ENV"] = "production"

    from app import create_app

    app = create_app("production")
    with app.app_context():
        print("Running MaterialHub production database migrations...")
        upgrade()
        print("MaterialHub production database migrations completed.")


if __name__ == "__main__":
    main()
