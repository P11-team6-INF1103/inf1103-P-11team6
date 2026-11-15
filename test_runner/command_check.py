#Ren Xiang

import subprocess
import sys
import time
from typing import TYPE_CHECKING

from test_runner.check import Check
from test_runner.result import Result

if TYPE_CHECKING:
    from test_runner.runner import Runner


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