#!/usr/bin/env python3
"""Byte-bound generic/source-adapter checkpoint; no package or native gate."""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def inputs(root, paths):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    observer, output = args.observer_checkout.resolve(), args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("write evidence only inside the owning Mesh repository")
    if any(path.exists() for path in (output, output.with_suffix(".gate1.log"), output.with_suffix(".gate2.log"))):
        parser.error("preserve prior evidence; choose a new output path")

    def snapshot():
        mesh_paths = [*ROOT.glob("src/mesh_plus/**/*.py"), *ROOT.glob("tests/test_sync_*.py"),
                      *ROOT.glob("scripts/check*.py"), ROOT / "pyproject.toml", ROOT / "contracts/LOCK.json",
                      ROOT / "docs/delta-sync-contract-appendix.md"]
        observer_paths = [*observer.glob("agent_observer/*.py"), *observer.glob("agent_observer/contracts/*.json"),
                          observer / "tests/test_mesh_sync_profile.py", observer / "tests/test_service_state.py"]
        return {"mesh": inputs(ROOT, mesh_paths), "observer": inputs(observer, observer_paths)}

    before = snapshot()
    output.parent.mkdir(parents=True, exist_ok=True)
    commands = [["rtk", "proxy", sys.executable, "scripts/check.py"],
                ["rtk", "proxy", sys.executable, "-m", "unittest", "discover", "-s", str(observer / "tests"),
                 "-p", "test_mesh_sync_profile.py", "-q"]]
    runs = []
    for index, command in enumerate(commands):
        gate_env = os.environ.copy()
        if index:
            gate_env["PYTHONPATH"] = os.pathsep.join((str(ROOT / "src"), str(observer)))
        completed = subprocess.run(command, cwd=ROOT, env=gate_env, capture_output=True, text=True)
        log = output.with_suffix(f".gate{index + 1}.log")
        log.write_text(completed.stdout + completed.stderr)
        counts = re.findall(r'"testsRun":\s*(\d+)', completed.stdout) if index == 0 else re.findall(r"Ran (\d+) tests", completed.stderr)
        runs.append({"argv": command, "exitCode": completed.returncode,
                     "tests": None if not counts else int(counts[-1]),
                     "log": str(log.relative_to(ROOT)), "logSha256": hashlib.sha256(log.read_bytes()).hexdigest()})
    after = snapshot()
    stable = before == after
    report = {"kind": "owned acquisition and preallocation source checkpoint; not G1/G2 acceptance",
              "checkedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "python": sys.version.split()[0], "sourceStableDuringRun": stable,
              "passed": stable and all(run["exitCode"] == 0 for run in runs), "runs": runs, "inputs": before,
              "exclusions": ["not the --native gate or independent domain acceptance", "no new wheel/version allocation",
                             "no new sync IPC/fixed SSH acceptance", "no matched CPU/bytes/RSS/plateau acceptance",
                             "old lock and schema bytes preserved", "no rollout, service or sibling source mutation"]}
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("passed", "sourceStableDuringRun", "python", "runs")}, sort_keys=True))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
