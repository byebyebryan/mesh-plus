"""Seal additive lifecycle evidence without changing the original checkpoint."""

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observer-repo", type=Path, required=True)
    parser.add_argument("--coordinator-repo", type=Path, required=True)
    parser.add_argument("--prefix", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("controller_seal", here / "seal_checkpoint.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    checkpoint = json.loads((here / "checkpoint.json").read_text())
    for name, value in checkpoint["artifacts"].items():
        assert prior.pin((repo / name).read_bytes()) == value
    source = json.loads((here / "results/qualification.json").read_text())
    verified = dict(mesh=prior.verify_blobs(repo, prior.RUNTIME, source["meshInputs"]),
                    observer=prior.verify_blobs(args.observer_repo, prior.OWNER, source["observerInputs"]),
                    protected=prior.verify_blobs(repo, prior.RUNTIME, source["protectedMeshInputs"]))
    for name, expected in {**source["meshInputs"], **source["protectedMeshInputs"]}.items():
        assert prior.pin((repo / name).read_bytes()) == expected
    result_dir = here / "lifecycle"
    result_dir.mkdir(exist_ok=False)
    reports = []
    for version in ("314", "311"):
        for suffix in ("json", "log"):
            shutil.copyfile(str(args.prefix) + "-" + version + "." + suffix, result_dir / (version + "." + suffix))
        result = json.loads((result_dir / (version + ".json")).read_text())
        assert (result["testsRun"], result["failures"], result["errors"], result["skips"], len(result["cases"])) == (2, 0, 0, 0, 20)
        for name, expected in result["loadedInputs"].items():
            side, path = name.split("/", 1)
            assert source["meshInputs" if side == "mesh" else "observerInputs"][path]["sha256"] == expected
        for case in result["cases"]:
            if "physicalInventory" in case:
                assert case["physicalInventory"]["afterUnwind"]["buffers"] == 0
                for phase, inventory in case["physicalInventory"].items():
                    if phase != "afterUnwind":
                        assert (inventory["buffers"], inventory["consuming"], inventory["encodedBytes"]) == (5, 5, case["heldNativeBytes"])
        reports.append(result)
    assert reports[0]["cases"] == reports[1]["cases"]
    assert reports[0]["loadedInputs"] == reports[1]["loadedInputs"]
    root_commit = subprocess.check_output(["rtk", "proxy", "git", "-C", str(args.coordinator_repo), "rev-parse", "96e3927"]).decode().strip()
    root_path = "projects/agent-dashboard/docs/delta-sync-relay-addendum.md"
    root_pin = prior.pin(prior.git_bytes(args.coordinator_repo, root_commit, root_path))
    names = ["verify_controller_lifecycle.py", "seal_lifecycle.py", "lifecycle.md"]
    artifacts = {str((here / name).relative_to(repo)): prior.pin((here / name).read_bytes()) for name in names}
    artifacts.update({str(path.relative_to(repo)): prior.pin(path.read_bytes()) for path in sorted(result_dir.iterdir())})
    output = dict(
        status="bounded additive actual-source lifecycle evidence; no runtime or producer acceptance",
        runtime=prior.RUNTIME, observer=prior.OWNER, priorEvidence="f667588acc9e41010ce30829bf7fb6b46e6f2b6b",
        priorCheckpoint=prior.pin((here / "checkpoint.json").read_bytes()), priorArtifactsUnchanged=len(checkpoint["artifacts"]),
        meshInputs=source["meshInputs"], observerInputs=source["observerInputs"], protectedInputs=source["protectedMeshInputs"],
        gitBlobFilesVerified=verified, artifacts=artifacts,
        coordinatorContractClosure=dict(commit=root_commit, path=root_path, **root_pin),
        results=dict(methodsPerPython=2, scenariosPerPython=20, pythonVersions=[r["python"] for r in reports],
                     loadedPinsPerPython=len(reports[0]["loadedInputs"]), scalarCasesAndLoadedPinsEqual=True,
                     finalCounters="Reader6 / relay5 zero; native owner to configured base; assertions enabled"),
        scope="Actual native Runtime with synthetic data/collect=False, expanded+compact source/codec, minted IPC controller/relay, independent Reader baseline/head, watch/end/expiry/head/stop, 4tx+completion held pins, wire cancel/repeated outer cancel/source close/partial write failure, sibling survival.",
        privateInstrumentation=reports[0]["exclusions"],
        earlierGates="Original 383 canonical /64 focused /24 composition retained at f667588, not rerun or relabelled.",
        changes="Evidence only; runtime/tests/contracts/scripts/pyproject and all original protected inputs unchanged; no IDs/artifacts/install/selection/rollout.",
    )
    (here / "lifecycle.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(gitBlobFilesVerified=verified, loadedPins=len(reports[0]["loadedInputs"]),
                         artifacts=len(artifacts), receipt=prior.pin((here / "lifecycle.json").read_bytes()))))


if __name__ == "__main__":
    main()
