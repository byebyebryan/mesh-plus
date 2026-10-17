"""Exact owner/ref tests; negative mode proves old ABI absence, not a source fix."""

import argparse
import gc
import hashlib
import json
import sys
import unittest
from pathlib import Path

MODULES = ("test_sync_inputs", "test_sync_relay")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--new-only", action="store_true")
    parser.add_argument("--expect-unavailable", action="store_true")
    args = parser.parse_args()
    mesh = args.mesh.resolve()
    sys.path[:0] = [str(mesh / "src"), str(mesh / "tests")]
    gc.disable()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
    if args.new_only:
        suite = unittest.TestSuite(item for item in flatten(suite)
                                   if item._testMethodName.startswith("test_ref_retirement"))
    count = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert not gc.isenabled()
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or Path(filename).suffix != ".py":
            continue
        path = Path(filename).resolve()
        if path.is_relative_to(mesh):
            relative = path.relative_to(mesh)
            if relative.parts[0] in ("src", "tests"):
                loaded[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    expected = 7 if args.new_only else 60
    valid = count == result.testsRun == expected and not result.skipped
    if args.expect_unavailable:
        valid = (valid and args.new_only and not result.failures and len(result.errors) == 7 and
                 all("has no attribute 'ref_is_retired'" in error for _, error in result.errors))
    else:
        valid = valid and result.wasSuccessful()
    report = {
        "python": sys.version.split()[0], "testsRun": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "expected": "old capability unavailable" if args.expect_unavailable else "pass",
        "matchesExpected": valid, "newOnly": args.new_only,
        "cyclicGC": "disabled before imports and operations; no explicit collection",
        "failureDetails": [{"name": case.id(), "traceback": error} for case, error in result.failures],
        "errorDetails": [{"name": case.id(), "traceback": error} for case, error in result.errors],
        "meshExport": str(mesh), "loadedInputs": loaded,
        "scope": "public query state/role/owner/epoch/error/semantic isolation; disclosed private generic pins and buffer count instrumentation",
        "exclusions": "No owning-source pruning adoption/fix, actual native/installed pair, end-to-end resources/RSS/CPU/2k recovery or rollout acceptance.",
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    raise SystemExit(0 if valid else 1)


if __name__ == "__main__":
    main()
