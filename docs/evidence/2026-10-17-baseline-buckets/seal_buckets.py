"""Seal compact baseline bucket lifetime and unchanged-cap qualification."""

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
    parser.add_argument("--trace-logs", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("bucket_qualification", here / "qualify_buckets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    helper = module.helper_module()
    source = args.results.resolve()
    report = json.loads((source / "qualification.json").read_text())
    assert report["meshRuntime"] == module.MESH and report["observerRuntime"] == module.OBSERVER
    assert report["runner"] == helper.pin(here / "qualify_buckets.py")
    assert report["gitVerified"] == dict(mesh=262, observer=212, protected=8, before=262)
    assert report["priorArtifactCounts"] == dict(field=52, trace=16)
    for roles in report["focused"].values():
        assert sum(value["methods"] for value in roles.values()) == 140
        for value in roles.values():
            assert value["failures"] == value["errors"] == value["skipped"] == 0 and value["gcDisabled"]
    for value in report["before"].values():
        assert value["methods"] == 1 and value["failures"] == 2 and value["errors"] == value["skipped"] == 0
    assert len(report["capacity"]) == 12
    for value in report["capacity"].values():
        assert value["finalCounters"] == [0] * 6 and value["gcDisabled"]
        if value["failure"] is not None:
            assert value["rows"] == 2000 and value["failure"]["code"] == "sync_decoded_capacity"
            assert value["failure"]["stage"] == "baseline-admit"
        else:
            assert value["outcome"] == "baseline-and-two-generations-confirmed"
    for name, expected in report["artifacts"].items():
        assert helper.pin(source / name) == expected, name
    supplemental = {}
    trace_path = "docs/evidence/2026-10-17-field-reservation/trace_refusal.py"
    for version in ("314", "311"):
        trace = json.loads((source / ("trace-" + version + ".json")).read_text())
        storage = json.loads((source / ("storage-" + version + ".json")).read_text())
        for value in (trace, storage):
            assert value["finalCounters"] == [0] * 6 and value["gcDisabled"]
        for name, digest in trace["loadedInputs"].items():
            role, path = name.split("/", 1)
            inputs = report["inputs"][role] | report["extraMeshInputs"] if role == "mesh" else report["inputs"][role]
            assert inputs[path]["sha256"] == digest, name
        for name, digest in storage["loadedInputs"].items():
            assert report["inputs"]["mesh"][name]["sha256"] == digest, name
        private = trace["privateReservationTrace"]
        assert private["script"] == helper.pin(repo / trace_path)
        assert private["reserveFailureCount"] == 1 and len(private["tail"]) == 1
        event = private["tail"][0]
        assert event["amount"] == 256 and event["escapedBoundaries"] == ["_field_patch", "_patch", "_finish"]
        assert any(frame["function"] == ("_branch" if version == "314" else "_leaf") and
                   frame["file"] == "src/mesh_plus/sync/_packed_nodes.py" for frame in event["stack"])
        assert trace["heapPeak"] == report["capacity"]["2000-packed-" + version]["heapPeak"]
        assert len(storage["checkpoints"]) == 10
        assert all(row["metadataBound"] <= row["metadataCredit"] for row in storage["checkpoints"])
        supplemental[version] = dict(reservationFailure=event, storageCheckpoints=storage["checkpoints"])
    for name, expected in report["inputs"]["mesh"].items():
        assert helper.pin(repo / name) == expected, name
    canonical = args.canonical.read_text()
    assert "Ran 411 tests" in canonical and '"skipped": []' in canonical and "All checks passed!" in canonical
    results = here / "results"
    results.mkdir(exist_ok=False)
    for path in source.iterdir():
        if path.is_file():
            shutil.copyfile(path, results / path.name)
    shutil.copyfile(args.canonical, results / "canonical.log")
    shutil.copyfile(args.driver_log, results / "driver.log")
    for version in ("314", "311"):
        shutil.copyfile(args.trace_logs / ("trace-" + version + ".log"), results / ("trace-" + version + ".log"))
    paths = sorted(path for path in results.iterdir() if path.is_file())
    paths += [here / name for name in ("README.md", "qualify_buckets.py", "seal_buckets.py", "check_storage.py")]
    receipt = dict(
        meshRuntime=module.MESH, beforeRuntime=module.BEFORE, observerRuntime=module.OBSERVER,
        observerEvidence=module.OBSERVER_EVIDENCE, gitVerified=report["gitVerified"],
        inputs="results/qualification.json", artifacts={str(path.relative_to(repo)): helper.pin(path) for path in paths},
        upstream=report["upstream"], priorArtifactCounts=report["priorArtifactCounts"],
        supplemental=supplemental, traceScript=helper.pin(repo / trace_path),
        gates=dict(canonicalTests=411, meshFocusedPerPython=76, observerFocusedPerPython=64,
                   newMeshMethods=4, gcDisabled=True, skipped=0, beforeMethods=1, beforeExpectedStorageAssertions=2,
                   intakeScreens=12, smallSuccesses=8, largeRefusals=4, metadataCheckpointsPerPython=10,
                   reservationTraceReplays=2, cpuOrPhysicalRssAcceptance=False),
        status="Private compact baseline seen/bucket ownership; all four 2k baselines still refuse",
        exclusions=report["exclusions"],
        rawLogWhitespace="Original unittest before-subtest log lines retain trailing spaces; source/scripts/Markdown/JSON checks exclude raw logs",
    )
    output = here / "receipt.json"
    assert not output.exists()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=helper.pin(output), artifacts=len(receipt["artifacts"]), verified=report["gitVerified"])))


if __name__ == "__main__":
    main()
