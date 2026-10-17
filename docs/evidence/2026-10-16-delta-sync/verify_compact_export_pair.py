"""Actual small compact writer/Reader plus owning components; no route/perf gate."""

import argparse
import gc
import hashlib
import json
import sys
import unittest
from pathlib import Path

MODULES = (
    "test_sync_compact_export", "test_sync_completed_changes", "test_mesh_sync_codec",
    "test_sync_compact_plan", "test_sync_compact", "test_sync_compact_transport",
    "test_mesh_sync_profile", "test_mesh_sync_read", "test_sync_owned_source",
    "test_sync_source", "test_sync_transport", "test_sync_acquisition",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    gc.disable()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
    expected = suite.countTestCases()
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert not gc.isenabled()
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
        "python": sys.version.split()[0], "modules": list(MODULES),
        "meshExport": str(mesh), "observerExport": str(observer),
        "testsRun": result.testsRun, "owningExportTests": 10, "otherOwningTests": 186,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "cyclicGC": "disabled before imports/operations; held errors/handles; no explicit collection",
        "loadedInputs": loaded,
        "scope": "independent execution of unchanged owning small compact native writer/Reader stage/proof/DTO/rollback tests plus component tests",
        "exclusions": [
            "Tests/oracles use synthetic ServiceState and disclosed private owning nonce/native fixture cleanup helpers; runtime codec and Reader use supported APIs.",
            "No actual compact source dispatch/transport/relay/controller path; owning source remains explicitly expanded. Expanded component tests do not qualify compact dispatch.",
            "No large cold probe rerun or dense9field/predecessor/slowpeer/2k delivery/recovery/CPU/RSS/aggregate32/64MiB qualification. Harness/schema/oracle/owner accounts are not one process ledger.",
            "No source pin-pruning closure, schema/encoding allocation/freeze, installed pair, artifact/version/route/provider/service/selection/sibling edit or rollout.",
        ],
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    assert expected == result.testsRun == 196, (expected, result.testsRun)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__ == "__main__":
    main()
