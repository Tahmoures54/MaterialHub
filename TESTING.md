# MaterialHub Test Suite

MaterialHub now includes a dedicated `tests/` package.

## Test layers

### 1. Contract / static tests
`tests/test_role_workspace_unit.py`

Validates:
- Python syntax
- role workspace templates
- role aliases
- automatic role-aware login routing
- live KPI API usage
- shared Design System loading

These tests use only the Python standard library.

### 2. Flask integration tests
`tests/test_app_integration.py`

Validates:
- `/health`
- authentication protection for `/workspace/`
- registered workspace routes

They are automatically skipped if Flask is unavailable.

## Run

```bash
python -m pip install -r requirements-dev.txt
pytest -q
```

or:

```bash
python tests/run_tests.py
```

## Recommended CI command

```bash
pytest -q --disable-warnings --maxfail=1
```
