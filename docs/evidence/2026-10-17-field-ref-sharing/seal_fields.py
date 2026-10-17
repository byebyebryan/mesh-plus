"""Seal field-reference topology and unchanged-cap intake qualification."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--canonical", type=Path, required=True)
    parser.add_argument("--driver-log", type=Path, required=True)
    parser.add_argument("--initial-before", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("field_qualification", here / "qualify_fields.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    helper = module.helper_module()
    source = args.results.resolve()
    report = json.loads((source / "qualification.json").read_text())
    assert report["meshRuntime"] == module.MESH and report["observerRuntime"] == module.OBSERVER
    assert report["runner"] == helper.pin(here / "qualify_fields.py")
    assert report["gitVerified"] == dict(mesh=262, observer=212, protected=8, before=262)
    for roles in report["focused"].values():
        assert sum(value["methods"] for value in roles.values()) == 136
        for value in roles.values():
            assert value["failures"] == value["errors"] == value["skipped"] == 0 and value["gcDisabled"]
    for value in report["before"].values():
        assert value["methods"] == 1 and value["failures"] == 2 and value["errors"] == value["skipped"] == 0
    assert len(report["capacity"]) == 12
    for value in report["capacity"].values():
        assert value["finalCounters"] == [0] * 6 and value["gcDisabled"]
        assert value["heapPeak"] <= 67108864 and value["encodedPeakReservedBound"] <= 33554432
        if value["failure"] is not None:
            assert value["rows"] == 2000 and value["failure"]["code"] == "sync_decoded_capacity"
            assert value["failure"]["stage"] == "baseline-admit"
        else:
            assert value["outcome"] == "baseline-and-two-generations-confirmed"
    for name, expected in report["artifacts"].items():
        assert helper.pin(source / name) == expected, name
    profile = json.loads((source / "profile-packed2000-314.json").read_text())
    assert profile["finalCounters"] == [0] * 6
    audit = profile["privateScalarAllocationAudit"]
    assert all(value == 0 for row in audit["finalTypes"].values() for value in row.values())
    for name, digest in profile["loadedInputs"].items():
        side, path = name.split("/", 1)
        files = report["inputs"][side] | report["extraMeshInputs"] if side == "mesh" else report["inputs"][side]
        assert files[path]["sha256"] == digest, name
    for name, expected in report["inputs"]["mesh"].items():
        assert helper.pin(repo / name) == expected, name
    canonical = args.canonical.read_text()
    assert "Ran 407 tests" in canonical and '"skipped": []' in canonical and "All checks passed!" in canonical
    results, diagnostics = here / "results", here / "diagnostics"
    results.mkdir(exist_ok=False)
    diagnostics.mkdir(exist_ok=False)
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, results / path.name)
    shutil.copyfile(args.canonical, results / "canonical.log")
    shutil.copyfile(args.driver_log, results / "driver.log")
    shutil.copyfile(args.initial_before / "before-sharing-314.log", diagnostics / "initial-before-314.log")
    shutil.copyfile(args.initial_before / "before-231a631/tests/test_sync_patch_workspace.py",
                    diagnostics / "initial-test.py.txt")
    paths = sorted(path for root in (results, diagnostics) for path in root.rglob("*") if path.is_file())
    paths += [here / name for name in ("README.md", "qualify_fields.py", "seal_fields.py")]
    artifacts = {str(path.relative_to(repo)): helper.pin(path) for path in paths}
    receipt = dict(
        meshRuntime=module.MESH, beforeRuntime=module.BEFORE, observerRuntime=module.OBSERVER,
        observerEvidence=module.OBSERVER_EVIDENCE, gitVerified=report["gitVerified"],
        inputs="results/qualification.json", artifacts=artifacts, upstream=report["upstream"],
        privateAuditScripts={name: helper.pin(repo / name) for name in (
            "docs/evidence/2026-10-17-reader-capacity/profile_intake.py",
            "docs/evidence/2026-10-17-reader-capacity/probe_reader_intake.py")},
        focused=dict(methodsPerPython=136, observer=64, mesh=72, newMeshMethods=4, canonicalTests=407,
                     beforeMethodsPerPython=1, beforeExpectedTopologyFailures=2,
                     gcDisabled=True, failures=0, errors=0, skipped=0),
        capacity=dict(cases=12, confirmed=sum(value["failure"] is None for value in report["capacity"].values()),
                      refused=sum(value["failure"] is not None for value in report["capacity"].values()),
                      finalSixCountersZero=True, gcDisabled=True, privateScalarAuditCount=1,
                      cpuClaim=False, physicalHeapRssAcceptance=False),
        status="Private exact field-reference ownership checkpoint; no producer acceptance",
        exclusions=report["exclusions"],
        diagnostics="Initial fixture OrderedMap/proof-context setup and assertion-inside-admission overlay excluded; final before report has two topology assertions only",
    )
    output = here / "receipt.json"
    assert not output.exists()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=helper.pin(output), artifacts=len(artifacts), verified=report["gitVerified"])))


if __name__ == "__main__":
    main()
