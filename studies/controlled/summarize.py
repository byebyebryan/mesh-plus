"""Summarize exact-work blocks; retain CPU time, topology and measurement limits."""

import argparse
import gzip
import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matrix import qualify  # noqa: E402

PRIMARY = {"reader-driver", "publisher", "ssh-client", "ssh-server-session", "ssh-listener"}


def cost(value):
    roles = value["resources"]["roles"]
    selected = [role for role in roles if role["role"] in PRIMARY]
    cpu = sum(role["cpuPercent"] * role["seconds"] / 100 for role in selected)
    unknown = sum(role["pssMeanKiB"] is None for role in selected)
    return {"primaryCpuSeconds": cpu, "cpuMsPerDeliveredStep": cpu * 1000 / value["steps"] / value["fanout"],
            "accessiblePssMiB": sum(role["pssMeanKiB"] or 0 for role in selected) / 1024,
            "unknownPssRoles": unknown, "primaryProcesses": len(selected),
            "fixtureCpuSeconds": sum(role["cpuPercent"] * role["seconds"] / 100 for role in roles if role["role"] == "fixture-source"),
            "samplerCpuPercent": value["resources"]["samplerCpuPercent"],
            "latencyMedianMs": value["latencyMedianMs"]}


def run(args):
    values = [json.loads(path.read_text()) for path in sorted(args.root.glob("*.json")) if path.name not in ("inputs.json", "index.json")]
    if len(values) != 192:
        raise ValueError("incomplete_192_case_matrix")
    groups = sorted({(v["pair"], v["mode"], v["fanout"], v["block"]) for v in values})
    blocks = []
    for pair, mode, fanout, number in groups:
        cases = sorted([v for v in values if (v["pair"], v["mode"], v["fanout"], v["block"]) == (pair, mode, fanout, number)], key=lambda v: v["position"])
        qualify(cases)
        costs = [cost(value) for value in cases]
        a = {key: statistics.mean(costs[i][key] for i in (0, 3)) for key in costs[0]}
        b = {key: statistics.mean(costs[i][key] for i in (1, 2)) for key in costs[0]}
        blocks.append({"pair": pair, "mode": mode, "fanout": fanout, "block": number, "status": "exact_work_matched",
            "A": a, "B": b, "cpuReductionPercent": 100 * (1 - b["primaryCpuSeconds"] / a["primaryCpuSeconds"]),
            "accessiblePssReductionPercent": 100 * (1 - b["accessiblePssMiB"] / a["accessiblePssMiB"]),
            "jsonBytes": [v["canonicalJsonBytes"] for v in cases],
            "backgroundCpuPercent": [v["resources"]["unattributedCpuPercent"] for v in cases]})
    raw = json.dumps({"inputs": json.loads((args.root / "inputs.json").read_text()), "cases": values}, sort_keys=True, separators=(",", ":")).encode()
    packed = gzip.compress(raw, mtime=0)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "matrix.json.gz").write_bytes(packed)
    summary = {"format": "mesh-plus.controlled-performance.v1", "cases": len(values), "matchedBlocks": len(blocks),
        "gzipSha256": hashlib.sha256(packed).hexdigest(), "rawSha256": hashlib.sha256(raw).hexdigest(), "blocks": blocks,
        "measurementHarnessInputSha256": hashlib.sha256((args.root / "inputs.json").read_bytes()).hexdigest(),
        "summaryToolSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "scope": "loopback synthetic 32-row Tmux trace; persistent poll/push; fresh owned resources; shared driver caches",
        "limits": ["reader-driver includes oracle native validation, control and sampler RPC overhead",
                   "fixture cached acquisition cost separate from primary total", "10ms own-tick quantization on this host",
                   "sampled memory cannot certify transient peaks", "background host load remains uncontrolled",
                   "fanout compares one shared IPC/WSS publisher with independent SSH publishers",
                   "no ordinary fleet budget, real network latency or WSS operational selection acceptance",
                   "no Agent Observer imports, source edits or live tests"]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"cases": len(values), "matchedBlocks": len(blocks), "compressedBytes": len(packed)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
