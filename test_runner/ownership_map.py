#Ren Xiang

import ast
import os

from test_runner.constants import _NAME_TAG


# Which person each test function belongs to, read from the name comment above it (the same tags the task allocation uses).
class OwnershipMap:
    def __init__(self, tests_dir: str) -> None:
        self._tests: dict[str, dict[str, str]] = {}
        for file_name in sorted(os.listdir(tests_dir)):
            if file_name.startswith("test_") and file_name.endswith(".py"):
                self._tests[file_name] = self._read(os.path.join(tests_dir, file_name))

    @staticmethod
    def _read(path: str) -> dict[str, str]:
        with open(path, encoding="utf-8") as f:
            source = f.read()
        tags = [(number, _NAME_TAG.match(line).group(1))
                for number, line in enumerate(source.splitlines(), start=1) if _NAME_TAG.match(line)]
        owners = {}
        for node in ast.parse(source).body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                first = min([node.lineno] + [d.lineno for d in node.decorator_list])
                owners[node.name] = next((name for number, name in reversed(tags) if number <= first), "unassigned")
        return owners

    def files(self) -> list[str]:
        return list(self._tests)

    # The test ids of one file, only those owned by `owner` when it is given.
    def node_ids(self, file_name: str, owner: str | None = None) -> list[str]:
        return [f"tests/{file_name}::{test}" for test, who in self._tests[file_name].items() if owner in (None, who)]

    def owners_in(self, file_name: str) -> list[str]:
        return sorted(set(self._tests[file_name].values()))