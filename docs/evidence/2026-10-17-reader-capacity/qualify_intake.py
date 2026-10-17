"""Serial immutable diagnostic screens under the shared CPU advisory lock."""

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def pin(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def inventory(root, directories):
    return {str(path.relative_to(root)): pin(path)
            for directory in directories for path in sorted((root / directory).rglob("*"))
            if path.is_file() and path.suffix in (".py", ".json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--python311", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    here, out = Path(__file__).resolve().parent, args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mesh_inputs = inventory(mesh, ("src", "tests", "scripts", "contracts"))
    owner_inputs = inventory(observer, ("agent_observer", "tests"))
    probe = here / "probe_reader_intake.py"
    probe_pin = pin(probe)
    lock_path = Path("/home/bryan/.cache/agent-active-feed-cpu.lock")
    commands, outcomes = [], []
    with lock_path.open("a") as lock:
        print("Waiting for shared CPU advisory lock", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        print("Shared lock acquired; diagnostic screens, no matched CPU claim", flush=True)
        for label, python in (("314", sys.executable), ("311", str(args.python311.absolute()))):
            for rows in (100, 500, 2000):
                for backend in ("default", "packed"):
                    stem = f"{rows}-{backend}-{label}"
                    output, log = out / (stem + ".json"), out / (stem + ".log")
                    argv = [python, "-B", str(probe), "--mesh", str(mesh), "--observer", str(observer),
                            "--rows", str(rows), "--backend", backend, "--output", str(output)]
                    with log.open("x") as stream:
                        result = subprocess.run(argv, cwd=mesh, stdout=stream, stderr=subprocess.STDOUT)
                    commands.append(dict(argv=argv, cwd=str(mesh), returncode=result.returncode))
                    assert result.returncode == 0, f"retain diagnostic {log}"
                    report = json.loads(output.read_text())
                    assert report["gcDisabled"] and report["finalCounters"] == [0] * 6
                    assert report["heapPeak"] <= 67108864 and report["encodedPeakReservedBound"] <= 33554432
                    for name, digest in report["loadedInputs"].items():
                        side, path = name.split("/", 1)
                        assert (mesh_inputs if side == "mesh" else owner_inputs)[path]["sha256"] == digest
                    assert pin(probe) == probe_pin, "do not edit measured source"
                    scalar = {name: report[name] for name in (
                        "rows", "backend", "python", "outcome", "heapPeak", "encodedPeakReservedBound", "nativeMembershipCells")}
                    scalar["failure"] = None if report["failure"] is None else dict(
                        stage=report["failure"]["stage"], code=report["failure"]["code"])
                    outcomes.append(scalar)
                    print(json.dumps(scalar), flush=True)
    assert inventory(mesh, ("src", "tests", "scripts", "contracts")) == mesh_inputs
    assert inventory(observer, ("agent_observer", "tests")) == owner_inputs
    report = dict(
        status="diagnostic capacity screen only; no inclusive process/resource/performance acceptance",
        meshRuntime="d013d2afd14c3d6fa03a3fe377b62aff3ee5944b",
        observerRuntime="84d284dab04b68ae0e9070335d017e85564f2ba9",
        meshInputs=mesh_inputs, observerInputs=owner_inputs,
        runners={path.name: pin(path) for path in (probe, Path(__file__).resolve())},
        sharedLock=str(lock_path), commands=commands, outcomes=outcomes,
        artifacts={path.name: pin(path) for path in out.iterdir()},
        exclusions="Actual disposable native IPC source+Reader ledger; native service has separate owning account. Synthetic fixture is not dense9; full-only. Private packed selection is test-owned only. Metering hook, private nonce/native pin/proof carrier, synthetic Reader clock, no absolute acquisition gate; no relay/controller/ordinary authenticated route, inclusive physical heap/RSS, matched CPU, delivered2k recovery, populated native/fixedSSH/immutable installed pair or producer acceptance. All runtime source stays immutable. Draft clock-context and generation receipt setup diagnostics are separate.",
    )
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
