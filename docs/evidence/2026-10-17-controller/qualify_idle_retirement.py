"""Immutable idle-frame retirement correction with unchanged public probes."""

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--before-mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--python311", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, before, observer = (path.resolve() for path in (args.mesh, args.before_mesh, args.observer))
    out, here = args.output.resolve(), Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("controller_prior_qualify", here / "qualify.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    old = json.loads((here / "copy-close/qualification.json").read_text())
    current = prior.inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",))
    initial = prior.inventory(before, ("src", "tests", "scripts"), ("pyproject.toml",))
    owner = prior.inventory(observer, ("agent_observer", "tests"))
    assert initial == old["meshInputs"] and owner == old["observerInputs"]
    assert all(prior.digest(mesh / name) == value for name, value in old["protectedInputs"].items())
    probes = {
        "idle": ("probe_idle_frame_retirement_original.py.txt", "051e31f1fbecb3f4ef4fe76d5f32a7897fc80066f40d57088bba0bc27a97d1be"),
        "copy": ("probe_header_close_original.py.txt", "b33788f836fd9585fad85fb50c439eb3d567e3f75682d76145bd2819fc933a0f"),
    }
    for name, digest in probes.values():
        assert prior.digest(here / name)["sha256"] == digest
    commands = []

    def run(name, argv):
        logfile = out / (name + ".log")
        with logfile.open("x") as stream:
            result = subprocess.run(argv, cwd=mesh, stdout=stream, stderr=subprocess.STDOUT)
        commands.append(dict(name=name, argv=argv, cwd=str(mesh), returncode=result.returncode))
        assert result.returncode == 0, f"{name} failed; retain {logfile}"

    for label, python in (("314", sys.executable), ("311", str(args.python311.absolute()))):
        for phase, source, inventory in (("before", before, initial), ("after", mesh, current)):
            for kind, (probe, _) in probes.items():
                output = out / f"{kind}-{phase}-{label}.json"
                run(f"{kind}-{phase}-{label}", [python, "-B", str(here / probe),
                    "--mesh", str(source), "--output", str(output)])
                result = json.loads(output.read_text())
                assert result["gcDisabled"]
                if kind == "idle":
                    assert result["siblingUsable"]
                    if phase == "before":
                        assert result["finalCounters"] == [0, 132952, 0, 0, 0]
                        assert len(result["callbackErrors"]) == 1
                        assert result["callbackErrors"][0]["type"] == "TypeError"
                    else:
                        assert result["finalCounters"] == [0] * 5 and not result["callbackErrors"]
                else:
                    for case in result["cases"]:
                        assert not case["returnedDetachedValueAfterClose"]
                        assert case["heapDuringOriginalDtoCopy"] == case["heapBeforeCopy"]
                        assert case["materializeError"] == "sync_control_retired"
                        assert case["siblingUsable"] and case["finalCounters"] == [0] * 5
                        if "closeReturnedBeforeCopyUnwind" in case:
                            assert not case["closeReturnedBeforeCopyUnwind"]
                for name, digest in result["loadedInputs"].items():
                    assert inventory[name]["sha256"] == digest
        names = ["test_sync_control.CarrierTests.test_worker_idle_frame_close_then_owner_close_drains_queued_retirement"]
        for phase, source, modules, count, failures in (
            ("before", before, names, 1, 2),
            ("after", mesh, ["test_sync_control", "test_sync_controller", "test_sync_relay"], 68, 0),
        ):
            output = out / f"unit-{phase}-{label}.json"
            code = (
                "import gc,json,sys,unittest;from pathlib import Path;gc.disable();"
                f"sys.path[:0]=[{str(source / 'src')!r},{str(mesh / 'tests')!r}];"
                f"suite=unittest.TestLoader().loadTestsFromNames({modules!r});"
                "r=unittest.TextTestRunner(verbosity=2).run(suite);assert not gc.isenabled();"
                f"Path({str(output)!r}).write_text(json.dumps(dict(python=sys.version.split()[0],testsRun=r.testsRun,failures=len(r.failures),errors=len(r.errors),skips=len(r.skipped)))+'\\n');"
                f"sys.exit(not(r.testsRun=={count} and len(r.failures)=={failures} and not r.errors and not r.skipped))"
            )
            run(f"unit-{phase}-{label}", [python, "-B", "-c", code])
        for name, script, scenarios in (("basic", "verify_observer_controller.py", 24),
                                         ("lifecycle", "verify_controller_lifecycle.py", 20)):
            output = out / f"{name}-{label}.json"
            run(f"{name}-command-{label}", [python, "-B", str(here / script), "--mesh", str(mesh),
                "--observer", str(observer), "--output", str(output), "--log", str(out / f"{name}-{label}.log")])
            result = json.loads(output.read_text())
            assert (result["failures"], result["errors"], result["skips"], len(result["cases"])) == (0, 0, 0, scenarios)
            for name, digest in result["loadedInputs"].items():
                side, path = name.split("/", 1)
                assert (current if side == "mesh" else owner)[path]["sha256"] == digest
    run("canonical-314", [sys.executable, "-B", str(mesh / "scripts/check.py")])
    assert "\nRan 387 tests in " in (out / "canonical-314.log").read_text()
    assert prior.inventory(mesh, ("src", "tests", "scripts"), ("pyproject.toml",)) == current
    assert prior.inventory(before, ("src", "tests", "scripts"), ("pyproject.toml",)) == initial
    assert prior.inventory(observer, ("agent_observer", "tests")) == owner
    report = dict(
        status="bounded idle-frame correction and preserved copy-pin/source replays; independent review pending",
        runtime="d013d2afd14c3d6fa03a3fe377b62aff3ee5944b",
        before="14990c789f853441b51af81ea0919facf0aff320",
        observer="e3441d017b94ee27f4dfccb5f1f3f30612435adf",
        meshInputs=current, beforeInputs=initial, observerInputs=owner,
        protectedInputs=old["protectedInputs"], commands=commands,
        outputs={path.name: prior.digest(path) for path in out.iterdir()},
        runners={name: prior.digest(here / name) for name in (
            "qualify_idle_retirement.py", "probe_idle_frame_retirement_original.py.txt",
            "probe_header_close_original.py.txt", "verify_observer_controller.py", "verify_controller_lifecycle.py")},
        exclusions=old["exclusions"],
    )
    (out / "qualification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(dict(canonical=387, focusedPerPython=68, basicScenariosPerPython=24,
                         lifecycleScenariosPerPython=20, beforeNamedTests=1, beforeFailedChecks=2,
                         meshInputs=len(current), beforeInputs=len(initial), observerInputs=len(owner))))


if __name__ == "__main__":
    main()
