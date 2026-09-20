# MaterialHub — Production Launch Guide

**Version target:** v1.1.0+  
**Last updated:** 2026-09-20

This document is the single checklist to take MaterialHub from “code ready” to “live with real users and real data”.

---

## 1. Architecture (final)

```
Internet
   │
   ▼
Nginx (TLS termination, ports 80/443)
   │  private Docker network
   ▼
Gunicorn × 3 workers  →  Flask (wsgi:app)
   │
   ├── PostgreSQL 16 (persistent volume)
   └── Redis 7 (rate-limit + session support)
```

---

## 2. Pre-flight checklist

### Secrets & environment
- [ ] Copy `.env.prod.example` → `.env.prod`
- [ ] Generate `SECRET_KEY` (≥ 32 bytes):
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- [ ] Create `secrets/` directory (never commit it):
  ```bash
  mkdir -p secrets
  openssl rand -base64 32 > secrets/postgres_password
  # place real TLS cert/key:
  # secrets/tls_cert   (fullchain.pem)
  # secrets/tls_key    (privkey.pem)
  ```
- [ ] Set `POSTGRES_DB` and `POSTGRES_USER` in `.env.prod`
- [ ] Confirm `FLASK_ENV=production`

### Domain & TLS
- [ ] DNS A/AAAA records point to the server
- [ ] Valid certificate (Let’s Encrypt or commercial)
- [ ] Nginx config in `nginx/nginx.conf` references the secrets

### Database
- [ ] Review Alembic history (`migrations/versions/`)
- [ ] If the DB already exists outside Alembic, stamp the correct baseline first
- [ ] Plan first backup immediately after migrate

---

## 3. Deploy commands

```bash
# Build
docker compose -f docker-compose.production.yml build

# Start
docker compose -f docker-compose.production.yml up -d

# Watch
docker compose -f docker-compose.production.yml ps
docker compose -f docker-compose.production.yml logs -f web

# Migrate (after services healthy)
docker compose -f docker-compose.production.yml exec web flask db upgrade

# Optional: load demo data (ONLY for staging / first demo environment)
docker compose -f docker-compose.production.yml exec -e SEED_DEMO=1 web \
  python scripts/seed_demo.py
```

---

## 4. Health & smoke tests

```bash
curl -fsS https://YOUR_DOMAIN/health/live
curl -fsS https://YOUR_DOMAIN/health/ready
# expect HTTP 200 both

# metrics (Prometheus scrape)
curl -fsS https://YOUR_DOMAIN/metrics | head
```

Manual smoke:
1. Open landing page → `/` or marketing routes
2. Register or login with demo accounts (if seeded)
3. Confirm 2FA flow
4. Walk one full path: MR → Tender/PO → Delivery → QC → Warehouse
5. Verify tenant isolation (two companies cannot see each other’s data)

---

## 5. Demo accounts (after `seed_demo.py`)

| Role             | Email                     | Password                 |
|------------------|---------------------------|--------------------------|
| Project Manager  | pm@pge.demo               | Demo@MaterialHub2026!    |
| Purchase         | purchase@pge.demo         | Demo@MaterialHub2026!    |
| Quality          | qc@pge.demo               | Demo@MaterialHub2026!    |
| Warehouse        | warehouse@pge.demo        | Demo@MaterialHub2026!    |
| Supplier         | sales@caspiansteel.demo   | Demo@MaterialHub2026!    |

**Change all passwords and rotate TOTP before giving access to real customers.**

---

## 6. User-acquisition readiness

Already present:
- `/demo`, `/pricing`, `/contact` (growth blueprint)
- Marketing templates under `templates/marketing/`
- ContactInquiry model + persistence

Recommended next steps (product):
1. Improve landing page copy & CTA (Request Demo)
2. Add email/Telegram notification when a ContactInquiry is created
3. Publish a 2-minute product video or Loom
4. SEO: title, description, Open Graph tags
5. Free-trial or “Start with demo data” onboarding path

---

## 7. Operational checklist (first week)

- [ ] Automated daily PostgreSQL backup + one successful restore test
- [ ] Alert on `/health/ready` returning non-200
- [ ] Alert on 5xx rate and authentication failures
- [ ] Log retention policy (JSON logs to stdout → collector)
- [ ] Document rollback: previous image + no automatic migration downgrade
- [ ] Rotate `SECRET_KEY` and Postgres password after any suspected leak

---

## 8. Go-live decision

You may declare production live when **all** of the following are true:

1. TLS valid and HSTS active  
2. PostgreSQL + Redis healthy  
3. Migrations applied and baseline confirmed  
4. Login + 2FA + RBAC tested with real roles  
5. At least one end-to-end business workflow completed  
6. Backup + restore verified  
7. Monitoring/alerting in place  
8. Demo or real seed data present for first users  

---

## Quick reference commands

```bash
# Restart only the app
docker compose -f docker-compose.production.yml restart web

# Shell into app
docker compose -f docker-compose.production.yml exec web bash

# View recent logs
docker compose -f docker-compose.production.yml logs --tail=200 web nginx

# Scale workers later (edit command in compose or use gunicorn config)
```

For detailed security policy see `SECURITY.md`.  
For the original hardening report see `PRODUCTION_READINESS_REPORT.md`.
