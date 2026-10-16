import asyncio
import unittest

from test_sync_cache import BRIDGE, CLOCK, NATIVE_BINDING, REQUEST, CacheProfile, baseline, transaction

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, source_binding
from mesh_plus.sync.acquisition import acquire
from mesh_plus.sync.cache import ResyncRequired
from mesh_plus.sync.canonical import canonical, decode


async def direct(awaitable, deadline):
    return await awaitable


class Endpoint:
    def __init__(self, cache, now):
        self.cache, self.now = cache, now
        raw1, maps1, tag1 = baseline(cache.profile)
        tx2, maps2, tag2 = transaction(cache.profile, maps1, tag1, 2, 2)
        tx3, _, tag3 = transaction(cache.profile, maps2, tag2, 3, 3)
        self.baselines = {i: baseline(cache.profile, i, i)[0] for i in (1, 2, 3)}
        self.baselines[1] = raw1
        self.tags, self.transactions = {1: tag1, 2: tag2, 3: tag3}, {2: tx2, 3: tx3}
        self.generation = 1
        self.moves = self.baseline_delay = self.proof_delay = self.change_delay = 0
        self.resync = self.in_proof = False
        self.calls = []

    async def baseline(self):
        self.calls.append("baseline")
        self.now[0] += self.baseline_delay
        return self.baselines[self.generation]

    async def changes(self, base, *, target, max_transactions, max_bytes):
        self.assert_not_proof()
        self.calls.append("changes")
        self.now[0] += self.change_delay
        if self.resync:
            return ResyncRequired("journal_evicted")
        return tuple(self.transactions[i] for i in range(base.generation + 1, target.generation + 1))

    def assert_not_proof(self):
        if self.in_proof:
            raise AssertionError("body catch-up entered the nonce operation")

    async def proof(self, challenge):
        self.calls.append("proof")
        self.in_proof = True
        try:
            if self.moves:
                self.generation += 1
                self.moves -= 1
            self.now[0] += self.proof_delay
            tag = self.tags[self.generation]
            receipts = decode(self.baselines[self.generation])["tables"]["receipts"]
            native_time = self.now[0] - 8000
            head = {"kind": "head", "descriptor": decode(self.cache.descriptor.native_descriptor),
                    "nativeBindingDigest": tag.binding, "tag": tag.wire(), "challenge": challenge,
                    "ownerClock": {**{name: NATIVE_BINDING[name] for name in
                                      ("bootId", "clockDomain", "uid", "hostScope", "ownerEpoch")},
                                   "boottimeMs": native_time},
                    "originalReceipts": receipts, "cohortHeads": [],
                    "attenuation": [[key, max(0, value["expiresBoottimeMs"] - native_time)]
                                    for key, value in receipts]}
            return canonical({"protocol": "mesh.state-sync/1", "kind": "proof", "descriptor": self.cache.descriptor.wire(),
                              "sourceBinding": decode(self.cache._binding.encoded), "sourceTag": self.cache._tag(tag).wire(),
                              "requestBinding": REQUEST, "challenge": challenge, "bridgeId": BRIDGE,
                              "bridgeClock": {"bootId": "owner-boot", "timeNamespace": "time:1", "boottimeMs": native_time},
                              "head": head, "remaining": head["attenuation"]})
        finally:
            self.in_proof = False


class AcquisitionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = [10000]
        self.profile = CacheProfile()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   request_binding=REQUEST, _now_ms=lambda: self.now[0], _clock=CLOCK)
        self.endpoint = Endpoint(self.cache, self.now)

    def tearDown(self):
        self.cache.close()
        self.assertEqual((self.cache.ledger.used, self.cache.ledger.reserved), (0, 0))

    async def run_acquire(self):
        return await acquire(self.cache, self.endpoint, clock=CLOCK, _now=lambda: self.now[0], _until=direct)

    async def test_cold_then_unchanged_acquisition_uses_no_second_baseline(self):
        first = await self.run_acquire()
        tag = first.view.tag
        self.assertEqual((first.baselines, first.proofs, first.transactions), (1, 1, 0))
        second = await self.run_acquire()
        self.assertEqual((second.baselines, second.proofs, second.transactions), (0, 1, 0))
        self.assertEqual(tag, second.view.tag)
        self.assertEqual(self.endpoint.calls, ["baseline", "proof", "proof"])

    async def test_moved_head_catches_up_unconfirmed_baseline_separately_once(self):
        self.endpoint.moves = 1
        result = await self.run_acquire()
        self.assertEqual((result.baselines, result.transactions, result.proofs, result.moved_heads), (1, 1, 2, 1))
        self.assertEqual(result.view.tag.native, self.endpoint.tags[2])
        self.assertEqual(self.endpoint.calls, ["baseline", "proof", "changes", "proof"])

    async def test_second_move_fails_without_another_body_retry(self):
        self.endpoint.moves = 2
        with self.assertRaisesRegex(ProtocolError, "sync_head_moved_again"):
            await self.run_acquire()
        self.assertEqual(self.endpoint.calls.count("changes"), 1)
        self.assertEqual(self.endpoint.calls.count("proof"), 2)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    async def test_evicted_chain_uses_explicit_separate_baseline(self):
        self.endpoint.moves, self.endpoint.resync = 1, True
        result = await self.run_acquire()
        self.assertEqual((result.baselines, result.transactions, result.proofs), (2, 0, 2))
        self.assertEqual(self.endpoint.calls, ["baseline", "proof", "changes", "baseline", "proof"])

    async def test_catchup_keeps_original_absolute_acquisition_deadline(self):
        self.endpoint.moves, self.endpoint.baseline_delay, self.endpoint.proof_delay = 1, 10000, 1500
        self.endpoint.change_delay = 4000
        with self.assertRaisesRegex(ProtocolError, "sync_acquisition_deadline"):
            await self.run_acquire()
        self.assertEqual(self.endpoint.calls, ["baseline", "proof", "changes"])

    async def test_validation_cannot_publish_after_absolute_deadline(self):
        self.endpoint.baseline_delay = 14500
        self.profile.head_callback = lambda ctx: self.now.__setitem__(0, self.now[0] + 600)
        with self.assertRaisesRegex(ProtocolError, "sync_acquisition_deadline"):
            await self.run_acquire()
        self.assertIsNone(self.cache.store.current)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    async def test_compact_proof_deadline_is_independent_of_fifteen_seconds(self):
        self.endpoint.proof_delay = 2000
        with self.assertRaisesRegex(ProtocolError, "sync_proof_deadline"):
            await self.run_acquire()

    async def test_cancellation_retires_owned_operation_and_revokes(self):
        entered, cleaned, blocked = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def wait_baseline():
            entered.set()
            try:
                await blocked.wait()
            finally:
                cleaned.set()

        self.endpoint.baseline = wait_baseline
        job = asyncio.create_task(self.run_acquire())
        await entered.wait()
        with self.assertRaisesRegex(ProtocolError, "sync_acquisition_in_progress"):
            await self.run_acquire()
        job.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await job
        self.assertTrue(cleaned.is_set())
        self.assertIsNone(self.cache._acquisition)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    async def test_endpoint_error_cannot_export_private_acquisition_frames(self):
        original = ValueError("private endpoint error with arbitrary details")

        async def reject():
            private_input = self.endpoint.baselines[1]
            self.assertTrue(private_input)
            raise original

        self.endpoint.baseline = reject
        try:
            await self.run_acquire()
        except ProtocolError as error:
            self.assertEqual(str(error), "sync_admission_rejected")
            trace, names = error.__traceback__, []
            while trace is not None:
                names.append(trace.tb_frame.f_code.co_name)
                self.assertNotIn("private_input", trace.tb_frame.f_locals)
                trace = trace.tb_next
            self.assertNotIn("baseline", names)
            self.assertNotIn("reject", names)
            self.assertIsNone(error.__context__)
        else:
            self.fail("endpoint error was admitted")
        self.assertIsNone(original.__traceback__)
        self.assertIsNone(self.cache._acquisition)

    async def test_warm_cancellation_revokes_before_repeated_cancel_cleanup_finishes(self):
        result = await self.run_acquire()
        view = result.view
        entered, cleaning, release, blocked = (asyncio.Event() for _ in range(4))

        async def blocked_proof(challenge):
            entered.set()
            try:
                await blocked.wait()
            finally:
                cleaning.set()
                await release.wait()

        self.endpoint.proof = blocked_proof
        job = asyncio.create_task(self.run_acquire())
        await entered.wait()
        job.cancel()
        await cleaning.wait()
        with self.assertRaises(ProtocolError):
            view.context(self.now[0], CLOCK)
        job.cancel()
        await asyncio.sleep(0)
        self.assertFalse(job.done())
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await job
        self.assertIsNone(self.cache._acquisition)
        self.assertEqual(self.cache.ledger.reserved, 0)


if __name__ == "__main__":
    unittest.main()
