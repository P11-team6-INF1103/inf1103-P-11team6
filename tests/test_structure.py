# Lennart
import ast
import os

import pytest

TESTS = os.path.dirname(__file__)

# --- Brief: "no remaining procedural style code" and the course rule "one class per file" ---

PROJECT = os.path.dirname(TESTS)
SKIPPED_FOLDERS = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "data"}


def _python_files(include_tests: bool) -> list[str]:
    found = []
    for folder, subfolders, names in os.walk(PROJECT):
        subfolders[:] = [d for d in subfolders if d not in SKIPPED_FOLDERS and (include_tests or d != "tests")]
        found += [os.path.join(folder, n) for n in names if n.endswith(".py")]
    return sorted(found)


@pytest.mark.parametrize("path", _python_files(include_tests=False))
def test_no_module_holds_a_loose_function(path):
    # Every function lives in a class. The one exception is the plain factory gunicorn needs to start the web API.
    allowed = {"create_app"}
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    loose = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert set(loose) <= allowed, f"{os.path.relpath(path, PROJECT)} has functions outside a class: {loose}"


@pytest.mark.parametrize("path", _python_files(include_tests=True))
def test_every_python_file_holds_at_most_one_class(path):
    # INF1103 rule: one class per .py file, not one file with many classes.
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    assert len(classes) <= 1, f"{os.path.relpath(path, PROJECT)} holds {len(classes)} classes: {classes}"
