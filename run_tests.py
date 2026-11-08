# Ren Xiang
# Runs every automated check from one command, offline: 
# no API keys and no real database are passed on.

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
OWNERS = ("Lennart", "Daniel", "Darrel", "Sufi", "Ren Xiang")
PHASE_NAMES = {1: "Development 1 (2-8 Nov)", 2: "Development 2 (9-15 Nov)", 3: "Misc (16-18 Nov)"}
PHASE_KEYS = {"dev1": 1, "dev2": 2, "misc": 3}
# Phase 1 tests need only the managers; phase 2 tests need the wiring, the web API and the features.
FIRST_PHASE_TESTS = {"test_models.py", "test_database.py", "test_data_manager.py", "test_logic_manager.py",
                     "test_io_manager.py", "test_ai_manager.py"}
BATCH_OUTPUT = ("INCIDENT SUMMARY", "Total incidents: 3", "With a photo: 1")
_NAME_TAG = re.compile(r"^\s*#\s?(Lennart|Daniel|Darrel|Sufi|Ren Xiang)\s*$")
_COUNTS = re.compile(r"(\d+) (passed|failed|errors?|skipped|deselected)")


@dataclass
class Result:
    status: str  # PASS, FAIL or SKIP
    detail: str = ""
    seconds: float = 0.0


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


# One thing to check. Subclasses say how to run it; the runner never needs to know which kind it has.
class Check(ABC):
    def __init__(self, name: str, owner: str, phase: int) -> None:
        self.name = name
        self.owner = owner
        self.phase = phase

    @abstractmethod
    def describe(self) -> str:
        ...

    @abstractmethod
    def run(self, runner: "Runner") -> Result:
        ...


# Runs one command (after an optional setup command). It passes when the exit code is 0 and every `expect` text is in the output.
class CommandCheck(Check):
    def __init__(self, name: str, owner: str, phase: int, command: list[str], needs: str | None = None,
                 expect: tuple[str, ...] = (), extra_env: dict[str, str] | None = None, cwd: str | None = None,
                 setup: list[str] | None = None) -> None:
        super().__init__(name, owner, phase)
        self._command = command
        self._needs = needs
        self._expect = expect
        self._extra_env = extra_env or {}
        self._cwd = cwd
        self._setup = setup

    def describe(self) -> str:
        return " ".join("python" if part == sys.executable else part for part in self._command)

    def _execute(self, command: list[str], runner: "Runner") -> tuple[int, str]:
        env = runner.env({key: value.replace("{tmp}", runner.scratch) for key, value in self._extra_env.items()})
        done = subprocess.run(command, check=False, cwd=self._cwd or runner.cwd, env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=900)
        return done.returncode, (done.stdout or "") + (done.stderr or "")

    def run(self, runner: "Runner") -> Result:
        reason = runner.missing(self._needs)
        if reason:
            return Result("SKIP", reason)
        started = time.time()
        try:
            if self._setup:
                code, output = self._execute(self._setup, runner)
                if code:
                    runner.show_failure(output)
                    return Result("FAIL", "setup failed: " + " ".join(self._setup), time.time() - started)
            code, output = self._execute(self._command, runner)
        except (OSError, subprocess.TimeoutExpired) as error:
            return Result("FAIL", str(error), time.time() - started)
        missing = [text for text in self._expect if text not in output]
        status = "PASS" if code == 0 and not missing else "FAIL"
        if status == "FAIL":
            runner.show_failure(output)
        return Result(status, self.summary(output, code, missing), time.time() - started)

    def summary(self, output: str, code: int, missing: list[str]) -> str:
        if missing:
            return "output is missing: " + ", ".join(missing)
        if self._expect and not code:
            return "output has: " + ", ".join(self._expect)
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        return lines[-1][:90] if lines else f"exit code {code}"


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


