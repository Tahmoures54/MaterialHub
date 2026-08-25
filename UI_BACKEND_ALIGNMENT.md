# MaterialHub UI / Backend Alignment Update

This release updates the main HTML shell and landing page so the interface reflects the application's real operational modules.

## Main changes

- Rebuilt `templates/base.html` as a responsive MaterialHub application shell with role-aware navigation.
- Rebuilt `templates/dashboard/home.html` around the actual backend lifecycle: Requisition → Procurement → Supplier → Delivery → Warehouse → Quality.
- Added direct navigation to Material Intelligence, Traceability and Excel Import.
- Registered the canonical `role_workspace` blueprint so authentication redirects and workspace KPI APIs resolve correctly.
- Corrected role detection to use `User.access_level` and administrator status.
- Corrected role KPI queries to use the project's real SQLAlchemy model/table names and company scope.
- Corrected several template/backend endpoint mismatches.
- Corrected template paths for Material Requisitions, Warehouse Operations and Warehouse Report.
- Added a functional administrator route and aligned the administrator page with the current data model.
- Added mobile navigation behavior and a consistent application visual system.

## Run

1. Create/activate a virtual environment.
2. Install `requirements.txt`.
3. Copy `.env.example` to `.env` and set a production `SECRET_KEY` and database settings.
4. Run `python app.py` for local development.

The release package intentionally does not include the local `.env` file so deployment secrets are not shipped with the application.
