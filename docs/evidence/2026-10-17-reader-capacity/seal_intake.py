"""Bind diagnostic capacity failures and allocation audit to immutable inputs."""

import argparse
import importlib.util
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    previous = here.parent / "2026-10-17-controller"
    spec = importlib.util.spec_from_file_location("controller_prior_seal", previous / "seal_checkpoint.py")
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    report = json.loads((args.results / "qualification.json").read_text())
    profile = json.loads(args.profile.read_text())
    assert report["meshRuntime"] == "d013d2afd14c3d6fa03a3fe377b62aff3ee5944b"
    assert report["observerRuntime"] == "84d284dab04b68ae0e9070335d017e85564f2ba9"
    assert len(report["outcomes"]) == 12
    for case in report["outcomes"]:
        if case["rows"] == 2000:
            assert case["outcome"] == "refused-or-failed"
            assert case["failure"] == dict(stage="baseline-admit", code="sync_decoded_capacity")
        else:
            assert case["outcome"] == "baseline-and-two-generations-confirmed" and case["failure"] is None
    for name, expected in report["artifacts"].items():
        assert old.pin((args.results / name).read_bytes()) == expected, name
    for name, expected in report["runners"].items():
        assert old.pin((here / name).read_bytes()) == expected, name
    assert profile["failure"]["stage"] == "baseline-admit"
    assert profile["failure"]["code"] == "sync_decoded_capacity"
    assert profile["finalCounters"] == [0] * 6 and profile["gcDisabled"]
    for name, digest in profile["loadedInputs"].items():
        side, path = name.split("/", 1)
        assert (report["meshInputs"] if side == "mesh" else report["observerInputs"])[path]["sha256"] == digest
    assert all(all(value == 0 for value in row.values())
               for row in profile["privateScalarAllocationAudit"]["finalTypes"].values())
    protected = json.loads((previous / "idle-retirement/qualification.json").read_text())["protectedInputs"]
    verified = dict(
        mesh=old.verify_blobs(repo, report["meshRuntime"], report["meshInputs"]),
        observer=old.verify_blobs(args.observer_repo, report["observerRuntime"], report["observerInputs"]),
        protected=old.verify_blobs(repo, report["meshRuntime"], protected),
    )
    prior = {}
    for name in ("checkpoint.json", "lifecycle.json", "copy-close.json", "idle-retirement.json"):
        prior.update(json.loads((previous / name).read_text())["artifacts"])
    for name, expected in prior.items():
        assert old.pin((repo / name).read_bytes()) == expected, name
    shutil.copytree(args.results, here / "results")
    shutil.copyfile(args.profile, here / "results/profile-charges-packed2000-314.json")
    diagnostics = here / "diagnostics"
    diagnostics.mkdir(exist_ok=False)
    for name in ("reader-intake-draft-100-default-314.json", "reader-intake-draft2-100-default-314.json",
                 "reader-intake-draft3-100-default-314.json"):
        shutil.copyfile(repo / ".cache" / name, diagnostics / name)
    paths = list((here / "results").iterdir()) + list(diagnostics.iterdir())
    paths += [here / name for name in ("README.md", "probe_reader_intake.py", "qualify_intake.py",
                                     "profile_intake.py", "seal_intake.py")]
    artifacts = {str(path.relative_to(repo)): old.pin(path.read_bytes()) for path in sorted(paths)}
    receipt = dict(
        status="Reader2000 capacity FAIL on default and private packed backends; diagnostic source evidence only",
        meshRuntime=report["meshRuntime"], observerRuntime=report["observerRuntime"],
        sourceInputs="results/qualification.json", gitInputsVerified=verified, artifacts=artifacts,
        priorArtifactPinsUnchanged=len(prior),
        screens=dict(total=12, smallSuccesses=8, largeCapacityRefusals=4,
                     pythonVersions=["3.14.8", "3.11.17"], finalSixCountersZero=True, gcDisabled=True,
                     baselineAndTwoGenerations=True, fullOnly=True, denseNineFields=False),
        audit=dict(python="3.14.8", rows=2000, backend="private packed", finalScalarCountsZero=True,
                   scope="private scalar type and cumulative stage-charge observation; no graph history or timing claim"),
        draftDiagnostics="Three raw draft reports retained separately; foreign clock context/stale worker receipt setup errors and small draft pass. Earlier harness bytes not frozen; no acceptance/replay claim.",
        sourceGate="No runtime changes; prior d013387/68/24/20 results stay bound to their original Observer e344 inputs, not these new capacity cases. New probe scripts Ruff checked; no native/source/wheel/matched CPU gate rerun.",
        profileCommand=[".venv/bin/python", "-B", "docs/evidence/2026-10-17-reader-capacity/profile_intake.py",
                        "--mesh", ".cache/controller-mesh-d013d2a", "--observer", ".cache/observer-row-reuse-84d284d",
                        "--output", ".cache/reader-intake-profile-charges-d013-84-packed2000-314.json"],
        exclusions=report["exclusions"],
    )
    output = here / "receipt.json"
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(verified=verified, artifacts=len(artifacts), priorPins=len(prior),
                         receipt=old.pin(output.read_bytes()))))


if __name__ == "__main__":
    main()
