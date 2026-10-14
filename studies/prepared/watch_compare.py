"""Serial changing-watch ABBA timing or separate paired allocation evidence."""

import argparse
import json
import statistics
import subprocess
from pathlib import Path


def main(args):
    args.output.mkdir(mode=0o700)
    script = Path(__file__).with_name("watch_measure.py")
    cases, blocks = [], []
    for change in ("envelope", "native"):
        for hosts in ((1, 4, 16) if args.memory else (1, 4)):
            for reads in ((1,) if args.memory else (1, 4, 16)):
                for block in range(1 if args.memory else 4):
                    cell = []
                    modes = ("legacy", "prepared") if args.memory else ("legacy", "prepared", "prepared", "legacy")
                    for position, mode in enumerate(modes):
                        command = [str(args.python), "-I", "-B", str(script), "--mode", mode,
                                   "--hosts", str(hosts), "--reads", str(reads), "--change", change]
                        if args.memory:
                            command += ["--memory", "--publications", "16" if hosts == 16 else "32"]
                        result = subprocess.run(command, capture_output=True, timeout=180)
                        if result.returncode:
                            (args.output / "failure.json").write_text(json.dumps(dict(
                                command=command, returncode=result.returncode,
                                stdout=result.stdout.decode(), stderr=result.stderr.decode()), indent=2) + "\n")
                            raise RuntimeError("watch_case_failed_see_failure_json")
                        value = json.loads(result.stdout)
                        value.update(block=block, position=position)
                        if value["status"] != "passed" or not value["cleanup"]:
                            raise ValueError("unaccepted_case")
                        cell.append(value)
                        cases.append(value)
                        (args.output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n")
                    equal = ("hosts", "rowsPerHost", "reads", "publications", "change", "inputOracleSha256",
                             "preflightSchemaAdmissions", "sourceAcquisitions", "harnessDigests", "runtimeDigests",
                             "meshVersion", "python")
                    if not args.memory:
                        equal += ("admissions", "queries", "cycles")
                    if any(any(value[key] != cell[0][key] for value in cell[1:]) for key in equal):
                        raise ValueError("work_or_input_mismatch")
                    if args.memory:
                        value = dict(change=change, hosts=hosts,
                                     legacy={key: cell[0][key] for key in cell[0] if "TracedBytes" in key},
                                     prepared={key: cell[1][key] for key in cell[1] if "TracedBytes" in key})
                    else:
                        legacy = statistics.mean(cell[index]["cpuNs"] for index in (0, 3))
                        prepared = statistics.mean(cell[index]["cpuNs"] for index in (1, 2))
                        value = dict(change=change, hosts=hosts, reads=reads, block=block,
                                     legacyCpuNs=legacy, preparedCpuNs=prepared,
                                     cpuReductionPercent=100 * (1 - prepared / legacy))
                    blocks.append(value)
                    print(json.dumps(value), flush=True)
    (args.output / "summary.json").write_text(json.dumps(dict(status="passed", cases=len(cases), blocks=blocks,
        scope="separate traced guard allocations" if args.memory else "persistent changing-publication consumer CPU; no network/source performance"), indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    if not args.python.is_absolute() or not args.output.is_absolute() or args.output.exists():
        parser.error("absolute_new_output_required")
    main(args)
