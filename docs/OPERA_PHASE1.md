# OPERA Phase 1

Additive commissioning foundation for the existing MaterialHub Flask app.

- OPERA `tenant_id` is an alias of existing `User.company_name`; no Tenant table.
- Existing `Project`, `User`, login, sessions and TOTP remain authoritative.
- Composite project foreign keys enforce tenant consistency.
- Signed-off CheckSheets and their items reject ORM update/delete operations.
- Revisions preserve the same sheet number and increment the revision value.
- Audit events are stored separately in `CommissioningAuditEvent` with before/after JSON.
- Attachments store metadata and a storage key, not file bytes.
- Numbering reuses MaterialHub `document_sequence`; atomic initialization and increment support PostgreSQL and SQLite.

## Apply and seed

```bash
flask --app wsgi db upgrade
SEED_COMMISSIONING_DEMO=1 FLASK_APP=wsgi.py python scripts/seed_commissioning_demo.py
```

The opt-in seed creates one project, two systems, three subsystems, ten tags,
five A-sheets, five B-sheets, three C-sheets, eight Punch items, one issued MC
and one pending RFC.

## Tests

```bash
pytest -q tests/test_commissioning_models.py
pytest -q
```
