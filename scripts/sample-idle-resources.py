"""Read process memory only for the explicitly named running idle-study fixture."""

import argparse
import json
import os
import time
from pathlib import Path


def memory(node):
    status = dict(line.split(":", 1) for line in (node / "status").read_text().splitlines())
    rollup = dict(line.split(":", 1) for line in (node / "smaps_rollup").read_text().splitlines()
                  if ":" in line)
    birth = (node / "stat").read_text().rpartition(") ")[2].split()[19]
    return {"pid": int(node.name), "birth": birth,
            "rssKiB": int(rollup["Rss"].split()[0]), "pssKiB": int(rollup["Pss"].split()[0]),
            "peakRssKiB": int(status["VmHWM"].split()[0])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run = str(args.run.resolve())
    processes = []
    for node in Path("/proc").iterdir():
        if not node.name.isdigit():
            continue
        try:
            argv = (node / "cmdline").read_bytes().decode().split("\0")
            processes.append((node, argv))
        except (OSError, UnicodeDecodeError):
            continue
    selected, roots, fleet_pids = {}, set(), set()
    for node, argv in processes:
        if "--output" not in argv or "--child" not in argv:
            continue
        if argv[argv.index("--output") + 1] != run:
            continue
        role = argv[argv.index("--child") + 1] + "-" + argv[argv.index("--role") + 1]
        roots.add(argv[argv.index("--fixture-root") + 1])
        selected[role] = node
        if role == "fleet-local":
            for task in (node / "task").iterdir():
                fleet_pids.update((task / "children").read_text().split())
    if len(roots) != 1 or len(selected) != 3:
        raise RuntimeError("one complete named fixture required")
    root = roots.pop()
    for node, argv in processes:
        if root + "/publisher-launcher.py" in argv:
            selected["bridge-remote"] = node
        if node.name in fleet_pids and (node / "comm").read_text().strip() == "ssh":
            selected["ssh-client"] = node
    if len(selected) != 5:
        raise RuntimeError("named fixture transport processes missing")
    record = {"run": args.run.name, "observedAt": time.time(), "loadAverage": os.getloadavg(),
              "processes": {role: memory(node) for role, node in selected.items()},
              "scope": "RSS/PSS snapshots; kernel peak RSS includes setup; not cgroup or peak PSS; "
                       "SSH daemon helpers and tmux servers excluded"}
    with args.output.open("a") as output:
        output.write(json.dumps(record, sort_keys=True) + "\n")
    print(json.dumps({"run": record["run"], "roles": len(selected),
                      "fleet": record["processes"]["fleet-local"]}))


if __name__ == "__main__":
    main()
