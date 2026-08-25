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
        try:
            ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception as exc:
            errors.append((str(p), str(exc)))
    assert not errors, errors
