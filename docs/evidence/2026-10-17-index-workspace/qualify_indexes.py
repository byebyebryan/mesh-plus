"""Immutable compact index scratch checks; pinned old-Observer intake only."""

import argparse
import fcntl
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

BEFORE = "4301339515e84f2edb63c88a886380bcde56c621"
OBSERVER = "84d284dab04b68ae0e9070335d017e85564f2ba9"
PY311 = "/home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after", required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    previous = here.with_name("2026-10-17-group-ownership")
    shared = here.with_name("2026-10-17-reader-capacity")
    spec = importlib.util.spec_from_file_location("phase_qualification", here.with_name(
        "2026-10-17-normalization-phases") / "qualify_phases.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    pin, inventory, verify = helper.pin, helper.inventory, helper.verify
    out = args.output.resolve()
    out.mkdir(exist_ok=False)
    before, after = out / "before", out / "after"
    helper.export(repo, BEFORE, before)
    helper.export(repo, args.after, after)
    observer = args.observer.resolve()
    selected = ("src", "tests", "scripts", "contracts")
    inputs = dict(before=inventory(before, selected), after=inventory(after, selected),
                  observer=inventory(observer, ("agent_observer", "tests")))
    verified = dict(before=verify(repo, BEFORE, inputs["before"]), after=verify(repo, args.after, inputs["after"]),
                    observer=verify(args.observer_repo, OBSERVER, inputs["observer"]))
    prior = json.loads((previous / "receipt.json").read_text())
    protected = json.loads((previous / "results/qualification.json").read_text())["protectedInputs"]
    verified["protected"] = verify(repo, args.after, protected)
    assert verify(repo, BEFORE, protected) == verified["protected"]
    for name, expected in prior["artifacts"].items():
        assert pin(repo / name) == expected, name
    overlay = before / "tests/test_sync_patch_workspace.py"
    overlay.write_bytes((after / "tests/test_sync_patch_workspace.py").read_bytes())
    overlay_pin = pin(overlay)
    probe, audit = shared / "probe_reader_intake.py", shared / "profile_intake.py"
    runners = {str(path.relative_to(repo)): pin(path) for path in (Path(__file__), Path(helper.__file__), probe, audit)}
    commands, outcomes = [], []

    def run(stem, argv, root, *, tests=False, expected=0):
        env = dict(os.environ)
        if tests:
            env["PYTHONPATH"] = str(root / "src") + ":" + str(root / "tests")
        log = out / (stem + ".log")
        with log.open("x") as stream:
            result = subprocess.run(argv, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(argv=argv, cwd=str(root), returncode=result.returncode, log=log.name))
        assert result.returncode == expected, str(log)
        print(stem + ": exit " + str(result.returncode), flush=True)
        return log.read_text()

    lock_path = Path("/home/bryan/.cache/agent-active-feed-cpu.lock")
    with lock_path.open("a") as lock:
        print("Waiting for shared CPU advisory lock; no CPU claim", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        for label, python in (("314", sys.executable), ("311", PY311)):
            text = run("before-rejection-" + label, [python, "-B", "-m", "unittest", "-v",
                       "test_sync_patch_workspace.PatchWorkspaceTests.test_compact_duplicate_fields_reject_before_unbounded_reference_growth"],
                       before, tests=True, expected=1)
            assert "Ran 1 test" in text and "FAILED (failures=1)" in text and "ERROR:" not in text
            assert "sync_decoded_capacity" in text and "sync_duplicate_field_token" in text
            run("focused-" + label, [python, "-B", "-m", "unittest", "-v", "test_sync_reconstruction",
                                     "test_sync_compact", "test_sync_ordered", "test_sync_packed_nodes",
                                     "test_sync_patch_workspace"], after, tests=True)
            for rows in (500, 2000):
                for backend in ("default", "packed"):
                    stem = f"{rows}-{backend}-{label}"
                    output = out / (stem + ".json")
                    run(stem, [python, "-B", str(probe), "--mesh", str(after), "--observer", str(observer),
                               "--rows", str(rows), "--backend", backend, "--output", str(output)], after)
                    case = json.loads(output.read_text())
                    assert case["gcDisabled"] and case["finalCounters"] == [0] * 6
                    assert case["heapPeak"] <= 67108864 and case["encodedPeakReservedBound"] <= 33554432
                    for name, digest in case["loadedInputs"].items():
                        side, path = name.split("/", 1)
                        assert inputs["after" if side == "mesh" else side][path]["sha256"] == digest
                    scalar = {key: case[key] for key in ("rows", "backend", "python", "outcome", "failure",
                                                         "heapPeak", "encodedPeakReservedBound")}
                    outcomes.append(scalar)
                    print(json.dumps(scalar), flush=True)
    run("profile-packed2000-314", [sys.executable, "-B", str(audit), "--mesh", str(after),
                                   "--observer", str(observer), "--output", str(out / "profile-packed2000-314.json")], after)
    expected_before = dict(inputs["before"])
    expected_before["tests/test_sync_patch_workspace.py"] = overlay_pin
    assert inventory(before, selected) == expected_before
    assert inventory(after, selected) == inputs["after"]
    assert inventory(observer, ("agent_observer", "tests")) == inputs["observer"]
    assert all(pin(repo / path) == expected for path, expected in runners.items())
    report = dict(meshBefore=BEFORE, meshAfter=args.after, observer=OBSERVER, inputs=inputs,
                  gitVerified=verified, protectedInputs=protected,
                  beforeTestOverlay=dict(path="tests/test_sync_patch_workspace.py", **overlay_pin,
                                         scope="Only duplicate reference-list rejection method executed; old rejected at capacity, no prior authority claim"),
                  runners=runners, commands=commands, screens=outcomes,
                  priorReceipt=pin(previous / "receipt.json"), priorArtifactPinsUnchanged=len(prior["artifacts"]),
                  artifacts={path.name: pin(path) for path in sorted(out.iterdir()) if path.is_file()},
                  exclusions="Private scratch/topology tests. Same frozen original compact sourceIPC+Reader singleledger probe/audit. Observer84 only, excludes new uncommitted patch prototype. Nativeowner separateaccount; testowned packedarena, full500/2000 fixture3510/14010cells notdense9, private nonce/nativepin/proofcarrier prepaidfixturecredit/syntheticclock. No ordinary SyncReader/authroute/relay/controller, inclusivephysicalheap/RSS/CPU, absolute2s15s, delivered2krecovery/native/fixedSSH/installedpair/producer acceptance. Expanded path retains original wholepatch prepayment; new scoped scratch billing is compact-only.")
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
