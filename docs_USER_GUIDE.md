# MaterialHub User Guide

## Purpose
MaterialHub is a construction and EPC material operations platform. It connects material demand, procurement, suppliers, logistics, quality, warehouse traceability and schedule-aware intelligence.

## Core lifecycle
`Need -> MR -> RFQ -> Quote -> PO -> Delivery -> QC -> Receipt -> Warehouse -> Issue -> Intelligence`

## Daily operating rhythm
- Engineering: update material requirements and required dates.
- Procurement: review open RFQs, supplier quotes, POs and late deliveries.
- Quality: review inspection and mandatory MTC/CoC/Datasheet evidence.
- Warehouse: record receipts, locations, trace identifiers and stock changes.
- Project Management: review readiness and schedule risk; assign actions.

## Material Intelligence
The intelligence layer should be treated as decision support. Readiness and risk indicators combine operational evidence such as available stock, open purchase orders, required dates, supplier behavior and lead-time information.

## AI Material Copilot
Copilot is intended to explain risk and recommend actions, not silently execute commercial or technical decisions. A good recommendation contains:
1. material and project context;
2. current stock and open commitments;
3. required date and estimated timing;
4. evidence for the risk;
5. a concrete recommended action;
6. the owner who should approve the action.

## Data quality rules
- Keep item codes consistent.
- Always maintain required dates.
- Do not create duplicate POs for the same commercial commitment.
- Record actual delivery dates promptly.
- Attach quality document references to the correct trace record.
- Use heat/lot/serial/batch identifiers when required by the material specification.

## Security
Keep `.env` out of source control. Use a unique production secret key and a managed PostgreSQL database for production deployments.
