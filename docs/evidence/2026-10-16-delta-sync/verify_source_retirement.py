"""Exact original/hardened pin overlays or affected committed source tests."""

import argparse
import gc
import hashlib
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

GAP_METHODS = {
    "test_public_inspect_preserves_head_pin_for_scope_close",
    "test_receive_pruning_preserves_another_head_pin_for_scope_close",
    "test_inspection_does_not_abort_a_healthy_pin",
}
MODULES = ("test_sync_source_retirement", "test_sync_owned_source", "test_sync_completed_changes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--overlay", type=Path)
    parser.add_argument("--expect-gap", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    paths = [str(mesh / "src"), str(observer), str(observer / "tests")]
    sys.path[:0] = paths
    os.environ["PYTHONPATH"] = os.pathsep.join(paths)
    gc.disable()
    overlay = None
    if args.overlay is not None:
        overlay = args.overlay.resolve()
        spec = importlib.util.spec_from_file_location("source_pin_review_overlay", overlay)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.SourceRefRevocationTest)
        expected_count = 5
    else:
        assert not args.expect_gap
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
        expected_count = 48
    with args.log.open("x") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert not gc.isenabled()
    valid = result.testsRun == expected_count and not result.errors and not result.skipped
    if args.expect_gap:
        valid = (valid and len(result.failures) == 3 and
                 {case._testMethodName for case, _ in result.failures} == GAP_METHODS)
    else:
        valid = valid and result.wasSuccessful()
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or Path(filename).suffix != ".py":
            continue
        path = Path(filename).resolve()
        for label, root in (("mesh", mesh), ("observer", observer)):
            if path.is_relative_to(root):
                loaded[label + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        "python": sys.version.split()[0], "meshExport": str(mesh), "observerExport": str(observer),
        "overlay": None if overlay is None else {"path": str(overlay), "bytes": overlay.stat().st_size,
                                                 "sha256": hashlib.sha256(overlay.read_bytes()).hexdigest()},
        "modules": [] if overlay is not None else list(MODULES), "testsRun": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "expected": "three original source pin gaps" if args.expect_gap else "pass", "matchesExpected": valid,
        "failureDetails": [{"name": case.id(), "traceback": error} for case, error in result.failures],
        "errorDetails": [{"name": case.id(), "traceback": error} for case, error in result.errors],
        "cyclicGC": "disabled before imports and operations; held errors; no explicit collection",
        "loadedInputs": loaded,
        "scope": "bounded public source retirement query adoption, pin credit/sibling/history/callback lifetimes; disclosed private generic pin fixtures",
        "exclusions": "No aggregate resources/RSS/CPU/dense2k/recovery/populated native/fixedSSH/controller/immutable installed pair or rollout acceptance.",
    }
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips", "matchesExpected")}))
    raise SystemExit(0 if valid else 1)


if __name__ == "__main__":
    main()
