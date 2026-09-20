# MaterialHub — Enhancement Notes

## v1.1 — Product hardening

Operational fixes that make the existing MaterialHub modules actually usable end-to-end.

### Fixed
- Registration TOTP setup now renders `auth/register.html` instead of a missing template.
- Material requisition and warehouse APIs gained the missing `from_dict` / `update_from_dict` helpers.
- Document numbering (`MR` / `PO` / `DLV` / `WH`) is sequential and company-aware.
- Purchase order, delivery and QC create flows persist `company_name` and stay tenant-scoped.
- Duplicate blueprint URL prefixes no longer produce `/warehouse/warehouse/...` routes.
- JSON APIs can send `csrf_token` in the request body.
- Gunicorn now boots `wsgi:app` instead of an invalid factory string.

### Added
- Public acquisition funnel: landing, demo, pricing and persisted demo-request contact.
- Liveness and readiness probes at `/health/live` and `/health/ready`.
- Role workspaces now show operational KPIs (pending, overdue, delayed, low stock) instead of raw table counts.
- Dedicated 403 page and `/register`, `/login`, `/getting-started` aliases.
- `testing` Flask config and broader integration coverage.

## vNext — Global Procurement & Materials Control

This release strengthens MaterialHub as an end-to-end construction / EPC material control platform.

### Added
- Executive **Control Center** with live KPIs for requisitions, POs, deliveries, low stock and tenders.
- Delivery Risk Radar using the existing risk-analysis engine.
- Low-stock / reorder signals on the executive dashboard.
- Procurement pipeline view with project, priority and approval status.
- Fast-action navigation for requisitions, purchasing, warehouse, delivery, quality and suppliers.
- JSON API: `GET /api/overview` for dashboards and future mobile integrations.
- Health endpoint: `GET /health` for deployment monitoring.
- Security response headers and configurable session security.
- Production-oriented `.env.example` and a local `.env` with a generated secret.
- Responsive executive UI designed for desktop and tablet field-office use.

### Competitive direction
MaterialHub is positioned around a construction/EPC-specific material lifecycle: **Need → MR → Approval → Tender → PO → Delivery → QC → Warehouse → Availability**.

The product direction intentionally combines strengths seen in Procore Materials (supply-chain visibility, field receiving, inventory), Autodesk Forma/Construction Cloud (single source of truth and integrations), and Oracle Procurement (procure-to-pay, sourcing and supplier management), while keeping MaterialHub focused on material operations rather than becoming an overly broad enterprise suite.
