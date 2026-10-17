"""Run committed Observer compact component checks against explicit Mesh source.

Synthetic owner/Reader fixtures only; this is not populated delivery, aggregate
capacity, performance, an installed pair or a release-selection check.
"""

import argparse
import gc
import hashlib
import json
import sys
import unittest
from pathlib import Path

MODULES = (
    "test_mesh_sync_codec", "test_sync_compact_plan", "test_sync_compact",
    "test_sync_compact_transport", "test_mesh_sync_profile", "test_mesh_sync_read",
    "test_sync_owned_source", "test_sync_source", "test_sync_transport", "test_sync_acquisition",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    # Child pure-import probes inherit the same explicit PYTHONPATH from the
    # caller. No editable checkout, installed fallback or sibling test imports.
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    gc.disable()
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or Path(filename).suffix != ".py":
            continue
        path = Path(filename).resolve()
        for label, root in (("mesh", mesh), ("observer", observer)):
            if path.is_relative_to(root):
                loaded[label + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert not gc.isenabled()
    report = {
        "python": sys.version.split()[0], "modules": list(MODULES),
        "meshExport": str(mesh), "observerExport": str(observer),
        "testsRun": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "cyclicGC": "disabled throughout imports/selected operations; no explicit collection",
        "loadedInputs": loaded,
        "scope": "actual Agent compact codec/profile with synthetic raw/root/owner/Reader fixtures, plus parser/facade/legacy source component checks",
        "exclusions": [
            "No native compact serializer/journal/source dispatch or original native request/control changes.",
            "Harness/raw fixture/oracle/import/test schema storage is outside per-operation ledgers; no aggregate32/64MiB, RSS, dense/2000-row or performance acceptance.",
            "No real producer, populated IPC/fixedSSH, controller grammar, completed-source seam, installed pair, schema/encoding allocation or selection/rollout.",
            "Fresh Reader proof helpers and synthetic native fixture cleanup use disclosed owning test-only scaffolding; runtime codec uses public Mesh APIs.",
        ],
    }
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, sort_keys=True)
        output.write("\n")
    assert result.testsRun == 171, result.testsRun
    raise SystemExit(0 if result.wasSuccessful() and not result.skipped else 1)


if __name__ == "__main__":
    main()
