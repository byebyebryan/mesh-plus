"""Named one-assertion revision of the historical eight completion relay probes.

The historical probe is unchanged. This revision requires five healthy pinned
refs during a four-transaction batch, rather than observing the old pruning bug.
It runs only the eight relay methods; owning component suites have separate pins.
"""

import argparse
import ast
import asyncio
import gc
import hashlib
import importlib
import inspect
import json
import os
import sys
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

ENV = None
METHOD = "test_material_drain_keeps_original_batch_meta_and_all_pins_until_completion"
HISTORICAL_SHA = "7ffe624538930c634738a5b940da20e58a78306437822f080bee05692463803c"


async def test_material_drain_keeps_original_batch_meta_and_all_pins_until_completion(self):
    case = await self.case(count=4)
    case.writer.hold = case.expected[0][:-1]
    task = case.job()
    await asyncio.wait_for(case.writer.entered.wait(), 2)
    session = case.source.sessions[0]
    self.assertEqual(session.batch.completion.status, "complete")
    self.assertGreaterEqual(case.ledger.encoded_reserved, sum(map(len, case.sent["changes"])))
    self.assertEqual(session.inspect()["ownedBatches"], 1)
    self.assertEqual(session.inspect()["ownedRefs"], 5)
    self.assertEqual(case.received.qsize(), 0)
    case.assert_no_completion()
    case.writer.release.set()
    await task
    lines = [await case.next_line() for _ in range(5)]
    self.assertEqual(ENV.decode(lines[-1])["payload"]["kind"], "control")
    self.assertEqual(session.inspect()["ownedBatches"], 0)


def validate_single_assertion(base):
    original = ast.parse(textwrap.dedent(inspect.getsource(getattr(base.CompletedRelayTests, METHOD))))
    revised = ast.parse(textwrap.dedent(inspect.getsource(globals()[METHOD])))
    target = ast.dump(ast.parse('self.assertEqual(session.inspect()["ownedRefs"], 0)').body[0],
                      include_attributes=False)
    changed = 0
    for node in ast.walk(original):
        if isinstance(node, ast.Expr) and ast.dump(node, include_attributes=False) == target:
            node.value.args[1] = ast.Constant(value=5)
            changed += 1
    assert changed == 1
    assert ast.dump(original, include_attributes=False) == ast.dump(revised, include_attributes=False)


def main():
    global ENV
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--expect-old-pruning", action="store_true")
    args = parser.parse_args()
    mesh, observer = args.mesh.resolve(), args.observer.resolve()
    paths = [str(mesh / "src"), str(observer), str(observer / "tests")]
    sys.path[:0] = paths
    os.environ["PYTHONPATH"] = os.pathsep.join(paths)
    gc.disable()
    base = importlib.import_module("verify_completed_relay")
    base_path = Path(base.__file__).resolve()
    assert hashlib.sha256(base_path.read_bytes()).hexdigest() == HISTORICAL_SHA
    validate_single_assertion(base)
    sync = importlib.import_module("mesh_plus.sync")
    transport = importlib.import_module("mesh_plus.transport")
    canonical = importlib.import_module("mesh_plus.sync.canonical")
    ENV = base.ENV = SimpleNamespace(
        Source=importlib.import_module("agent_observer.sync_source").CachedAgentSyncSource,
        Profile=importlib.import_module("agent_observer.mesh_sync_profile").AgentSyncProfile,
        Codec=importlib.import_module("agent_observer.sync_transport").AgentSyncTransportCodec,
        seeded=importlib.import_module("test_sync_service_delivery").seeded,
        snapshot=importlib.import_module("test_service_runtime").scoped_snapshot,
        Ledger=importlib.import_module("mesh_plus.sync.budget").AllocationLedger,
        ProtocolError=importlib.import_module("mesh_plus.protocol").ProtocolError,
        relay=sync.create_sync_relay, Cache=sync.OwnedSyncCache, Budgets=sync.SyncBudgets,
        binding=sync.source_binding, Line=transport.LineChannel, now=transport.boottime_ms,
        canonical=canonical.canonical, decode=canonical.decode,
    )
    revised = type("CompletedRelayRetirementTests", (base.CompletedRelayTests,), {METHOD: globals()[METHOD]})
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(revised)
    with args.log.open("x") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    assert not gc.isenabled()
    expected = result.testsRun == 8 and not result.errors and not result.skipped
    if args.expect_old_pruning:
        expected = (expected and len(result.failures) == 1 and
                    result.failures[0][0]._testMethodName == METHOD and "0 != 5" in result.failures[0][1])
    else:
        expected = expected and result.wasSuccessful()
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not filename or Path(filename).suffix != ".py":
            continue
        path = Path(filename).resolve()
        for label, root in (("mesh", mesh), ("observer", observer)):
            if path.is_relative_to(root):
                loaded[label + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"python": sys.version.split()[0], "testsRun": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors), "skips": len(result.skipped),
              "expected": "old consuming-ref pruning" if args.expect_old_pruning else "pass",
              "matchesExpected": expected, "singleAssertionAstVerified": True,
              "historicalProbe": {"path": str(base_path), "sha256": HISTORICAL_SHA},
              "meshExport": str(mesh), "observerExport": str(observer), "loadedInputs": loaded,
              "failureDetails": [{"name": case.id(), "traceback": error} for case, error in result.failures],
              "errorDetails": [{"name": case.id(), "traceback": error} for case, error in result.errors],
              "cyclicGC": "disabled before imports and operations; held errors; no explicit collection",
              "cases": base.OUTCOMES,
              "scope": "eight historical expanded source/relay/Reader integration probes with exactly one pinned-ref expectation corrected",
              "exclusions": "No producer acceptance; source final pair/hardened regression, compact lifecycle, aggregate32/64/RSS/CPU/dense2k/recovery/native-provider/fixedSSH/installedpair/rollout remain separate."}
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in ("python", "testsRun", "failures", "errors", "skips", "matchesExpected")}))
    raise SystemExit(0 if expected else 1)


if __name__ == "__main__":
    main()
