"""Summarize the predeclared serial idle study; incomplete studies cannot pass."""

import argparse
import json
import statistics
from pathlib import Path


def record(root, name, seconds):
    value = json.loads((root / name / "result.json").read_text())
    if value["state"] != "passed" or not value["cleanup"] or value["seconds"] != seconds:
        raise ValueError("incomplete owned fixture: " + name)
    if value["profiled"] or value["counters"]:
        raise ValueError("instrumented CPU sample: " + name)
    if any(abs(samples - seconds / 2) > 1 for samples in value["acceptedSamples"].values()):
        raise ValueError("native sample cadence differs: " + name)
    return value


def group(root, prefix, seconds):
    records = []
    for index, variant in enumerate(("before", "candidate", "candidate", "before"), 1):
        name = f"{prefix}-{index}-{variant}"
        value = record(root, name, seconds)
        active = prefix == "qualified-active-two"
        if active:
            if not value.get("controlledChanges") or value["nativeFactsUnchanged"]:
                raise ValueError("controlled updates were not exercised: " + name)
        elif not value["nativeFactsUnchanged"]:
            raise ValueError("idle facts changed: " + name)
        records.append({"run": name, "variant": variant, "value": value})
    result = {}
    for role in records[0]["value"]["cpu"]:
        variants = {}
        for variant in ("before", "candidate"):
            values = [r["value"]["cpu"][role]["selfCpuPercent"] for r in records
                      if r["variant"] == variant]
            children = [r["value"]["cpu"][role]["reapedChildCpuPercent"] for r in records
                        if r["variant"] == variant]
            variants[variant] = {"mean": statistics.mean(values), "min": min(values),
                                 "max": max(values), "range": max(values) - min(values),
                                 "meanReapedChildCpu": statistics.mean(children)}
        before, after = variants["before"]["mean"], variants["candidate"]["mean"]
        result[role] = {**variants, "savedPercentagePoints": before - after,
                        "relativeReductionPercent": 100 * (before - after) / before if before else None}
    return {"components": result,
            "acceptedSamples": {r["run"]: r["value"]["acceptedSamples"] for r in records},
            "controlledChanges": {r["run"]: r["value"].get("controlledChanges", 0) for r in records},
            "harnesses": sorted({r["value"]["harnessSha256"] for r in records})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (args.input / "all-complete.json").is_file() or args.output.exists():
        parser.error("complete study and new output required")
    groups = {"emptyBlock1": group(args.input, "qualified-empty-1", 300),
              "emptyBlock2": group(args.input, "qualified-empty-2", 300),
              "twoSessions": group(args.input, "qualified-two", 120),
              "activeTwoSessions": group(args.input, "qualified-active-two", 120)}
    counters = {}
    for variant in ("before", "candidate"):
        directory = args.input / ("final-counts-" + variant)
        paths = list(directory.glob("counts-fleet-*.json"))
        if len(paths) != 1:
            raise ValueError("one Fleet counter record required")
        counters[variant] = json.loads(paths[0].read_text())
        metrics = counters[variant]["readerMetrics"]
        if metrics["activeConnections"] or metrics["cleanupFailures"] or metrics["connectionFailures"]:
            raise ValueError("Reader did not retire cleanly")
    result = {"scope": "controlled same-host two-owner actual localhost SSH; CPU percent of one core",
              "limits": ["not whole-host or whole-fleet CPU", "SSH daemon helpers and tmux servers excluded",
                         "uncontrolled host power/frequency and desktop activity", "no live deployment acceptance"],
              "groups": groups, "counters": counters,
              "gate": "manual review of block savings/spread, required work, active regression and resource limits; "
                      "20 percent Fleet reduction is the initial target, not an automatic promotion"}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: value["components"]["fleet-local"] for key, value in groups.items()}, indent=2))


if __name__ == "__main__":
    main()
