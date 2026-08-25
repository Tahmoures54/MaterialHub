# MaterialHub vNext — Material Operations Intelligence

MaterialHub vNext extends the core procurement and warehouse workflow into a traceable EPC material operating system.

## Delivered capabilities

1. **QR Material Traceability** — unique trace codes with QR endpoint and complete PO/delivery/warehouse/project identity.
2. **Heat / Lot / Serial / Batch Tracking** — trace records support all four identifiers.
3. **MTC / CoC / Datasheet Control** — controlled document model linked to a material trace, with approval/revision/expiry fields.
4. **Material Readiness Index** — dynamic readiness score based on stock, open PO coverage and required date.
5. **Supplier Performance Score** — quality + OTIF + commercial/responsiveness/lead-time dimensions with monthly scorecards.
6. **Automatic RFQ** — generate an RFQ from an MR and invite qualified suppliers.
7. **Quote Comparison** — normalized supplier quote endpoint for price, lead time, quality and total score.
8. **PO ↔ Receipt ↔ Invoice 3-Way Match** — automatic variance and exception detection.
9. **Offline Mobile Warehouse Shell** — installable PWA shell with service-worker fallback for warehouse pages/assets.
10. **Excel/CSV Import Wizard** — schema validation and preview before data commit.
11. **Material Price History** — historical supplier price observations by item code.
12. **Lead-Time Intelligence** — observed average/best/worst supplier lead times.
13. **Supplier OTIF Score** — on-time-in-full signal derived from procurement history.
14. **Schedule-aware Procurement Risk** — required-date vs stock/open-PO coverage is surfaced as readiness risk.
15. **AI Material Copilot** — explainable rules-based decision support that produces a reason and recommended action.

## AI principle

The Copilot is deliberately **decision support, not a chatbot**. Every insight contains:

- material/item identity
- current stock
- open PO coverage
- days to required date
- readiness score
- explicit reason
- recommended action

Example:

> 12-inch CS Pipe has 9 days until required date and only 120 in stock with 600 on open PO.
>
> **Recommended Action:** Expedite the open PO; if the supplier cannot recover the lead time, activate a qualified alternate supplier.

## Key endpoints

- `/material-intelligence`
- `/api/material-intelligence`
- `/traceability`
- `/api/trace/<trace_code>`
- `/api/qr/<trace_code>`
- `POST /rfq/auto/<mr_id>`
- `/rfq/compare/<rfq_id>`
- `POST /three-way-match/<po_id>`
- `/excel-import`
- `/price-history/<item_code>`
- `/lead-time/<item_code>`
- `POST /supplier-score/<supplier_id>`

## Production note

This release intentionally keeps the intelligence layer additive. For an existing production database, use Flask-Migrate to create and apply migrations rather than relying on `db.create_all()`.
