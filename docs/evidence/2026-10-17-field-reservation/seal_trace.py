"""Bind call-site observations to unchanged accepted source inputs."""

import argparse
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

MESH = "13f27e25c46e1fd3da664975e964104a56fd6dbf"
OBSERVER = "b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f"


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("field_qualification", here.with_name(
        "2026-10-17-field-ref-sharing") / "qualify_fields.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    helper = module.helper_module()
    prior_path = repo / "docs/evidence/2026-10-17-field-ref-sharing/receipt.json"
    prior = json.loads(prior_path.read_text())
    for name, expected in prior["artifacts"].items():
        assert pin(repo / name) == expected, name
    q_path = repo / "docs/evidence/2026-10-17-field-ref-sharing/results/qualification.json"
    q = json.loads(q_path.read_text())
    assert q["meshRuntime"] == MESH and q["observerRuntime"] == OBSERVER
    verified = dict(mesh=helper.verify(repo, MESH, q["inputs"]["mesh"]),
                    observer=helper.verify(args.observer_repo, OBSERVER, q["inputs"]["observer"]),
                    protected=helper.verify(repo, MESH, q["protectedInputs"]))
    final = {}
    for version in ("314", "311"):
        value = json.loads((args.results / ("final-" + version + ".json")).read_text())
        assert value["gcDisabled"] and value["finalCounters"] == [0] * 6
        assert value["failure"]["stage"] == "baseline-admit" and value["failure"]["code"] == "sync_decoded_capacity"
        trace = value["privateReservationTrace"]
        assert trace["script"] == pin(here / "trace_refusal.py")
        assert trace["reserveFailureCount"] == 1 and len(trace["tail"]) == 1
        row = trace["tail"][0]
        assert row["ledger"]["decodedBytes"] + row["ledger"]["reservedBytes"] + row["amount"] > 67108864
        assert row["escapedBoundaries"][-2:] == ["_patch", "_finish"]
        assert (row["amount"] == 256 and row["escapedBoundaries"][0] == "_field_patch" if version == "314" else
                row["amount"] == 1024 and row["escapedBoundaries"][:2] == [
                    "apply_indexes:error_retired", "apply_indexes:replacement_raised"])
        for name, digest in value["loadedInputs"].items():
            role, relative = name.split("/", 1)
            inputs = q["inputs"][role] | q["extraMeshInputs"] if role == "mesh" else q["inputs"][role]
            assert inputs[relative]["sha256"] == digest, name
        previous = q["capacity"]["2000-packed-" + version]
        for name in ("heapPeak", "encodedPeakReservedBound", "outcome", "finalCounters"):
            assert value[name] == previous[name], (version, name)
        final[version] = dict(python=value["python"], heapPeak=value["heapPeak"], failure=row,
                              loadedInputs=len(value["loadedInputs"]), finalCounters=value["finalCounters"])
    results = here / "results"
    results.mkdir(exist_ok=False)
    for path in args.results.iterdir():
        if path.is_file():
            shutil.copyfile(path, results / path.name)
    bindings = dict(meshRuntime=MESH, observerRuntime=OBSERVER, inputs=q["inputs"],
                    protectedInputs=q["protectedInputs"], probe=q["extraMeshInputs"])
    (results / "source-bindings.json").write_text(json.dumps(bindings, indent=2, sort_keys=True) + "\n")
    paths = sorted(path for path in results.iterdir() if path.is_file())
    paths += [here / name for name in ("README.md", "trace_refusal.py", "seal_trace.py")]
    receipt = dict(meshRuntime=MESH, observerRuntime=OBSERVER, verified=verified,
                   artifacts={str(path.relative_to(repo)): pin(path) for path in paths},
                   previousReceipt=pin(prior_path), priorArtifactsUnchanged=len(prior["artifacts"]),
                   final=final, capacityOrCpuAcceptance=False, productionDiff=False,
                   exclusions="Two new bounded instrumented diagnostic replays only; earlier exploratory traces preserved. No unchanged functional/canonical/capacity suite rerun, allocation estimate/cap change, physical/RSS/timing/producer acceptance or sibling action.")
    output = here / "receipt.json"
    assert not output.exists()
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(receipt=pin(output), verified=verified, artifacts=len(receipt["artifacts"]))))


if __name__ == "__main__":
    main()
