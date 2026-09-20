# Production Deployment Guide

## Architecture
Internet traffic terminates at Nginx. Nginx forwards traffic to Gunicorn/Flask over the private Docker network. PostgreSQL and Redis are internal services.

## Required configuration
Copy .env.prod.example to a real .env.prod file and fill in production values.
Create these Docker secret files outside Git:
- secrets/postgres_password
- secrets/tls_cert
- secrets/tls_key

## Start
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

Then inspect:
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=200 web
docker compose -f docker-compose.prod.yml logs --tail=200 nginx

## Migration
Review the current Alembic history before the first production upgrade. If the existing database was created outside Alembic, establish the correct baseline first. After the baseline is confirmed:
docker compose -f docker-compose.prod.yml exec web flask db upgrade

## Health checks
/health/live must return HTTP 200 when the process is alive.
/health/ready must return HTTP 200 only when required dependencies are ready and HTTP 503 when a required dependency is unavailable.

## Rollback
For an application-only rollback, stop deployment traffic, deploy the previous known-good image, confirm liveness/readiness, test login and a representative business workflow, then re-enable traffic.
Do not automatically downgrade database migrations. Use a reviewed migration or verified backup/restore procedure.

## Backups
Back up PostgreSQL on a schedule appropriate to business requirements. A backup is not operationally valid until a restore has been tested.

At minimum test schema restoration, representative business data, application startup, login/2FA, and MR/RFQ/PO/Delivery/QC/Warehouse workflow.

## Production acceptance
Production acceptance requires successful real-environment verification of TLS, PostgreSQL, Redis, migrations, authentication/2FA/RBAC, tenant isolation, Excel import/export, backup/restore, monitoring and graceful shutdown.