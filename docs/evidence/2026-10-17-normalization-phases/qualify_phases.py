"""Immutable phase-ownership tests and pinned source/Reader capacity screens."""

import argparse
import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

BEFORE = "f0924e457230c49d04d3e5983476766d4c58a4af"
OBSERVER = "84d284dab04b68ae0e9070335d017e85564f2ba9"
PY311 = "/home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python"


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def inventory(root, directories):
    return {str(path.relative_to(root)): pin(path)
            for directory in directories for path in sorted((root / directory).rglob("*"))
            if path.is_file() and path.suffix in (".py", ".json")}


def verify(repo, commit, inputs):
    for name, expected in inputs.items():
        raw = subprocess.check_output(["git", "-C", str(repo), "show", commit + ":" + name])
        assert dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()) == expected, name
    return len(inputs)


def export(repo, commit, destination):
    destination.mkdir(exist_ok=False)
    raw = subprocess.check_output(["git", "-C", str(repo), "archive", commit,
                                   "src", "tests", "scripts", "contracts", "pyproject.toml"])
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        archive.extractall(destination, filter="data")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after", required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--observer-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    here, repo = Path(__file__).resolve().parent, Path(__file__).resolve().parents[3]
    previous = here.with_name("2026-10-17-reader-capacity")
    out = args.output.resolve()
    out.mkdir(exist_ok=False)
    before, after = out / "before", out / "after"
    export(repo, BEFORE, before)
    export(repo, args.after, after)
    observer = args.observer.resolve()
    selected = ("src", "tests", "scripts", "contracts")
    snapshots = dict(before=inventory(before, selected), after=inventory(after, selected),
                     observer=inventory(observer, ("agent_observer", "tests")))
    verified = dict(before=verify(repo, BEFORE, snapshots["before"]),
                    after=verify(repo, args.after, snapshots["after"]),
                    observer=verify(args.observer_repo, OBSERVER, snapshots["observer"]))
    protected = json.loads((here.with_name("2026-10-17-controller") /
                            "idle-retirement/qualification.json").read_text())["protectedInputs"]
    verified["protected"] = verify(repo, args.after, protected)
    assert verify(repo, BEFORE, protected) == verified["protected"]
    prior = json.loads((previous / "receipt.json").read_text())
    for name, expected in prior["artifacts"].items():
        assert pin(repo / name) == expected, name
    # Only two new tests run on the old runtime. The resource assertion must
    # fail; the unchanged delta ownership/rollback requirement is a control.
    overlay = before / "tests/test_sync_compact.py"
    overlay.write_bytes((after / "tests/test_sync_compact.py").read_bytes())
    overlay_pin = pin(overlay)
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

    probe, audit = previous / "probe_reader_intake.py", previous / "profile_intake.py"
    runners = {str(path.relative_to(repo)): pin(path) for path in (Path(__file__), probe, audit)}
    lock_path = Path("/home/bryan/.cache/agent-active-feed-cpu.lock")
    with lock_path.open("a") as lock:
        print("Waiting for shared CPU advisory lock; no CPU claim", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        for label, python in (("314", sys.executable), ("311", PY311)):
            text = run("before-" + label, [python, "-B", "-m", "unittest", "-v",
                       "test_sync_compact.CompactTests.test_baseline_phase_credit_does_not_accumulate_at_profile_entry",
                       "test_sync_compact.CompactTests.test_delta_operation_credit_survives_phase_cleanup_and_callback_failure"],
                       before, tests=True, expected=1)
            assert "Ran 2 tests" in text and "FAILED (failures=1)" in text and "ERROR:" not in text
            run("compact-" + label, [python, "-B", "-m", "unittest", "-v", "test_sync_compact"], after, tests=True)
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
                        assert snapshots["after" if side == "mesh" else side][path]["sha256"] == digest
                    scalar = {key: case[key] for key in ("rows", "backend", "python", "outcome", "failure",
                                                         "heapPeak", "encodedPeakReservedBound")}
                    outcomes.append(scalar)
                    print(json.dumps(scalar), flush=True)
    run("profile-packed2000-314", [sys.executable, "-B", str(audit), "--mesh", str(after),
                                   "--observer", str(observer), "--output", str(out / "profile-packed2000-314.json")], after)
    expected_before = dict(snapshots["before"])
    expected_before["tests/test_sync_compact.py"] = overlay_pin
    assert inventory(before, selected) == expected_before
    assert inventory(after, selected) == snapshots["after"]
    assert inventory(observer, ("agent_observer", "tests")) == snapshots["observer"]
    assert all(pin(repo / path) == expected for path, expected in runners.items())
    report = dict(meshBefore=BEFORE, meshAfter=args.after, observer=OBSERVER, inputs=snapshots,
                  gitVerified=verified, protectedInputs=protected,
                  beforeTestOverlay=dict(path="tests/test_sync_compact.py", **overlay_pin,
                                         scope="Only resource assertion and delta rollback/control methods executed"),
                  runners=runners, commands=commands, screens=outcomes,
                  priorReceipt=pin(previous / "receipt.json"), priorArtifactPinsUnchanged=len(prior["artifacts"]),
                  artifacts={path.name: pin(path) for path in sorted(out.iterdir()) if path.is_file()},
                  exclusions="Private phase/topology test instrumentation; unchanged source intake probe and private scalar audit. Actual disposable compact source IPC and Reader share one ledger; native owner has separate account. Private packed arena test-owned. Synthetic full500/2000 fixture has3510/14010cells, not dense9. Test nonce/native pin/proof carrier extra prepaid scratch and synthetic clock; no ordinary relay/controller/authenticated selected route, inclusive physical heap/RSS/CPU, native/fixedSSH/installedpair/producer acceptance. See prior frozen capacity probe for exact exclusions.")
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
