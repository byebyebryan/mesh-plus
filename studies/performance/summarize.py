"""Publish metadata-only paired window evidence without inventing comparability."""

import argparse
import gzip
import hashlib
import json
import statistics
from pathlib import Path

TRIAL = {"reader-consumer", "publisher", "ssh-client", "ssh-server-session"}


def traffic(window):
    a, b = window["readerBefore"]["mark"], window["readerAfter"]["mark"]
    return {"frames": b["receivedFrames"] - a["receivedFrames"],
            "bytes": b["receivedBytes"] - a["receivedBytes"],
            "proofs": b["operations"]["proofRequests"] - a["operations"]["proofRequests"]}


def pss(window):
    roles = [r for endpoint in window["resources"].values() for r in endpoint["roles"] if r["role"] in TRIAL]
    return sum(r["pssMeanKiB"] or 0 for r in roles) / 1024


def run(args):
    windows, blocks = [], []
    for pair in ("baseline-carrier", "optimization", "candidate-carrier"):
        source = args.root / ("matrix-" + pair)
        cases = [json.loads(p.read_text()) for p in sorted(source.glob("*.json")) if p.name != "index.json"]
        for case in cases:
            case["pair"] = pair
            case["timedTraffic"] = traffic(case)
            case["accessiblePssMiB"] = pss(case)
        windows.extend(cases)
        groups = sorted({(case["host"], case["domain"], case["block"]) for case in cases})
        for host, domain, block in groups:
            rows = sorted([c for c in cases if (c["host"], c["domain"], c["block"]) == (host, domain, block)], key=lambda c: c["position"])
            if len(rows) != 4:
                raise ValueError("incomplete_ABBA_block")
            if [row["position"] for row in rows] != [0, 1, 2, 3]:
                raise ValueError("invalid_ABBA_positions")
            identities = [(row["carrier"], row["variant"]) for row in rows]
            if identities[0] != identities[3] or identities[1] != identities[2] or identities[0] == identities[1]:
                raise ValueError("invalid_ABBA_variants")
            exclusions = [reason for row in rows for reason in row["exclusions"]]
            if any(row["status"] != "accepted_window" for row in rows):
                exclusions.append("window_guard_not_accepted")
            if len({key for row in rows for key in row["reader"]["inventories"]}) != 1:
                exclusions.append("cross_window_inventory_changed")
            for field in ("frames", "bytes", "proofs"):
                counts = [row["timedTraffic"][field] for row in rows]
                if max(counts) > min(counts) * 1.05:
                    exclusions.append("timed_" + field + "_not_matched_within_5pct")
            # This is a noise warning, not a post-hoc acceptance threshold.
            nuisance = {endpoint: [row["resources"][endpoint]["unattributedCpuPercent"] for row in rows]
                        for endpoint in ("readerHost", "publisherHost")}
            warnings = ["ordinary_native_contents_not_frozen", "sampler_transport_overhead_not_fully_attributed",
                        "root_SSH_session_PSS_unavailable"]
            if any(max(values) - min(values) > 10 for values in nuisance.values()):
                warnings.append("background_CPU_varied_more_than_10_points")
            a, b = [rows[index] for index in (0, 3)], [rows[index] for index in (1, 2)]
            a_cpu = statistics.mean(row["attributableCpuPercent"] for row in a)
            b_cpu = statistics.mean(row["attributableCpuPercent"] for row in b)
            a_pss = statistics.mean(row["accessiblePssMiB"] for row in a)
            b_pss = statistics.mean(row["accessiblePssMiB"] for row in b)
            blocks.append({"pair": pair, "host": host, "domain": domain, "block": block,
                "cases": [row["case"] for row in rows], "A": {"cpuPercent": a_cpu, "accessiblePssMiB": a_pss},
                "B": {"cpuPercent": b_cpu, "accessiblePssMiB": b_pss},
                "cpuReductionPercent": 100 * (1 - b_cpu / a_cpu), "accessiblePssReductionPercent": 100 * (1 - b_pss / a_pss),
                "exclusions": sorted(set(exclusions)), "warnings": warnings,
                "status": "descriptive_only" if not exclusions else "excluded_comparison",
                "timedTraffic": [row["timedTraffic"] for row in rows], "unattributedCpuPercent": nuisance})
    raw = json.dumps({"windows": windows}, separators=(",", ":"), sort_keys=True).encode()
    packed = gzip.compress(raw, mtime=0)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "matched-windows.json.gz").write_bytes(packed)
    summary = {"format": "mesh-plus.performance-windows.v1", "windows": len(windows),
        "windowGuards": {status: sum(w["status"] == status for w in windows) for status in ("accepted_window", "excluded_window", "failed_window")},
        "rawSha256": hashlib.sha256(raw).hexdigest(), "gzipSha256": hashlib.sha256(packed).hexdigest(),
        "blocks": blocks, "scope": "two-host cached endpoint watch; ordinary native activity; descriptive role totals, not controlled trace causality",
        "exclusions": ["complete Observer fleet budget scope", "physical suspend", "candidate promotion", "deployment selection"]}
    (args.output / "matched-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"windows": len(windows), "windowGuards": summary["windowGuards"], "compressedBytes": len(packed),
                      "excludedComparisons": sum(bool(b["exclusions"]) for b in blocks)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
