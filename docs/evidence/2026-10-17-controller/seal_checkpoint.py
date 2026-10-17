"""Bind captured controller results to exact Git bytes; copies only own evidence."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

RUNTIME = "a482abbd463d23ebf66f23c60e4e95a521c19cc6"
INITIAL = "828cf0c759d36cc8aa939c513ac6c156862e3526"
OWNER = "e3441d017b94ee27f4dfccb5f1f3f30612435adf"
AGREEMENT = "d6364d1c3441b07436ca1e32789994aa2448be85"
ROOT_RECORD = "92b97d825cc2c1f8c3bbd1ad17b046e328e3eec9"


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def git_bytes(repo, revision, path):
    return subprocess.check_output(["rtk", "proxy", "git", "-C", str(repo), "show", revision + ":" + path])


def verify_blobs(repo, revision, expected):
    query = "".join(revision + ":" + name + "\n" for name in expected).encode()
    result = subprocess.run(["rtk", "proxy", "git", "-C", str(repo), "cat-file", "--batch"],
                            input=query, stdout=subprocess.PIPE, check=True)
    data, offset = result.stdout, 0
    for name, value in expected.items():
        end = data.index(b'\n', offset)
        fields = data[offset:end].split()
        assert len(fields) == 3 and fields[1] == b'blob', name
        size = int(fields[2])
        offset = end + 1
        assert pin(data[offset:offset + size]) == value, name
        offset += size
        assert data[offset:offset + 1] == b'\n'
        offset += 1
    assert offset == len(data)
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    parser.add_argument("--coordinator-repo", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    source = json.loads((args.results / "qualification.json").read_text())
    assert (source["meshRuntime"], source["beforeClockProvenanceRuntime"], source["observerSource"]) == (RUNTIME, INITIAL, OWNER)
    for name, expected in {**source["results"], **source["logs"]}.items():
        assert pin((args.results / name).read_bytes()) == expected, name
    for name, expected in source["artifacts"].items():
        assert pin((here / name).read_bytes()) == expected, name
    verified = {
        "mesh": verify_blobs(repo, RUNTIME, source["meshInputs"]),
        "initialMesh": verify_blobs(repo, INITIAL, source["beforeMeshInputs"]),
        "observer": verify_blobs(args.observer_repo, OWNER, source["observerInputs"]),
        "protectedMesh": verify_blobs(repo, RUNTIME, source["protectedMeshInputs"]),
    }
    for name, expected in {**source["meshInputs"], **source["protectedMeshInputs"]}.items():
        assert pin((repo / name).read_bytes()) == expected, name
    for version in ("314", "311"):
        focused = json.loads((args.results / ("focused-" + version + ".json")).read_text())
        assert (focused["testsRun"], focused["failures"], focused["errors"], focused["skips"]) == (64, 0, 0, 0)
        before = json.loads((args.results / ("before-provenance-" + version + ".json")).read_text())
        assert (before["testsRun"], before["expectedSubcaseFailures"], before["errors"], before["skips"]) == (2, 5, 0, 0)
    assert "\nRan 383 tests in " in (args.results / "canonical-314.log").read_text()
    agreement_pins = {}
    for name, expected in (
        ("docs/delta-sync-controller-agreement.md", "29bfb22e1259165148ac09e0f1f82e5d6ee8ac808e688422e7e76785f57bbd32"),
        ("docs/evidence/2026-10-16-delta-sync-source/controller-agreement.json", "341584bc02f2d79ee3ef1395d9a98d10d16f08bba97a1bf0d374dfa603373564"),
    ):
        value = pin(git_bytes(args.observer_repo, AGREEMENT, name))
        assert value["sha256"] == expected
        agreement_pins[name] = value
    mesh_agreements = {}
    for revision, name, expected in (
        ("33cb57c98ca3062f139ea1fd0c68b15bd5abd8d6", "docs/delta-sync-controller-proposal-r2.md", "89b24a9f3191bcded303d33c8b2ed973335b703811185abf1186848fbd562f48"),
        ("5d8cb484f8eba9fb6ca8dce9421410434cedf37d", "docs/delta-sync-controller-completion-r3.md", "42375477c46c097ede85b3bbbe5cda5f03a89823fdd7358e1078064a0c34e1c2"),
    ):
        value = pin(git_bytes(repo, revision, name))
        assert value["sha256"] == expected and pin((repo / name).read_bytes()) == value
        mesh_agreements[name] = {"commit": revision, **value}
    root_path = "projects/agent-dashboard/docs/delta-sync-relay-addendum.md"
    root_pin = pin(git_bytes(args.coordinator_repo, ROOT_RECORD, root_path))
    shutil.copytree(args.results, here / "results")
    diagnostics = here / "diagnostics"
    diagnostics.mkdir(exist_ok=False)
    for name in ("controller-observer-draft-314.json", "controller-observer-draft-314.log",
                 "controller-observer-draft-311.json", "controller-observer-draft-311.log",
                 "controller-observer-draft2-314.json", "controller-observer-draft2-314.log",
                 "controller-provenance-followup-314.log"):
        shutil.copyfile(repo / ".cache" / name, diagnostics / name)
    artifacts = {str(path.relative_to(repo)): pin(path.read_bytes()) for path in sorted(here.rglob("*")) if path.is_file()}
    for name in ("docs/delta-sync-controller-g1.md", "docs/handoff.md"):
        artifacts[name] = pin((repo / name).read_bytes())
    report = {
        "status": "bounded private controller source checkpoint; no G1/G2, route, producer or artifact acceptance",
        "runtime": RUNTIME, "initialController": INITIAL, "clockCorrection": "6daba40a7fdbe6846fb17ccdafb8ddbeaba03b7c",
        "observerFixture": OWNER, "gitBlobFilesVerified": verified,
        "observerAgreement": {"commit": AGREEMENT, "inputs": agreement_pins},
        "meshAgreements": mesh_agreements,
        "coordinatorAgreement": {"commit": ROOT_RECORD, "path": root_path, **root_pin},
        "qualification": "results/qualification.json", "artifacts": artifacts,
        "diagnosticProvenance": {
            "controller-observer-draft-*": "Draft runner passed tuple tag to canonical JSON; harness sync_json_type, not a producer failure. Both 24-error runs retained.",
            "controller-observer-draft2-*": "Draft runner tried .wire on Observer tuple; harness AttributeError. Retained, not production fail-before.",
            "controller-provenance-followup-314.log": "Intermediate clock fix: early guard cleanup and fixture clock restored before metadata check needed correction. Not a final qualification run.",
        },
        "checks": {"canonical314": "383 pass; lock/design/delivery/Ruff pass; no native/source/wheel flags",
                   "focusedPerPython": "64 methods, GC disabled, 0 failures/errors/skips",
                   "actualCompositionPerPython": "2 methods / 24 scenarios, exact native fragments, independent Reader full admission and 2 fresh proofs each",
                   "beforePerPython": "2 final overlay methods / 5 expected failures on initial 828cf0c, no errors/skips"},
        "exclusions": source["exclusions"],
    }
    (here / "checkpoint.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"verifiedGitBlobs": verified, "artifacts": len(artifacts), "checkpoint": pin((here / "checkpoint.json").read_bytes())}))


if __name__ == "__main__":
    main()
