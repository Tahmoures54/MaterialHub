# Role-Aware Enterprise Workspaces

## Login behavior
After authentication, users can open `/workspace/` and are automatically routed from their role to:
- Administrator → `/workspace/admin`
- Project Manager → `/workspace/project_manager`
- Engineering → `/workspace/engineering`
- Procurement → `/workspace/procurement`
- Warehouse → `/workspace/warehouse`
- Quality → `/workspace/quality`
- Supplier → `/workspace/supplier`

Role aliases are normalized so common role names such as `QA`, `QC`, `Buyer`, `Storekeeper`, `Vendor`, and `Owner` resolve correctly.

## Live KPIs
The workspace renders server-side KPI values and refreshes them through:
`GET /workspace/api/kpis`

The service queries existing tables defensively. Missing tables return zero rather than breaking the workspace. This makes the UX layer compatible with the current database while remaining ready for richer domain metrics.

## Security
A user cannot switch into another role workspace unless the current normalized role is `admin`. This is a UX layer and should be paired with the project's existing authorization decorators for every sensitive action.

## Next production hardening
Map each KPI to domain-specific queries (open, overdue, at-risk, pending approval) rather than raw table counts and add caching for executive dashboards.
