"""Fresh installed-wheel ABBA trials; fail closed on workload or artifact drift."""

import argparse
import asyncio
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent


async def run(args):
    args.output.mkdir(mode=0o700)
    inputs = {role: hashlib.sha256((args.artifacts / role / "mesh_plus-0.1.0a16-py3-none-any.whl").read_bytes()).hexdigest()
              for role in ("baseline", "candidate")}
    inputs["tmuxInstalledCopyManifestSha256"] = hashlib.sha256((args.artifacts / "tmux-installed-input.json").read_bytes()).hexdigest()
    inputs["harness"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob("*.py"))}
    values, blocks = [], []
    scenarios = [(phase, hosts, 32, 8) for phase in ("admission", "pipeline") for hosts in (1, 4, 16)]
    scenarios += [(phase, 16, 128, 4) for phase in ("admission", "pipeline")]
    scenarios += [(phase, 1, 1, 1000) for phase in ("heartbeat", "error")]
    if args.pilot:
        scenarios = [("pipeline", 4, 32, 4), ("heartbeat", 1, 1, 100)]
    for phase, hosts, rows, rounds in scenarios:
        for block in range(1 if args.pilot else 4):
            cases = []
            for position, role in enumerate(("baseline", "candidate", "candidate", "baseline")):
                command = [str(args.artifacts / (role + "-env") / "bin/python"), "-I", "-B", str(ROOT / "measure.py"),
                           "--phase", phase, "--hosts", str(hosts), "--rows", str(rows), "--rounds", str(rounds), "--native-profile"]
                child = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, stderr = await asyncio.wait_for(child.communicate(), 30)
                    if child.returncode:
                        raise RuntimeError("worker_failed:" + stderr.decode())
                    value = json.loads(stdout)
                finally:
                    if child.returncode is None:
                        child.kill()
                        await child.wait()
                value.update(role=role, block=block, position=position)
                if value["status"] != "passed" or not value["cleanup"]:
                    raise ValueError("case_not_accepted")
                cases.append(value)
                values.append(value)
            work = ("phase", "hosts", "rowsPerHost", "rounds", "nativeProfile", "expectedRowsSha256", "nativeReads", "packages", "harnessSha256")
            if any(any(v[k] != cases[0][k] for k in work) for v in cases[1:]):
                raise ValueError("workload_mismatch")
            for role in ("baseline", "candidate"):
                hashes = {v["runtimeSha256"] for v in values if v["role"] == role}
                if len(hashes) != 1:
                    raise ValueError("runtime_drift")
            a = statistics.mean(cases[i]["cpuNs"] for i in (0, 3))
            b = statistics.mean(cases[i]["cpuNs"] for i in (1, 2))
            item = {"phase": phase, "hosts": hosts, "rowsPerHost": rows, "rounds": rounds, "block": block,
                    "cpuReductionPercent": 100 * (1 - b / a), "baselineCpuNs": a, "candidateCpuNs": b,
                    "baselineClassifications": cases[0]["classifications"], "candidateClassifications": cases[1]["classifications"]}
            blocks.append(item)
            (args.output / "cases.json").write_text(json.dumps(values, indent=2) + "\n")
            print(json.dumps(item), flush=True)
    summary = {"status": "passed", "inputs": inputs, "cases": len(values), "matchedBlocks": len(blocks), "blocks": blocks,
               "limits": ["unprofiled pure publisher/Reader/Guard pipeline with installed Tmux a7 facade; no carrier/source I/O",
                          "independent expected-row oracle included in CPU time", "synthetic unchanged original receipts; not actual native push performance",
                          "RSS is process high-water including setup, not steady PSS or a memory decision gate",
                          "fresh subprocess per case, schema warmup outside timing, uncontrolled host background"]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    if not args.artifacts.is_absolute() or not args.output.is_absolute() or args.output.exists():
        parser.error("absolute_inputs_new_output")
    asyncio.run(run(args))
