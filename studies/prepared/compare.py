"""Four ABBA blocks of complete legacy/prepared consumer lifetimes."""

import argparse
import hashlib
import json
import statistics
import subprocess
from pathlib import Path


def main(args):
    args.output.mkdir(mode=0o700)
    root = Path(__file__).resolve().parent
    records, blocks = [], []
    for hosts in (1, 4):
        for reads in (1, 4, 16):
            for block in range(4):
                cases = []
                for position, mode in enumerate(("legacy", "prepared", "prepared", "legacy")):
                    result = subprocess.run([str(args.python), "-I", "-B", str(root / "measure.py"), "--mode", mode,
                        "--hosts", str(hosts), "--reads", str(reads), "--cycles", "8"], capture_output=True, check=True, timeout=30)
                    value = json.loads(result.stdout)
                    value.update(block=block, position=position)
                    if value["status"] != "passed" or not value["cleanup"]:
                        raise ValueError("case_not_accepted")
                    cases.append(value)
                    records.append(value)
                for key in ("hosts", "rowsPerHost", "reads", "cycles", "admissions", "queries", "sourceAcquisitions", "expectedRowsSha256", "harnessSha256"):
                    if any(v[key] != cases[0][key] for v in cases[1:]):
                        raise ValueError("work_mismatch")
                a = statistics.mean(cases[i]["cpuNs"] for i in (0, 3))
                b = statistics.mean(cases[i]["cpuNs"] for i in (1, 2))
                value = {"hosts": hosts, "reads": reads, "block": block, "legacyCpuNs": a, "preparedCpuNs": b,
                         "cpuReductionPercent": 100 * (1 - b / a)}
                blocks.append(value)
                print(json.dumps(value), flush=True)
                (args.output / "cases.json").write_text(json.dumps(records, indent=2) + "\n")
    (args.output / "summary.json").write_text(json.dumps({"status": "passed", "cases": len(records), "blocks": blocks,
        "studyFiles": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('*.py'))},
        "scope": "complete consumer lifetimes; additive opt-in single-admission consumer; test-only Tmux compiler; no whole-pipeline or deployment performance acceptance"}, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.python.is_absolute() or not args.output.is_absolute() or args.output.exists():
        parser.error("absolute_inputs_new_output")
    main(args)