class Runner:
    def __init__(self, cwd: str, strict: bool) -> None:
        self.cwd = cwd
        self.strict = strict
        self.scratch = tempfile.mkdtemp(prefix="triage-tests-")

    # The environment every check runs in: no API keys, no database, a throwaway data folder. The variables are set
    # to empty rather than removed, because the app's load_dotenv() would otherwise refill them from the real .env.
    def env(self, extra: dict[str, str]) -> dict[str, str]:
        env = dict(os.environ)
        env.update({name: "" for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "DATABASE_URL")})
        env.update({"INCIDENT_DATA_DIR": os.path.join(self.scratch, "data"), "PYTHONUTF8": "1"})
        env.update(extra)
        return env

    # Why a check cannot run on this machine, or None if it can.
    def missing(self, need: str | None) -> str | None:
        if need == "ruff" and subprocess.run([sys.executable, "-m", "ruff", "--version"], check=False,
                                             capture_output=True).returncode:
            return "ruff is not installed (pip install ruff==0.17.2)"
        if need == "npm" and not shutil.which("npm"):
            return "npm is not installed"
        if need == "docker":
            if not shutil.which("docker"):
                return "docker is not installed"
            if subprocess.run(["docker", "info"], check=False, capture_output=True).returncode:
                return "the docker daemon is not running"
        return None

    @staticmethod
    def show_failure(output: str) -> None:
        print("\n".join("      " + line for line in output.strip().splitlines()[-40:]))

    def run_all(self, checks: list[Check]) -> list[tuple[Check, Result]]:
        results = []
        for check in checks:
            print(f"  ...  {check.name:<18} {check.describe()[:80]}", flush=True)
            result = check.run(self)
            print(f"[{result.status}] {check.name:<18} {check.owner:<10} {PHASE_NAMES[check.phase].split(' (')[0]:<14} {result.detail}")
            results.append((check, result))
        return results

    def close(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)


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


# What `python run_tests.py` does: reads the options, picks the checks and runs them.
class CommandLine:
    @staticmethod
    def resolve_owner(text: str | None) -> str | None:
        if not text:
            return None
        key = text.replace(" ", "").lower()
        for name in OWNERS:
            if name.replace(" ", "").lower().startswith(key):
                return name
        raise SystemExit(f"Unknown owner '{text}'. Use one of: {', '.join(OWNERS)}.")

    @staticmethod
    def write_report(path: str, results: list[tuple[Check, Result]], title: str) -> None:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, cwd=ROOT, capture_output=True,
                                text=True).stdout.strip()
        intro = (f"Run on {datetime.now():%d %b %Y %H:%M}, commit {commit or 'unknown'}. "
                 "No API keys and no real database were available to the checks.")
        lines = [f"# Test report: {title}", "", intro, "",
                 "| Check | Owner | Phase | Result | Detail | Seconds |", "|---|---|---|---|---|---|"]
        for check, result in results:
            lines.append(f"| {check.name} | {check.owner} | {PHASE_NAMES[check.phase].split(' (')[0]} | {result.status} | "
                         f"{result.detail} | {result.seconds:.1f} |")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    @classmethod
    def main(cls) -> int:
        parser = argparse.ArgumentParser(description="Run the automated checks, offline.")
        parser.add_argument("--phase", choices=sorted(PHASE_KEYS), default="misc", help="run what is due by the end of this phase")
        parser.add_argument("--owner", help="only the tests this person owns, and the checks they own")
        parser.add_argument("--only", help="comma-separated check names (see --list)")
        parser.add_argument("--skip-docker", action="store_true")
        parser.add_argument("--strict", action="store_true", help="a skipped check counts as a failure")
        parser.add_argument("--fresh-clone", action="store_true", help="run inside a clean clone of the committed code")
        parser.add_argument("--report", metavar="FILE", help="also write a Markdown result table")
        parser.add_argument("--list", action="store_true", help="show the checks and exit")
        args = parser.parse_args()

        owner = cls.resolve_owner(args.owner)
        phase = PHASE_KEYS[args.phase]
        only = [name.strip() for name in (args.only or "").split(",") if name.strip()]
        plan = Plan(ROOT)
        chosen = plan.select(phase, owner, only, args.skip_docker)
        if args.list:
            for check in chosen:
                print(f"{check.name:<18} {check.owner:<28} {PHASE_NAMES[check.phase]:<26} {check.describe()[:60]}")
            return 0

        runner = Runner(ROOT, args.strict)
        try:
            if args.fresh_clone:
                clone = os.path.join(runner.scratch, "clone")
                subprocess.run(["git", "clone", "--quiet", ROOT, clone], check=True)
                runner.cwd = clone
                chosen = Plan(clone).select(phase, owner, only, args.skip_docker)
                print(f"Running in a fresh clone of the committed code ({clone}); uncommitted changes are not tested.")
            title = f"{PHASE_NAMES[phase]}" + (f", {owner}'s tests" if owner else "")
            print(f"{title}: {len(chosen)} checks\n")
            results = runner.run_all(chosen)
        finally:
            runner.close()

        failed = [c.name for c, r in results if r.status == "FAIL"]
        skipped = [c.name for c, r in results if r.status == "SKIP"]
        print(f"\n{sum(r.status == 'PASS' for _, r in results)} passed, {len(failed)} failed, {len(skipped)} skipped"
              + (f"  (skipped: {', '.join(skipped)})" if skipped else ""))
        if args.report:
            cls.write_report(args.report, results, title)
            print(f"Report written to {args.report}")
        return 1 if failed or (args.strict and skipped) else 0


if __name__ == "__main__":
    raise SystemExit(CommandLine.main())
