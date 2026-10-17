"""Seal idle-frame correction evidence without changing earlier checkpoints."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location("controller_prior_seal", here / "seal_checkpoint.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    report = json.loads((args.results / "qualification.json").read_text())
    assert report["runtime"] == "d013d2afd14c3d6fa03a3fe377b62aff3ee5944b"
    assert report["before"] == "14990c789f853441b51af81ea0919facf0aff320"
    old = {}
    for name in ("checkpoint.json", "lifecycle.json", "copy-close.json"):
        old.update(json.loads((here / name).read_text())["artifacts"])
    for name, expected in old.items():
        assert prior.pin((repo / name).read_bytes()) == expected, name
    for name, expected in report["outputs"].items():
        assert prior.pin((args.results / name).read_bytes()) == expected, name
    for name, expected in report["runners"].items():
        assert prior.pin((here / name).read_bytes()) == expected, name
    verified = dict(
        afterMesh=prior.verify_blobs(repo, report["runtime"], report["meshInputs"]),
        beforeMesh=prior.verify_blobs(repo, report["before"], report["beforeInputs"]),
        observer=prior.verify_blobs(args.observer_repo, report["observer"], report["observerInputs"]),
        protected=prior.verify_blobs(repo, report["runtime"], report["protectedInputs"]),
    )
    for name, expected in {**report["meshInputs"], **report["protectedInputs"]}.items():
        assert prior.pin((repo / name).read_bytes()) == expected, name
    destination = here / "idle-retirement"
    shutil.copytree(args.results, destination)
    paths = list(destination.iterdir()) + [here / name for name in (
        "idle-retirement.md", "qualify_idle_retirement.py", "seal_idle_retirement.py",
        "probe_idle_frame_retirement_original.py.txt")]
    artifacts = {str(path.relative_to(repo)): prior.pin(path.read_bytes()) for path in sorted(paths)}
    receipt = dict(
        status="idle-frame correction implemented; immutable bounded replays pass; independent review pending",
        request="RLCD e-cde6b92d adjacent idle-frame retirement regression",
        runtime=report["runtime"], before=report["before"], observer=report["observer"],
        sourceInputs="idle-retirement/qualification.json", gitBlobFilesVerified=verified,
        artifacts=artifacts, priorArtifactPinsUnchanged=len(old),
        checks=dict(canonical314=387, focusedPerPython=68, basicScenariosPerPython=24,
                    lifecycleScenariosPerPython=20, beforeNamedTests=1, beforeFailedChecks=2,
                    idleProbe="unchanged051e31f1: before callback TypeError/132952 held; after no callback errors/final5zero/sibling live",
                    originalCopyProbe="unchangedb33788f8: original copy pins/revocation/close joins remain correct on both sources/Pythons"),
        compatibility="No API/wire/role/encoding/source/schema/LOCK/version/cap/deadline change; two frames, one queued retirement per frame, direct owning idle retirement and empty-frame storage invariant; active copies remain pinned.",
        diagnostic="One new method against prior runtime fails both callback assertion and teardown credit assertion; two checks on the same retained credit, not two methods.",
        exclusions=report["exclusions"],
    )
    output = here / "idle-retirement.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(verified=verified, artifacts=len(artifacts), priorArtifactPinsUnchanged=len(old),
                         receipt=prior.pin(output.read_bytes()))))


if __name__ == "__main__":
    main()
