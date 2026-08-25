# MaterialHub

## Construction & EPC Material Management Platform

MaterialHub is designed to control the material lifecycle from project demand through procurement, delivery, quality inspection, warehouse receipt and field availability.

### Core lifecycle

**Material Need → Material Requisition → Approval → Tender → Supplier Bid → Purchase Order → Delivery → Quality Control → Warehouse Receipt → Stock Availability**

### Strategic product advantages

1. **Material-first architecture** instead of generic project management.
2. **Executive risk visibility** for delayed deliveries and low stock.
3. **Field-to-office workflow** through APIs and mobile-friendly pages.
4. **Supplier marketplace + tendering** connected to actual project demand.
5. **Audit-ready traceability** through persistent business records and timestamps.
6. **Deployment flexibility**: SQLite for local development, PostgreSQL for production.
7. **Security baseline**: CSRF protection, TOTP authentication, secure cookies and security headers.

### Competitive benchmark

- **Procore:** strong material supply-chain, field receiving, inventory and financial integration. MaterialHub focuses more deeply on the material lifecycle and supplier/tender workflow.
- **Autodesk Forma / Construction Cloud:** strong document, project and integration ecosystem. MaterialHub differentiates with a simpler material-centric operating model.
- **Oracle Fusion Cloud Procurement:** excellent enterprise sourcing and procure-to-pay capabilities. MaterialHub is lighter and more construction/EPC operationally focused.

### Production checklist

- Use PostgreSQL.
- Set `FLASK_ENV=production`.
- Set `SESSION_COOKIE_SECURE=true` behind HTTPS.
- Replace the generated local `SECRET_KEY` with a deployment-specific secret manager value.
- Run behind Gunicorn or an equivalent WSGI server.
- Configure backups and log aggregation.
