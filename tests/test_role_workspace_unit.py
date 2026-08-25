"""Fast unit tests for MaterialHub's role-aware workspace contract.

These tests use the standard library so they can run even before application
runtime dependencies are installed. They validate the source contract and
workspace assets. Integration tests are provided separately.
"""
from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "admin": "admin.html",
    "project_manager": "project_manager.html",
    "engineering": "engineering.html",
    "procurement": "procurement.html",
    "warehouse": "warehouse.html",
    "quality": "quality.html",
    "supplier": "supplier.html",
}


def test_python_sources_parse():
    for path in ROOT.rglob("*.py"):
        if ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_all_role_workspace_templates_exist():
    base = ROOT / "templates" / "workspaces"
    for filename in EXPECTED.values():
        assert (base / filename).is_file(), filename


def test_role_workspace_blueprint_contains_expected_routes():
    source = (ROOT / "app" / "role_workspace.py").read_text(encoding="utf-8")
    for route in ["/", "/<role>", "/api/kpis"]:
        assert route in source
    for role in EXPECTED:
        assert role in source


def test_role_aliases_cover_operational_roles():
    source = (ROOT / "app" / "role_workspace.py").read_text(encoding="utf-8")
    for alias in ["purchase", "buyer", "qc", "qa", "storekeeper", "delivery", "vendor"]:
        assert f'"{alias}"' in source


def test_login_uses_role_aware_workspace():
    source = (ROOT / "blueprints" / "auth.py").read_text(encoding="utf-8")
    assert "role_workspace.my_workspace" in source


def test_live_kpi_api_is_used_by_workspaces():
    for path in (ROOT / "templates" / "workspaces").glob("*.html"):
        source = path.read_text(encoding="utf-8")
        assert "role_workspace.api_kpis" in source, path.name
        assert "MaterialHubKPIs" in source, path.name


def test_design_system_is_loaded():
    css = ROOT / "static" / "css" / "design-system.css"
    assert css.is_file()
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    assert "design-system.css" in base
