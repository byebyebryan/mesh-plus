"""One standalone validation gate; native and sibling-source checks are explicit."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wss", action="store_true", help="include optional WSS extra acceptance")
    parser.add_argument("--native", action="store_true", help="include owned native/SSH tests; requires Observers")
    parser.add_argument("--check-sources", action="store_true", help="verify reviewed sibling source baselines")
    args = parser.parse_args()
    commands = [
        ["scripts/check-contract-lock.py"],
        ["scripts/check-design.py", *(["--check-sources"] if args.check_sources else [])],
        ["scripts/check-delivery.py"],
        ["scripts/check-view-feed.py"],
        ["scripts/check-runtime.py", *([] if args.native else ["--core-only"])],
        ["-m", "ruff", "check", "src", "tests", "scripts"],
    ]
    if args.wss:
        commands.append(["scripts/check-wss.py", *(["--native"] if args.native else [])])
    for command in commands:
        print("[check] " + " ".join(command), flush=True)
        result = subprocess.run([sys.executable, *command], cwd=ROOT)
        if result.returncode:
            return result.returncode if result.returncode > 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
