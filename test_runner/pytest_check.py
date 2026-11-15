#Ren Xiang

import re
import sys

from test_runner.command_check import CommandCheck
from test_runner.constants import _COUNTS


# Runs pytest on whole files, or on only the tests one person owns.
class PytestCheck(CommandCheck):
    def __init__(self, name: str, owner: str, phase: int, targets: list[str]) -> None:
        super().__init__(name, owner, phase, [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets])
        self._targets = targets

    def describe(self) -> str:
        return f"pytest {self._targets[0].split('::')[0]}" + (f" ({len(self._targets)} tests)" if "::" in self._targets[0] else "")

    def summary(self, output: str, code: int, missing: list[str]) -> str:
        last = [line for line in output.splitlines() if _COUNTS.search(line)]
        return re.sub(r"[= ]{2,}", " ", last[-1]).strip() if last else f"exit code {code}"