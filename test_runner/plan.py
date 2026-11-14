# Ren Xiang
import os
import sys

from test_runner.check import Check
from test_runner.command_check import CommandCheck
from test_runner.constants import BATCH_OUTPUT, FIRST_PHASE_TESTS
from test_runner.ownership_map import OwnershipMap
from test_runner.pytest_check import PytestCheck


# Builds the list of checks and works out which ones to run for the options given.
class Plan:
    def __init__(self, root: str) -> None:
        self._root = root
        self._ownership = OwnershipMap(os.path.join(root, "tests"))
        self._has_node_modules = os.path.isdir(os.path.join(root, "frontend", "node_modules"))

    def checks(self, owner: str | None = None) -> list[Check]:
        checks: list[Check] = [CommandCheck("lint", "Ren Xiang", 1, [sys.executable, "-m", "ruff", "check", "."], needs="ruff")]
        for file_name in self._ownership.files():
            phase = 1 if file_name in FIRST_PHASE_TESTS else 2
            ids = self._ownership.node_ids(file_name, owner)
            if ids:
                targets = ids if owner else [f"tests/{file_name}"]
                who = owner or "/".join(self._ownership.owners_in(file_name))
                checks.append(PytestCheck(file_name[len("test_"):-len(".py")], who, phase, targets))
        checks += [
            CommandCheck("batch", "Lennart", 2, [sys.executable, "main.py", "--batch", "tests/sample_batch.json"],
                         expect=BATCH_OUTPUT, extra_env={"DATABASE_URL": "{tmp}/triage.db"}),
            CommandCheck("frontend", "Lennart", 2, ["npm", "run", "build"], needs="npm", expect=("built in",),
                         cwd=os.path.join(self._root, "frontend"),
                         setup=None if self._has_node_modules else ["npm", "ci", "--no-audit", "--no-fund"]),
            CommandCheck("docker-build", "Darrel", 2, ["docker", "build", "-t", "triage-test", "."], needs="docker"),
            CommandCheck("docker-tests", "Darrel", 2, ["docker", "run", "--rm", "triage-test", "python", "-m", "pytest", "-q"], needs="docker"),
            # No DATABASE_URL and no keys: the container must still run, as it does for an assessor (local files, manual review).
            CommandCheck("docker-batch", "Darrel", 2, ["docker", "run", "--rm", "-e", "PYTHONUTF8=1",
                                                       "triage-test", "python", "main.py", "--batch", "tests/sample_batch.json"],
                         needs="docker", expect=BATCH_OUTPUT + ("saved in local files",)),
        ]
        return [c for c in checks if owner is None or c.owner == owner or isinstance(c, PytestCheck)]

    # The checks to run: due by `phase`, for `owner`, named in `only`, without Docker if skip_docker.
    def select(self, phase: int, owner: str | None, only: list[str], skip_docker: bool) -> list[Check]:
        chosen = [c for c in self.checks(owner) if c.phase <= phase]
        if only:
            chosen = [c for c in chosen if c.name in only]
        if skip_docker:
            chosen = [c for c in chosen if not c.name.startswith("docker")]
        return chosen