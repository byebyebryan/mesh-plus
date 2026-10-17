"""Run unchanged owning compact-source and component tests on explicit exports."""

import argparse
import gc
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

MODULES = (
    "test_sync_compact_source", "test_sync_compact_export", "test_sync_completed_changes",
    "test_mesh_sync_codec", "test_sync_compact_plan", "test_sync_compact",
    "test_sync_compact_transport", "test_mesh_sync_profile", "test_mesh_sync_read",
    "test_sync_owned_source", "test_sync_source", "test_sync_transport", "test_sync_acquisition",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    roots = [str(mesh / "src"), str(observer), str(observer / "tests")]
    sys.path[:0] = roots
    os.environ["PYTHONPATH"] = os.pathsep.join(roots)
    gc.disable()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
    expected = suite.countTestCases()
    with args.log.open("x") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
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
        "testsRun": result.testsRun, "owningCompactSourceTests": 7, "otherOwningTests": 196,
        "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
        "cyclicGC": "disabled before imports/operations; held errors/handles; no explicit collection",
        "loadedInputs": loaded,
        "scope": "unchanged owning synthetic native Runtime compact IPC/source/Reader tests and components",
        "exclusions": [
            "Native Runtime is a disposable synthetic ServiceState with collection disabled; no populated native provider.",
            "Native head bytes are actual source output; private Reader nonce/native-byte pin and test-owned proof carrier are disclosed fixture scaffolding.",
            "No compact relay/controller/carrier, fixed SSH, immutable installed pair or selected route qualification.",
            "Owner, oracle and Reader ledgers are separate; no aggregate 32/64 MiB, RSS, dense 9-field/2k/predecessor/slow-peer/cold/recovery/CPU qualification.",
            "Observer source pruning is unchanged. Mesh query availability alone does not fix consuming-ref scope retirement.",
            "No source/schema/encoding ID allocation/freeze, artifact/version/install/provider/service/selection/sibling edit or rollout.",
        ],
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips")}))
    assert expected == result.testsRun == 203, (expected, result.testsRun)
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__ == "__main__":
    main()
