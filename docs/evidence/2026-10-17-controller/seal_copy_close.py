"""Bind copy-close correction and original coordinator replay to Git bytes."""

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
    spec = importlib.util.spec_from_file_location("old_controller_seal", here / "seal_checkpoint.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    result = json.loads((args.results / "qualification.json").read_text())
    assert result["runtime"] == "14990c789f853441b51af81ea0919facf0aff320"
    old_checkpoint = json.loads((here / "checkpoint.json").read_text())
    old_lifecycle = json.loads((here / "lifecycle.json").read_text())
    for name, value in {**old_checkpoint["artifacts"], **old_lifecycle["artifacts"]}.items():
        assert prior.pin((repo / name).read_bytes()) == value, name
    for name, value in result["outputs"].items():
        assert prior.pin((args.results / name).read_bytes()) == value, name
    for name, value in result["runners"].items():
        assert prior.pin((here / name).read_bytes()) == value, name
    verified = dict(afterMesh=prior.verify_blobs(repo, result["runtime"], result["meshInputs"]),
                    beforeMesh=prior.verify_blobs(repo, result["before"], result["beforeInputs"]),
                    observer=prior.verify_blobs(args.observer_repo, result["observer"], result["observerInputs"]),
                    protected=prior.verify_blobs(repo, result["runtime"], result["protectedInputs"]))
    for name, value in {**result["meshInputs"], **result["protectedInputs"]}.items():
        assert prior.pin((repo / name).read_bytes()) == value, name
    shutil.copytree(args.results, here / "copy-close")
    diagnostic = here / "copy-close/test-cleanup-draft.log"
    shutil.copyfile(repo / ".cache/controller-copy-fix-new-tests-draft-314.log", diagnostic)
    paths = list((here / "copy-close").iterdir())
    paths += [here / name for name in ("copy-close.md", "qualify_copy_close.py", "seal_copy_close.py", "probe_header_close_original.py.txt")]
    artifacts = {str(path.relative_to(repo)): prior.pin(path.read_bytes()) for path in sorted(paths)}
    output = dict(status="copy-close correction implemented and bounded immutable replay passed; independent review pending",
                  request="RLCD m156", runtime=result["runtime"], before=result["before"], observer=result["observer"],
                  gitBlobFilesVerified=verified, artifacts=artifacts,
                  priorEvidence=dict(controller="f667588acc9e41010ce30829bf7fb6b46e6f2b6b",
                                     lifecycle="1e37541d868c439a48628d99830e314bd87af360",
                                     artifactPinsUnchanged=len({**old_checkpoint["artifacts"], **old_lifecycle["artifacts"]})),
                  sourceInputs="copy-close/qualification.json",
                  checks=dict(canonical314=386, focusedPerPython=67, basicScenariosPerPython=24,
                              lifecycleScenariosPerPython=20, namedBeforeFailuresPerPython=3,
                              rootProbe="unchanged b33788f8, before both gaps; after both retired and fully charged, sibling and final counters correct"),
                  compatibility="No public signature/wire/role/encoding/native or source API/schema/LOCK/version/cap/deadline change. One bounded active copy per frame; two slots include retired physical pins; local sync_control_copy_busy rejects before another copy.",
                  diagnostic="New test draft expected zero shared credit while sibling still open; fixture closes sibling explicitly. Not a production failure.",
                  exclusions=result["exclusions"])
    (here / "copy-close.json").write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(verified=verified, artifacts=len(artifacts), receipt=prior.pin((here / "copy-close.json").read_bytes()))))


if __name__ == "__main__":
    main()
