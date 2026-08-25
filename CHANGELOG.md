# MaterialHub — Enhancement Notes

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
