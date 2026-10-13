"""Requalify and archive matched WSS/TCP study blocks; no physical-wire claim."""

import argparse
import gzip
import hashlib
import json
import statistics
import sys
from pathlib import Path

# Installed under studies/compact; runner roots can live elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "controlled"))
from matrix import qualify  # noqa: E402


def cost(value):
    roles = value["resources"]["roles"]
    primary = [r for r in roles if r["role"] in {"reader-driver", "publisher"}]
    cpu = sum(r["cpuPercent"] * r["seconds"] / 100 for r in primary)
    return {"primaryCpuSeconds": cpu, "cpuMsPerDelivery": cpu * 1000 / value["steps"] / value["fanout"],
            "accessiblePssMiB": sum(r["pssMeanKiB"] or 0 for r in primary) / 1024,
            "unknownPssRoles": sum(r["pssMeanKiB"] is None for r in primary),
            "latencyMedianMs": statistics.median(value["latencyMs"]),
            "fixtureCpuSeconds": sum(r["cpuPercent"] * r["seconds"] / 100 for r in roles if r["role"] == "fixture-source"),
            "samplerCpuPercent": value["resources"]["samplerCpuPercent"]}


def run(args):
    values = [json.loads(p.read_text()) for p in sorted(args.root.glob("*.json")) if p.name not in {"inputs.json", "index.json"}]
    index = json.loads((args.root / "index.json").read_text())
    if len(values) != args.expected_cases or len(index) * 4 != len(values):
        raise ValueError("incomplete_matrix")
    groups = sorted({(v["mode"], v["fanout"], v["block"]) for v in values})
    if len(groups) != len(index):
        raise ValueError("incomplete_index")
    blocks = []
    for mode, fanout, number in groups:
        cases = sorted([v for v in values if (v["mode"], v["fanout"], v["block"]) == (mode, fanout, number)], key=lambda v: v["position"])
        if [v["carrier"] for v in cases] != ["wss", "tcp", "tcp", "wss"]:
            raise ValueError("carrier_order")
        qualify(cases)
        costs = [cost(v) for v in cases]
        a = {key: statistics.mean(costs[i][key] for i in (0, 3)) for key in costs[0]}
        b = {key: statistics.mean(costs[i][key] for i in (1, 2)) for key in costs[0]}
        blocks.append({"mode": mode, "fanout": fanout, "block": number, "status": "exact_work_matched", "wss": a, "tcp": b,
                       "cpuReductionPercent": 100 * (1 - b["primaryCpuSeconds"] / a["primaryCpuSeconds"]),
                       "pssReductionPercent": 100 * (1 - b["accessiblePssMiB"] / a["accessiblePssMiB"]),
                       "jsonBytes": [v["canonicalJsonBytes"] for v in cases],
                       "backgroundCpuPercent": [v["resources"]["unattributedCpuPercent"] for v in cases]})
    decisions = []
    for mode, fanout in sorted({(b["mode"], b["fanout"]) for b in blocks}):
        selected = [b for b in blocks if (b["mode"], b["fanout"]) == (mode, fanout)]
        decisions.append({"mode": mode, "fanout": fanout, "blocks": len(selected),
            "medianCpuReductionPercent": statistics.median(b["cpuReductionPercent"] for b in selected),
            "medianPssReductionPercent": statistics.median(b["pssReductionPercent"] for b in selected),
            "cpuThresholdBlocks": sum(b["cpuReductionPercent"] >= 15 for b in selected),
            "pssThresholdBlocks": sum(b["pssReductionPercent"] >= 20 for b in selected),
            "cpuRegressionsOverFivePercent": sum(b["cpuReductionPercent"] < -5 for b in selected)})
    raw = json.dumps({"inputs": json.loads((args.root / "inputs.json").read_text()), "cases": values}, sort_keys=True, separators=(",", ":")).encode()
    packed = gzip.compress(raw, mtime=0)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "matrix.json.gz").write_bytes(packed)
    summary = {"format": "mesh-plus.study-carrier-control.v1", "cases": len(values), "matchedBlocks": len(blocks),
        "gzipSha256": hashlib.sha256(packed).hexdigest(), "rawSha256": hashlib.sha256(raw).hexdigest(),
        "summaryToolSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "measurementInputSha256": hashlib.sha256((args.root / "inputs.json").read_bytes()).hexdigest(),
        "decisions": decisions, "blocks": blocks,
        "limits": ["synthetic 32-row loopback work; separate actual-native correctness gates",
            "identical shared publisher topology; generic Reader provenance label is synthetic",
            "reader-driver includes control, validation, accounting RPC and consumer work",
            "fixture-source CPU separate, sampler CPU separately visible, 10ms own-tick quantization",
            "sampled PSS has no transient-peak guarantee; background load uncontrolled",
            "logical JSON bytes and experimental pre-TLS framing counters are not physical wire capture",
            "no production TCP selection, binary/compact capability, real network or suspend acceptance",
            "no active Agent imports, owner edits or managed deployment changes"]}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"cases": len(values), "matchedBlocks": len(blocks), "decisions": decisions}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-cases", type=int, required=True)
    run(parser.parse_args())
