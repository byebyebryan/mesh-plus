"""Sequential matched replay runs, avoiding contention between matrix cases."""

import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--python", type=Path, required=True)
parser.add_argument("--private-directory", type=Path, required=True)
parser.add_argument("--seconds", type=int, default=15)
parser.add_argument("--operation", choices=("watch", "snapshot"), default="watch")
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
for domain in ("tmux", "agent"):
    for carrier in ("ipc", "ssh"):
        for processes in (1, 4):
            for updates in ((False,) if args.operation == "snapshot" else (False, True)):
                name = f"matched-{args.operation}-{domain}-{carrier}-{processes}-{'updates' if updates else 'idle'}"
                command = [str(args.python), str(root / "scripts/measure-processes.py"),
                           "--domain", domain, "--carrier", carrier,
                           "--frame", str(args.private_directory / f"native-{domain}.json"),
                           "--processes", str(processes), "--seconds", str(args.seconds),
                           "--operation", args.operation,
                           "--proof-interval", "3", "--report", str(args.private_directory / (name + ".json"))]
                if updates:
                    command.append("--updates")
                subprocess.run(command, check=True, timeout=args.seconds + 80)
