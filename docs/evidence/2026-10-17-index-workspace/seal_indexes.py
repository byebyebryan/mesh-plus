"""Seal compact index-workspace source evidence and preserve previous bytes."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("phase_qualification", here.with_name(
        "2026-10-17-normalization-phases") / "qualify_phases.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source = args.results.resolve()
    report = json.loads((source / "qualification.json").read_text())
    assert report["meshAfter"] == "231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc"
    assert len(report["screens"]) == 8
    for case in report["screens"]:
        if case["rows"] == 2000:
            assert case["failure"]["code"] == "sync_decoded_capacity"
            assert case["failure"]["stage"] == "baseline-admit"
        else:
            assert case["outcome"] == "baseline-and-two-generations-confirmed" and case["failure"] is None
    for name, expected in report["artifacts"].items():
        assert helper.pin(source / name) == expected, name
    for name, expected in report["runners"].items():
        assert helper.pin(repo / name) == expected, name
    profile = json.loads((source / "profile-packed2000-314.json").read_text())
    assert profile["failure"]["code"] == "sync_decoded_capacity" and profile["finalCounters"] == [0] * 6
    for name, digest in profile["loadedInputs"].items():
        side, path = name.split("/", 1)
        assert report["inputs"]["after" if side == "mesh" else side][path]["sha256"] == digest
    assert all(value == 0 for row in profile["privateScalarAllocationAudit"]["finalTypes"].values()
               for value in row.values())
    log = args.canonical.read_text()
    assert "Ran 403 tests" in log and '"skipped": []' in log and "All checks passed!" in log
    for name, expected in report["inputs"]["after"].items():
        assert helper.pin(repo / name) == expected, name
    results = here / "results"
    results.mkdir(exist_ok=False)
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, results / path.name)
    shutil.copyfile(args.canonical, results / "canonical-final.log")
    paths = sorted(path for path in results.iterdir() if path.is_file())
    paths += [here / name for name in ("README.md", "qualify_indexes.py", "seal_indexes.py")]
    artifacts = {str(path.relative_to(repo)): helper.pin(path) for path in paths}
    receipt = dict(
        meshRuntime=report["meshAfter"], beforeRuntime=report["meshBefore"], observerRuntime=report["observer"],
        gitVerified=report["gitVerified"], inputs="results/qualification.json", artifacts=artifacts,
        priorReceipt=report["priorReceipt"], priorArtifactPinsUnchanged=report["priorArtifactPinsUnchanged"],
        sourceGate=dict(canonicalTests=403, focusedMethodsPerPython=68, newMethods=6, skipped=0,
                        beforeNegativeMethodCount=1, beforeExpectedRejectionPhaseAssertionsPerPython=1,
                        pythonVersions=["3.14.8", "3.11.17"], nativeSourceWheelCpuGatesRun=False),
        capacity=dict(cases=8, smallConfirmed=4, largeRefused=4, finalSixCountersZero=True,
                      gcDisabled=True, privateScalarAuditCount=1, cpuClaim=False,
                      physicalHeapRssAcceptance=False, newObserverPrototypePaired=False),
        status="Private compact index-workspace source checkpoint; Observer84 still fails before new index phase at2000",
        exclusions=report["exclusions"],
    )
    output = here / "receipt.json"
    assert not output.exists()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=helper.pin(output), artifacts=len(artifacts), verified=report["gitVerified"])))


if __name__ == "__main__":
    main()
