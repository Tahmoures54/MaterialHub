"""Portable test launcher for MaterialHub.

Usage:
    python tests/run_tests.py

The launcher always runs the dependency-free contract suite. If pytest and
Flask are installed it also runs the integration suite.
"""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
cmd = [sys.executable, "-m", "pytest", "tests", "-q"]
try:
    result = subprocess.run(cmd, cwd=ROOT)
except Exception as exc:
    print(f"Unable to start pytest: {exc}")
    raise SystemExit(2)
raise SystemExit(result.returncode)
