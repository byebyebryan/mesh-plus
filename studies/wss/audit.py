"""Read-only final source and owned-process hygiene audit; no private data output."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent


def main():
    baseline = json.loads((STUDY / "baseline.json").read_text())
    drift = [name for name, expected in baseline["runtimeInputs"].items()
             if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    owned = []
    for process in Path("/proc").iterdir():
        if not process.name.isdecimal():
            continue
        try:
            argv = (process / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        script = any(arg.endswith(b"/studies/wss/node.py") or arg.endswith(b"/studies/wss/measure.py")
                     for arg in argv)
        executable = Path(argv[0].decode(errors="replace")).name if argv[0] else ""
        fixture = executable in {"ssh", "sshd", "sshd-session", "socat"} and any(
            b".mesh-wss-measure-" in arg for arg in argv)
        if script or fixture:
            owned.append(int(process.name))
    directories = len(list(Path.home().glob(".mesh-wss-measure-*")))
    report = {"format": "mesh-plus.wss-study.hygiene.v1", "status": "passed" if not drift and not owned and
              directories == 0 else "failed", "runtimeDrift": drift, "ownedStudyProcesses": owned,
              "retainedMeasureDirectories": directories,
              "scope": "exact runtime hashes and study argv markers; unrelated processes excluded"}
    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
