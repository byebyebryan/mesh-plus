"""Longer one-host pipeline repeat to resolve a short-cell regression outlier."""

import argparse
import json
import statistics
import subprocess
from pathlib import Path


def main(args):
    cases, blocks = [], []
    for block in range(4):
        values = []
        for position, role in enumerate(("baseline", "candidate", "candidate", "baseline")):
            result = subprocess.run([str(args.artifacts / (role + "-env") / "bin/python"), "-I", "-B",
                str(Path(__file__).with_name("measure.py")), "--phase", "pipeline", "--hosts", "1",
                "--rows", "32", "--rounds", "128", "--native-profile"], check=True, capture_output=True, timeout=15)
            value = json.loads(result.stdout)
            if value["status"] != "passed" or not value["cleanup"]:
                raise ValueError("repeat_not_accepted")
            value.update(role=role, block=block, position=position)
            values.append(value)
            cases.append(value)
        for key in ("phase", "hosts", "rowsPerHost", "rounds", "nativeReads", "expectedRowsSha256", "harnessSha256", "packages"):
            if any(v[key] != values[0][key] for v in values[1:]):
                raise ValueError("repeat_work_mismatch")
        a = statistics.mean(values[i]["cpuNs"] for i in (0, 3))
        b = statistics.mean(values[i]["cpuNs"] for i in (1, 2))
        item = {"block": block, "cpuReductionPercent": 100 * (1 - b / a), "baselineCpuNs": a, "candidateCpuNs": b}
        blocks.append(item)
        print(json.dumps(item), flush=True)
    args.output.write_text(json.dumps({"status": "passed", "cases": cases, "blocks": blocks}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.artifacts.is_absolute() or not args.output.is_absolute() or args.output.exists():
        parser.error("absolute_inputs_new_output")
    main(args)
