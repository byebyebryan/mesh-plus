"""Exact Observer patch / Mesh compact index join, no source modifications."""

import argparse
import fcntl
import gc
import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

MESH = "231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc"
MESH_EVIDENCE = "103f3b3056d5f88d4e72e6556e7af6e8ff2e7aed"
OBSERVER = "b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f"
OBSERVER_EVIDENCE = "1cc8217d4f60a339a9eacca0589f76bc9667d101"
OWNER_TESTS = ("test_mesh_sync_patch", "test_mesh_sync_profile", "test_mesh_sync_codec", "test_mesh_sync_read")
MESH_TESTS = ("test_sync_compact", "test_sync_reconstruction", "test_sync_ordered",
              "test_sync_packed_nodes", "test_sync_patch_workspace")


def helper_module():
    path = Path(__file__).resolve().parents[1] / "2026-10-17-normalization-phases/qualify_phases.py"
    spec = importlib.util.spec_from_file_location("phase_utilities", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def loaded(mesh, observer):
    import hashlib

    result = {}
    for module in tuple(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path and Path(path).suffix == ".py":
            path = Path(path).resolve()
            for name, root in (("mesh", mesh), ("observer", observer)):
                if path.is_relative_to(root):
                    result[name + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
                    break
    return result


def worker(args):
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    # Each owning suite has same-named fixture modules. Separate processes
    # preserve both namespaces rather than replacing another owner's helper.
    sys.path[:0] = ([str(mesh / "src"), str(observer), str(observer / "tests")] if args.role == "observer" else
                    [str(mesh / "src"), str(mesh / "tests"), str(observer)])
    gc.disable()
    modules = OWNER_TESTS if args.role == "observer" else MESH_TESTS
    expected = 64 if args.role == "observer" else 68
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    with args.log.open("x") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert not gc.isenabled()
    report = dict(python=sys.version.split()[0], methods=result.testsRun, failures=len(result.failures),
                  errors=len(result.errors), skipped=len(result.skipped), gcDisabled=True,
                  role=args.role, modules=modules, loadedInputs=loaded(mesh, observer))
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    assert result.wasSuccessful() and not result.skipped and result.testsRun == expected


def qualify(args):
    helper = helper_module()
    repo = Path(__file__).resolve().parents[3]
    work = args.output.resolve()
    work.mkdir(exist_ok=False)
    mesh, observer = work / "mesh-103f3b3", work / "observer-1cc8217"
    # Full exports retain both immutable reports and their source inventories.
    import io
    import tarfile

    for root, revision, path in ((repo, MESH_EVIDENCE, mesh),
                                  (args.observer_repo, OBSERVER_EVIDENCE, observer)):
        path.mkdir()
        raw = subprocess.check_output(["git", "-C", str(root), "archive", revision])
        with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
            archive.extractall(path, filter="data")
    inputs = dict(mesh=helper.inventory(mesh, ("src", "tests", "scripts", "contracts")),
                  observer=helper.inventory(observer, ("agent_observer", "tests")))
    verified = dict(mesh=helper.verify(repo, MESH, inputs["mesh"]),
                    observer=helper.verify(args.observer_repo, OBSERVER, inputs["observer"]))
    upstream = {}
    for name, root, path in (
        ("mesh", mesh, "docs/evidence/2026-10-17-index-workspace/receipt.json"),
        ("observer", observer, "docs/evidence/2026-10-17-profile-patch/receipt.json"),
        ("observerGroupJoin", observer, "docs/evidence/2026-10-17-profile-group-join/receipt.json")):
        upstream[name] = dict(path=path, pin=helper.pin(root / path))
    previous = json.loads((mesh / upstream["mesh"]["path"]).read_text())
    for name, expected in previous["artifacts"].items():
        assert helper.pin(mesh / name) == expected, name
    owner_prior = json.loads((observer / upstream["observer"]["path"]).read_text())
    protected = owner_prior["protectedInputs"]
    verified["protected"] = helper.verify(repo, MESH, protected)
    probe = mesh / "docs/evidence/2026-10-17-reader-capacity/probe_reader_intake.py"
    probe_pin = helper.pin(probe)
    extra_mesh = {str(probe.relative_to(mesh)): probe_pin}
    helper.verify(repo, MESH_EVIDENCE, extra_mesh)
    runner_pin = helper.pin(Path(__file__))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    commands, focused, cases = [], {}, {}

    def run(argv, log):
        with log.open("x") as stream:
            result = subprocess.run(argv, cwd=observer, env=env, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(argv=argv, cwd=str(observer), returncode=result.returncode, log=log.name))
        assert result.returncode == 0, log

    def verify_loaded(report):
        for name, digest in report["loadedInputs"].items():
            role, relative = name.split("/", 1)
            files = inputs[role] | extra_mesh if role == "mesh" else inputs[role]
            assert files[relative]["sha256"] == digest, name

    with Path("/home/bryan/.cache/agent-active-feed-cpu.lock").open("a") as lock:
        print("Waiting for shared CPU advisory lock; no timing claim", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        for label, python in (("314", sys.executable), ("311", str(args.python311.absolute()))):
            focused[label] = {}
            for role in ("observer", "mesh"):
                stem = "focused-" + role + "-" + label
                path = work / (stem + ".json")
                run([python, "-B", str(Path(__file__).resolve()), "--worker", "--role", role,
                     "--mesh", str(mesh), "--observer", str(observer), "--output", str(path),
                     "--log", str(work / (stem + ".log"))], work / (stem + ".stdout.log"))
                focused[label][role] = json.loads(path.read_text())
                verify_loaded(focused[label][role])
            assert sum(report["methods"] for report in focused[label].values()) == 132
            print(label + ":132 focused PASS", flush=True)
            for rows in (100, 500, 2000):
                for backend in ("default", "packed"):
                    name = f"{rows}-{backend}-{label}"
                    path = work / (name + ".json")
                    run([python, "-B", str(probe), "--mesh", str(mesh), "--observer", str(observer),
                         "--rows", str(rows), "--backend", backend, "--output", str(path)], work / (name + ".log"))
                    value = json.loads(path.read_text())
                    verify_loaded(value)
                    assert value["gcDisabled"] and value["finalCounters"] == [0] * 6
                    assert value["heapPeak"] <= 67108864 and value["encodedPeakReservedBound"] <= 33554432
                    cases[name] = value
                    print(json.dumps({key: value[key] for key in ("rows", "backend", "python", "outcome", "failure", "heapPeak")}), flush=True)
    assert helper.inventory(mesh, ("src", "tests", "scripts", "contracts")) == inputs["mesh"]
    assert helper.inventory(observer, ("agent_observer", "tests")) == inputs["observer"]
    assert helper.pin(probe) == probe_pin and helper.pin(Path(__file__)) == runner_pin
    report = dict(meshRuntime=MESH, meshEvidence=MESH_EVIDENCE, observerRuntime=OBSERVER,
                  observerEvidence=OBSERVER_EVIDENCE, inputs=inputs, gitVerified=verified,
                  protectedInputs=protected, upstream=upstream, probe=probe_pin, extraMeshInputs=extra_mesh,
                  runner=runner_pin,
                  focused=focused, capacity=cases, commands=commands,
                  artifacts={path.name: helper.pin(path) for path in work.iterdir() if path.is_file()},
                  exclusions="Same unchanged actual compact sourceIPC+Reader probe, shared32/64ledger, nativeowner separate. Full100/500/2000 fixture710/3510/14010cells notdense9; testowned packedarena; private nonce/nativepin/proofcarrier extra prepaid scratch/syntheticclock. No ordinary SyncReader/authroute/controller/relay, physicalprocessheap/RSS/CPU/absolute2s15s/dense2krecovery/nativefleet/fixedSSH/installedpair/producer acceptance. No source edits or old evidence reattribution.")
    (work / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--role", choices=("mesh", "observer"))
    for name in ("observer-repo", "python311", "mesh", "observer", "log"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    worker(args) if args.worker else qualify(args)


if __name__ == "__main__":
    main()
