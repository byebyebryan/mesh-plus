"""Immutable copy-close correction, independent original probe and source replay."""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--before-mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--python311", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, before, observer = args.mesh.resolve(), args.before_mesh.resolve(), args.observer.resolve()
    out, here = args.output.resolve(), Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=False)
    prior = load("prior_qualify", here / "qualify.py")
    old = json.loads((here / "results/qualification.json").read_text())
    assert all(prior.digest(mesh / name) == value for name, value in old["protectedMeshInputs"].items())
    initial = prior.inventory(before, ("src", "tests", "scripts"), ("pyproject.toml",))
    assert initial == old["meshInputs"]
    current = prior.inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",))
    owner = prior.inventory(observer, ("agent_observer", "tests"))
    assert owner == old["observerInputs"]
    original_probe = here / "probe_header_close_original.py.txt"
    assert hashlib.sha256(original_probe.read_bytes()).hexdigest() == "b33788f836fd9585fad85fb50c439eb3d567e3f75682d76145bd2819fc933a0f"
    commands, artifacts = [], {}

    def run(name, argv):
        logfile = out / (name + ".log")
        with logfile.open("x") as stream:
            result = subprocess.run(argv, cwd=mesh, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(name=name, argv=argv, cwd=str(mesh), returncode=result.returncode))
        assert result.returncode == 0, f"{name} failed: retain {logfile}"

    suffixes = ("reentrant_frame_close_keeps_original_copy_credit_and_rejects_result",
                "concurrent_carrier_close_joins_copy_despite_repeated_cancel_and_keeps_sibling",
                "retired_inflight_copy_still_occupies_frame_slot_and_concurrent_copy_rejects")
    names = ["test_sync_control.CarrierTests.test_" + name for name in suffixes]
    for label, python in (("314", sys.executable), ("311", str(args.python311.absolute()))):
        for phase, source in (("before", before), ("after", mesh)):
            output = out / ("root-probe-" + phase + "-" + label + ".json")
            run("root-probe-" + phase + "-" + label,
                [python, "-B", str(original_probe), "--mesh", str(source), "--output", str(output)])
            result = json.loads(output.read_text())
            for case in result["cases"]:
                assert case["returnedDetachedValueAfterClose"] is (phase == "before")
                assert case["siblingUsable"] and case["finalCounters"] == [0] * 5
                if phase == "after":
                    assert case["heapDuringOriginalDtoCopy"] == case["heapBeforeCopy"]
                    assert case["materializeError"] == "sync_control_retired"
                else:
                    assert case["heapDuringOriginalDtoCopy"] < case["heapBeforeCopy"]
                if "closeReturnedBeforeCopyUnwind" in case:
                    assert case["closeReturnedBeforeCopyUnwind"] is (phase == "before")
            for path, expected in result["loadedInputs"].items():
                assert (initial if phase == "before" else current)[path]["sha256"] == expected
        for phase, source, modules, count, expected in (
            ("before", before, names, 3, 3),
            ("after", mesh, ["test_sync_control", "test_sync_controller", "test_sync_relay"], 67, 0),
        ):
            output = out / ("unit-" + phase + "-" + label + ".json")
            code = (
                "import gc,json,sys,unittest;from pathlib import Path;gc.disable();"
                f"sys.path[:0]=[{str(source / 'src')!r},{str(mesh / 'tests')!r}];"
                f"suite=unittest.TestLoader().loadTestsFromNames({modules!r});"
                "r=unittest.TextTestRunner(verbosity=2).run(suite);assert not gc.isenabled();"
                f"Path({str(output)!r}).write_text(json.dumps(dict(python=sys.version.split()[0],testsRun=r.testsRun,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped)))+'\\n');"
                f"sys.exit(not (r.testsRun=={count} and len(r.failures)=={expected} and not r.errors and not r.skipped))"
            )
            run("unit-" + phase + "-" + label, [python, "-B", "-c", code])
        for name, script, scenarios in (("basic", "verify_observer_controller.py", 24),
                                         ("lifecycle", "verify_controller_lifecycle.py", 20)):
            output = out / (name + "-" + label + ".json")
            run(name + "-command-" + label, [python, "-B", str(here / script), "--mesh", str(mesh),
                "--observer", str(observer), "--output", str(output), "--log", str(out / (name + "-" + label + ".log"))])
            result = json.loads(output.read_text())
            assert (result["failures"], result["errors"], result["skips"], len(result["cases"])) == (0, 0, 0, scenarios)
            for key, expected in result["loadedInputs"].items():
                side, path = key.split("/", 1)
                assert (current if side == "mesh" else owner)[path]["sha256"] == expected
    run("canonical-314", [sys.executable, "-B", str(mesh / "scripts/check.py")])
    assert "\nRan 386 tests in " in (out / "canonical-314.log").read_text()
    assert prior.inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",)) == current
    assert prior.inventory(observer, ("agent_observer", "tests")) == owner
    for path in out.iterdir():
        artifacts[path.name] = prior.digest(path)
    report = dict(status="bounded copy-close implementation correction; no producer/route acceptance",
                  runtime="14990c789f853441b51af81ea0919facf0aff320", before="a482abbd463d23ebf66f23c60e4e95a521c19cc6",
                  observer="e3441d017b94ee27f4dfccb5f1f3f30612435adf", meshInputs=current, beforeInputs=initial,
                  observerInputs=owner, protectedInputs=old["protectedMeshInputs"], commands=commands, outputs=artifacts,
                  runners={name: prior.digest(here / name) for name in
                           ("qualify_copy_close.py", "probe_header_close_original.py.txt", "verify_observer_controller.py", "verify_controller_lifecycle.py")},
                  exclusions="Original controlled deepcopy timings, synthetic Runtime/source data and trusted test caller, private nonce/native teardown/physical inventory hooks, separate ledgers/oracles. No measured cap/RSS overrun, aggregate32-64/CPU/dense2k/deliveredrecovery/populatednative/fixedSSH/installedpair/ordinaryauthenticatedroute/selection/rollout acceptance.")
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(canonical=386, focusedPerPython=67, basicScenariosPerPython=24, lifecycleScenariosPerPython=20,
                         beforeNamedFailuresPerPython=3, meshInputs=len(current), observerInputs=len(owner))))


if __name__ == "__main__":
    main()
