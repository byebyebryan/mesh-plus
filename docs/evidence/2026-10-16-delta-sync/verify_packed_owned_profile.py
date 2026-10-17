"""Private fixture ownership only; all Observer tests/assertions stay unchanged.

Each test owner closes its arena after its last store retires. This is not a
production factory, source adapter, native/installed test or resource benchmark.
"""

import argparse
import gc
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh-source", type=Path, required=True)
    parser.add_argument("--observer-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("preserve prior report")
    mesh, observer = args.mesh_source.resolve(), args.observer_source.resolve()
    sys.path[:0] = [str(mesh / "src"), str(observer), str(observer / "tests")]
    from test_mesh_sync_profile import MeshSyncProfileTest

    from mesh_plus.sync._packed_nodes import PackedNodeArena
    from mesh_plus.sync.reconstruction import ReconstructionStore

    # Dictionaries below belong only to the test harness. They distinguish
    # live store ownership from completed audit rows and do not drop or relax
    # any producer assertion. A shared ledger closes after its last store.
    by_store, by_ledger, completed = {}, {}, []
    initialize, close = ReconstructionStore.__init__, ReconstructionStore.close

    def initialize_owned(store, *positional, **keywords):
        initialize(store, *positional, **keywords)
        ledger = store.ledger
        owner = by_ledger.get(ledger)
        if owner is None:
            selected = getattr(ledger, "_packed_nodes", None)
            if selected is not None and selected() is not None:
                raise AssertionError("fixture cannot own an externally selected arena")
            try:
                owner = PackedNodeArena(ledger), set()
            except BaseException:
                close(store)
                raise
            by_ledger[ledger] = owner
        owner[1].add(store)
        by_store[store] = owner

    def close_owned(store):
        close(store)
        owner = by_store.pop(store, None)
        if owner is not None:
            arena, stores = owner
            stores.remove(store)
            if not stores:
                arena.close()
                del by_ledger[arena.ledger]
                completed.append(arena)

    names = unittest.defaultTestLoader.getTestCaseNames(MeshSyncProfileTest)
    precopy = "test_body_reservation_rejection_precedes_detached_copy"
    assert precopy in names
    enabled = gc.isenabled()
    gc.disable()
    collection_calls = 0

    def no_collection(*_positional, **_keywords):
        nonlocal collection_calls
        collection_calls += 1
        raise AssertionError("explicit collection is outside this source check")

    cases, success = [], True
    try:
        with patch.object(ReconstructionStore, "__init__", initialize_owned), patch.object(
                ReconstructionStore, "close", close_owned), patch.object(gc, "collect", no_collection):
            for name in names:
                stream = io.StringIO()
                result = unittest.TextTestRunner(stream=stream, verbosity=1).run(
                    unittest.TestSuite([MeshSyncProfileTest(name)]))
                sys.stderr.write(name + "\n" + stream.getvalue())
                counts = []
                for arena in completed:
                    arena.close()  # explicit repeated close must remain safe
                    ledger = arena.ledger
                    row = {"heap": ledger.used, "heapReserved": ledger.reserved,
                           "encoded": ledger.encoded, "encodedReserved": ledger.encoded_reserved,
                           "pendingUnits": ledger.pending_units, "pendingEncoded": ledger.pending_encoded,
                           "allocationUnits": ledger.units, "liveNodes": arena.live_nodes,
                           "liveMaps": arena._maps, "liveControls": arena._controls}
                    counts.append(row)
                clean = not by_store and not by_ledger and all(
                    all(value == 0 for value in row.values()) for row in counts)
                accepted = (result.wasSuccessful() and not result.skipped and clean and
                            not gc.isenabled() and collection_calls == 0)
                cases.append({"name": name, "testsRun": result.testsRun,
                              "failures": len(result.failures), "errors": len(result.errors),
                              "skips": len(result.skipped), "passed": accepted,
                              "ownerAndLedgerCleanup": counts, "remainingOwnedStores": len(by_store),
                              "remainingOwnedLedgers": len(by_ledger), "gcEnabledAfterCase": gc.isenabled(),
                              "explicitCollectionCalls": collection_calls})
                completed.clear()
                success = success and accepted
                if not clean or gc.isenabled() or collection_calls:
                    break  # retain the failed ownership finding; no fake refund
    finally:
        # A failed test may leave owned fixtures. Cleanup belongs here too,
        # but is not used to turn its preceding failed resource check into pass.
        for store in tuple(by_store):
            close_owned(store)
        if enabled:
            gc.enable()
        else:
            gc.disable()
    result = {"scope": "private unchanged Agent profile tests with explicit per-test store/arena ownership only",
              "gcDisabledDuringTests": all(not case["gcEnabledAfterCase"] for case in cases),
              "gcCollectCalled": bool(collection_calls), "explicitCollectionCalls": collection_calls,
              "profileTestSha256": digest(observer / "tests/test_mesh_sync_profile.py"),
              "privateBackendSha256": digest(mesh / "src/mesh_plus/sync/_packed_nodes.py"),
              "testsDiscovered": len(names), "testsRun": sum(case["testsRun"] for case in cases),
              "skips": sum(case["skips"] for case in cases), "passed": success,
              "excludedTests": [], "testSourceOrAssertionsModified": False, "cases": cases,
              "limits": ["no aggregate resource/RSS/CPU qualification", "no native/installed or transport test",
                         "no revised historical 30-case gate", "no production arena ownership/API change"]}
    raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    with args.output.open("xb") as target:
        target.write(raw)
    print(json.dumps({"passed": success, "tests": result["testsRun"], "skips": result["skips"],
                      "excluded": [], "sha256": hashlib.sha256(raw).hexdigest()}))
    return int(not success)


if __name__ == "__main__":
    raise SystemExit(main())
