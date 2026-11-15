# Ren Xiang
# Runs every automated check from one command, offline: no API keys and no real database are passed on.
#   python run_tests.py                      everything that can run on this machine
#   python run_tests.py --phase dev1         the checks due by the end of Development 1 (Sun 8 Nov)
#   python run_tests.py --phase dev2         ... by the end of Development 2 (Sun 15 Nov), cumulative
#   python run_tests.py --owner Daniel       only the tests tagged with that name, plus the checks that person owns
#   python run_tests.py --fresh-clone --strict --report test_report.md    the final gate, from a clean clone of HEAD
#   python run_tests.py --list               every check with its owner and phase
import argparse
import os
import subprocess
from datetime import datetime

from test_runner.check import Check
from test_runner.constants import OWNERS, PHASE_KEYS, PHASE_NAMES
from test_runner.plan import Plan
from test_runner.result import Result
from test_runner.runner import Runner

ROOT = os.path.dirname(os.path.abspath(__file__))

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
