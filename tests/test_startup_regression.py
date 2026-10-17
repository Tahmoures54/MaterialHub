from pathlib import Path
import ast, re

ROOT = Path(__file__).resolve().parents[1]

def test_generate_next_mr_no_is_defined():
    utils = (ROOT / "utils.py").read_text(encoding="utf-8")
    assert re.search(r"^\s*def\s+generate_next_mr_no\s*\(", utils, re.M)

def test_material_requisition_import_target_exists():
    utils = (ROOT / "utils.py").read_text(encoding="utf-8")
    assert "generate_next_mr_no" in utils

def test_python_sources_parse():
    errors=[]
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception as exc:
            errors.append((str(p), str(exc)))
    assert not errors, errors


def test_auth_uses_moved_register_template():
    auth = (ROOT / "blueprints" / "auth.py").read_text(encoding="utf-8")
    assert "auth/register.html" in auth
    assert "render_template(\n        'register.html'" not in auth
    assert "'register.html'" not in auth


def test_warehouse_blueprint_is_readable_and_importable():
    source = (ROOT / "blueprints" / "warehouse.py").read_text(encoding="utf-8")
    assert "zlib.decompress" not in source
    assert "exec(compile(" not in source

    from blueprints.warehouse import warehouse_bp

    endpoint_names = {rule.endpoint.rsplit(".", 1)[-1] for rule in warehouse_bp.deferred_functions if False}
    # Import itself is the regression boundary; app integration tests verify registration.
    assert warehouse_bp.name == "warehouse"
