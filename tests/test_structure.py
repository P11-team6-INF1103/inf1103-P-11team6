# Lennart
import ast
import os

import pytest

TESTS = os.path.dirname(__file__)
PROJECT = os.path.dirname(TESTS)
SKIPPED_FOLDERS = {".venv", "node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "dist", "data"}

# Files that still hold more than one class. Whoever owns a file removes its line here in the same pull request
# that splits it into one class per file (see "One class per file" in Task_Allocation_Part2.pdf). When the list is
# empty, delete it and the xfail handling below.
PENDING_SPLIT = {
    "ai_clients.py": "Ren Xiang: split into ai_clients/ (response_cache, json_reply, gemini_client)",
    "ai_manager.py": "Ren Xiang: move the steps into ai_steps/ and keep only AIManager here",
    "tests/fakes.py": "Ren Xiang: move the fakes into tests/doubles/",
}


def _python_files() -> list[str]:
    found = []
    for folder, subfolders, names in os.walk(PROJECT):
        subfolders[:] = [d for d in subfolders if d not in SKIPPED_FOLDERS]
        found += [os.path.join(folder, n) for n in names if n.endswith(".py")]
    return sorted(found)


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: os.path.relpath(p, PROJECT).replace(os.sep, "/"))
def test_every_python_file_holds_at_most_one_class(path):
    # INF1103 rule: one class per .py file, not one file with many classes.
    relative = os.path.relpath(path, PROJECT).replace(os.sep, "/")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    if relative in PENDING_SPLIT and len(classes) <= 1:
        pytest.fail(f"{relative} is already split: remove it from PENDING_SPLIT")
    if relative in PENDING_SPLIT:
        pytest.xfail(f"{relative} still holds {len(classes)} classes. {PENDING_SPLIT[relative]}")
    assert len(classes) <= 1, f"{relative} holds {len(classes)} classes: {classes}"
