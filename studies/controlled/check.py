"""Adversarial trace ownership checks and downstream pure Tmux networking conformance."""

import asyncio
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace import Trace  # noqa: E402

from matrix import qualify  # noqa: E402
from run import case  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import CachedPublisher  # noqa: E402
from mesh_plus.testing import network_suite  # noqa: E402


class TraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_interruption_retires_owned_ipc_resources(self):
        trial = asyncio.create_task(case(SimpleNamespace(rows=32, steps=100, interval=.1), "ipc", 1, "push"))
        await asyncio.sleep(.7)
        trial.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await asyncio.wait_for(trial, 5)
        # Case teardown itself checks native watchers and closes every owned
        # child before propagating cancellation; no background replacement runs.

    def test_workload_mismatch_and_failure_cannot_certify_a_block(self):
        values = [{"status": "passed", "cleanup": True, "position": i, "carrier": carrier,
                   "rows": 32, "steps": 4, "mode": "push", "fanout": 1, "trace": [{"step": 1}],
                   "traffic": {"proofRequests": 4, "received:data": 4},
                   "sourceCountsBefore": {"snapshot": 2}, "sourceCountsAfter": {"snapshot": 6},
                   "consumerAdmissions": [6]} for i, carrier in enumerate(("ssh", "wss", "wss", "ssh"))]
        qualify(values)
        broken = copy.deepcopy(values)
        broken[2]["traffic"]["proofRequests"] = 3
        with self.assertRaisesRegex(ValueError, "matrix_workload_mismatch"):
            qualify(broken)
        broken = copy.deepcopy(values)
        broken[2]["cleanup"] = False
        with self.assertRaisesRegex(ValueError, "matrix_case_not_accepted"):
            qualify(broken)

    def test_steps_are_ordered_complete_and_do_not_renew_receipts(self):
        trace = Trace(64)
        original = copy.deepcopy(trace.frame)
        for step in range(1, 5):
            trace.advance(step)
            self.assertEqual(trace.frame["receipt"], original["receipt"])
            self.assertEqual(trace.frame["snapshot"]["sample"], original["snapshot"]["sample"])
            self.assertEqual(trace.frame["snapshot"]["sessions"][0]["name"], "trace-" + str(step).zfill(5))
        with self.assertRaisesRegex(ValueError, "trace_step_order"):
            trace.advance(6)
        self.assertEqual(trace.step, 4)

    def test_normalization_preserves_logical_changes(self):
        a, b = Trace(4), Trace(4)
        self.assertEqual(a.describe(), b.describe())
        a.advance(1)
        self.assertNotEqual(a.describe()["normalizedFrameSha256"], b.describe()["normalizedFrameSha256"])

    async def test_repeated_proofs_cannot_renew_expired_source(self):
        trace = Trace(4, expired=True)

        class Native:
            async def snapshot(self):
                return trace.frame

            async def watch(self):
                raise AssertionError("not selected")
                yield

        publisher = CachedPublisher("tmux", "beta", "controlled", Native(), profile=trace.profile)
        for _ in range(4):
            proof = await publisher.proof({"nonce": "a" * 32})
            self.assertTrue(all(receipt["remainingMs"] == 0 for receipt in proof["remaining"]))
            self.assertEqual(proof["ownerFrame"]["receipt"], trace.frame["receipt"])
        before = publisher.sequence
        trace.frame["source"]["hostId"] = "forged"
        with self.assertRaisesRegex(ValueError, "invalid retained owner snapshot"):
            await publisher.proof({"nonce": "b" * 32})
        self.assertEqual(publisher.sequence, before)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TraceTests)
    suite.addTests(network_suite(lambda domain: TmuxMeshProfile(), domain="tmux"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit(1)
