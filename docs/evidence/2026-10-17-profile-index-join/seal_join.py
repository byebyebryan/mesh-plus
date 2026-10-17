"""Seal the immutable source join without rewriting earlier evidence."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--diagnostic-import", type=Path, required=True)
    parser.add_argument("--diagnostic-pins", type=Path, required=True)
    parser.add_argument("--driver-log", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("join_qualification", here / "qualify_join.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    helper = module.helper_module()
    source = args.results.resolve()
    report = json.loads((source / "qualification.json").read_text())
    assert report["meshRuntime"] == module.MESH and report["observerRuntime"] == module.OBSERVER
    assert report["runner"] == helper.pin(here / "qualify_join.py")
    assert report["gitVerified"] == dict(mesh=262, observer=212, protected=8)
    for roles in report["focused"].values():
        assert sum(value["methods"] for value in roles.values()) == 132
        for value in roles.values():
            assert value["failures"] == value["errors"] == value["skipped"] == 0
            assert value["gcDisabled"]
    assert len(report["capacity"]) == 12
    for value in report["capacity"].values():
        assert value["finalCounters"] == [0] * 6 and value["gcDisabled"]
        if value["rows"] == 2000:
            assert value["failure"]["code"] == "sync_decoded_capacity"
            assert value["failure"]["stage"] == "baseline-admit"
        else:
            assert value["failure"] is None and value["outcome"] == "baseline-and-two-generations-confirmed"
    for name, expected in report["artifacts"].items():
        assert helper.pin(source / name) == expected, name
    profile = json.loads((source / "profile-packed2000-314.json").read_text())
    assert profile["failure"]["code"] == "sync_decoded_capacity" and profile["finalCounters"] == [0] * 6
    audit = profile["privateScalarAllocationAudit"]
    assert all(value == 0 for row in audit["finalTypes"].values() for value in row.values())
    assert len(audit["failedRetains"]) == 1 and audit["failedRetains"][0]["rootType"] == "_Decoded"
    for name, digest in profile["loadedInputs"].items():
        side, path = name.split("/", 1)
        files = report["inputs"][side] | report["extraMeshInputs"] if side == "mesh" else report["inputs"][side]
        assert files[path]["sha256"] == digest, name
    for name, expected in report["inputs"]["mesh"].items():
        assert helper.pin(repo / name) == expected, name
    results = here / "results"
    results.mkdir(exist_ok=False)
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, results / path.name)
    shutil.copyfile(args.driver_log, results / "driver.log")
    diagnostics = here / "diagnostics"
    diagnostics.mkdir(exist_ok=False)
    for label, root in (("import", args.diagnostic_import), ("pins", args.diagnostic_pins)):
        target = diagnostics / label
        target.mkdir()
        for path in root.iterdir():
            if path.is_file():
                shutil.copyfile(path, target / path.name)
    paths = sorted(path for root in (results, diagnostics) for path in root.rglob("*") if path.is_file())
    paths += [here / name for name in ("README.md", "qualify_join.py", "seal_join.py")]
    artifacts = {str(path.relative_to(repo)): helper.pin(path) for path in paths}
    receipt = dict(
        meshRuntime=module.MESH, meshEvidence=module.MESH_EVIDENCE,
        observerRuntime=module.OBSERVER, observerEvidence=module.OBSERVER_EVIDENCE,
        gitVerified=report["gitVerified"], inputs="results/qualification.json",
        artifacts=artifacts, upstream=report["upstream"],
        privateAuditScripts={name: helper.pin(repo / name) for name in (
            "docs/evidence/2026-10-17-reader-capacity/profile_intake.py",
            "docs/evidence/2026-10-17-reader-capacity/probe_reader_intake.py")},
        focused=dict(methodsPerPython=132, observer=64, mesh=68, pythonVersions=["3.14.8", "3.11.17"],
                     gcDisabled=True, failures=0, errors=0, skipped=0, canonicalRerun=False),
        capacity=dict(cases=12, smallConfirmed=8, largeRefused=4, finalSixCountersZero=True,
                      gcDisabled=True, privateScalarAuditCount=1, cpuClaim=False, physicalHeapRssAcceptance=False),
        status="Compatible immutable source pair; all four 2k baseline admissions still refuse unchanged capacity",
        exclusions=report["exclusions"],
        diagnostics="Two isolated driver setup failures retained; excluded from final qualification",
    )
    output = here / "receipt.json"
    assert not output.exists()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=helper.pin(output), artifacts=len(artifacts), verified=report["gitVerified"])))


if __name__ == "__main__":
    main()
