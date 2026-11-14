#Ren Xiang

import os
import shutil
import subprocess
import sys
import tempfile

from test_runner.check import Check
from test_runner.constants import PHASE_NAMES
from test_runner.result import Result


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