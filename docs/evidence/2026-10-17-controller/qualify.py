"""Reproduce a private, immutable controller source checkpoint; no rollout."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def digest(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def inventory(root, trees, files=()):
    paths = {root / name for name in files}
    for name in trees:
        paths.update(path for path in (root / name).rglob("*")
                     if path.is_file() and path.suffix in (".py", ".json"))
    return {str(path.relative_to(root)): digest(path) for path in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True, help="immutable git archive")
    parser.add_argument("--observer", type=Path, required=True, help="immutable git archive")
    parser.add_argument("--before-mesh", type=Path, required=True, help="immutable 828cf0c archive")
    parser.add_argument("--python311", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer, out = args.mesh.resolve(), args.observer.resolve(), args.output.resolve()
    before = args.before_mesh.resolve()
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    protected = json.loads((mesh / "docs/evidence/2026-10-16-delta-sync/source-retirement-pair-review.json").read_text())["protectedMeshInputs"]
    assert all(digest(mesh / name) == expected for name, expected in protected.items())
    mesh_inputs = inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",))
    owner_inputs = inventory(observer, ("agent_observer", "tests"))
    before_inputs = inventory(before, ("src", "tests", "scripts"), ("pyproject.toml",))
    logs, commands, reports = {}, [], {}

    def run(name, argv):
        log = out / (name + ".log")
        with log.open("x") as stream:
            result = subprocess.run(argv, cwd=mesh, stdout=stream, stderr=subprocess.STDOUT)
        logs[log.name] = digest(log)
        commands.append({"name": name, "argv": argv, "cwd": str(mesh), "returncode": result.returncode})
        assert result.returncode == 0, f"{name} failed; retain {log}"

    for label, python in (("314", sys.executable), ("311", str(args.python311.absolute()))):
        prior = out / ("before-provenance-" + label + ".json")
        before_code = (
            "import gc,json,sys,unittest; from pathlib import Path; gc.disable(); "
            f"sys.path[:0]=[{str(before / 'src')!r},{str(mesh / 'tests')!r}]; "
            "suite=unittest.TestLoader().loadTestsFromNames(['test_sync_control.CarrierTests.test_buffered_tail_and_minted_header_reject_changed_clock_before_new_read',"
            "'test_sync_control.CarrierTests.test_failed_detached_copy_clears_payload_and_hook_frames_before_credit_return']); "
            "result=unittest.TextTestRunner(verbosity=2).run(suite); assert not gc.isenabled(); "
            f"Path({str(prior)!r}).write_text(json.dumps(dict(python=sys.version.split()[0],testsRun=result.testsRun,"
            "expectedSubcaseFailures=len(result.failures),errors=len(result.errors),skips=len(result.skipped)))+'\\n'); "
            "sys.exit(not (result.testsRun==2 and len(result.failures)==5 and not result.errors and not result.skipped))"
        )
        run("before-provenance-" + label, [python, "-B", "-c", before_code])
        reports[prior.name] = digest(prior)
        focused = out / ("focused-" + label + ".json")
        code = (
            "import gc,json,sys,unittest; from pathlib import Path; gc.disable(); "
            "sys.path[:0]=['src','tests']; "
            "suite=unittest.TestLoader().loadTestsFromNames(['test_sync_control','test_sync_controller','test_sync_relay']); "
            "result=unittest.TextTestRunner(verbosity=2).run(suite); "
            "assert not gc.isenabled(); "
            f"Path({str(focused)!r}).write_text(json.dumps(dict(python=sys.version.split()[0],testsRun=result.testsRun,"
            "failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),cyclicGC='disabled'))+'\\n'); "
            "sys.exit(not result.wasSuccessful() or bool(result.skipped))"
        )
        run("focused-" + label, [python, "-B", "-c", code])
        reports[focused.name] = digest(focused)
        assert json.loads(focused.read_text())["testsRun"] == 64
        composition = out / ("composition-" + label + ".json")
        run("composition-command-" + label, [python, "-B", str(here / "verify_observer_controller.py"),
             "--mesh", str(mesh), "--observer", str(observer), "--output", str(composition),
             "--log", str(out / ("composition-" + label + ".log"))])
        reports[composition.name] = digest(composition)
        logs["composition-" + label + ".log"] = digest(out / ("composition-" + label + ".log"))
        value = json.loads(composition.read_text())
        assert len(value["cases"]) == 24 and (value["failures"], value["errors"], value["skips"]) == (0, 0, 0)
        for key, expected in value["loadedInputs"].items():
            side, name = key.split("/", 1)
            assert (mesh_inputs if side == "mesh" else owner_inputs)[name]["sha256"] == expected
    run("canonical-314", [sys.executable, "-B", str(mesh / "scripts/check.py")])
    assert inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",)) == mesh_inputs
    assert inventory(observer, ("agent_observer", "tests")) == owner_inputs
    assert inventory(before, ("src", "tests", "scripts"), ("pyproject.toml",)) == before_inputs
    report = {
        "status": "bounded source checkpoint passed; not route or producer acceptance",
        "meshRuntime": "a482abbd463d23ebf66f23c60e4e95a521c19cc6",
        "beforeClockProvenanceRuntime": "828cf0c759d36cc8aa939c513ac6c156862e3526",
        "observerSource": "e3441d017b94ee27f4dfccb5f1f3f30612435adf",
        "meshInputs": mesh_inputs, "observerInputs": owner_inputs,
        "beforeMeshInputs": before_inputs,
        "protectedMeshInputs": protected,
        "artifacts": {path.name: digest(path) for path in (Path(__file__).resolve(), here / "verify_observer_controller.py")},
        "commands": commands, "logs": logs, "results": reports,
        "exclusions": "No native providers, fixed SSH, authentication/selected Reader route, actual compact watch/cancel stress, aggregate shared32-64/RSS/CPU/dense2k/delivered-recovery/immutable-installed-pair/consumer adoption or rollout acceptance.",
    }
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"focusedPerPython": 64, "actualScenariosPerPython": 24, "canonicalTests": 383,
                      "meshInputs": len(mesh_inputs), "observerInputs": len(owner_inputs), "status": report["status"]}))


if __name__ == "__main__":
    main()
