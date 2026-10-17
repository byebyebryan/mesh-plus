import asyncio
import gc
import unittest
from unittest.mock import patch

from test_sync_cache import CLOCK, IDENTITY, REQUEST, CacheProfile, baseline, proof, transaction

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import InputOwner, OwnedInputRef, OwnedSyncCache, source_binding
from mesh_plus.sync.budget import AllocationLedger


class InputTests(unittest.TestCase):
    def setUp(self):
        self.profile = CacheProfile()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   request_binding=REQUEST, _now_ms=lambda: 10000, _clock=CLOCK)
        self.inputs = self.cache.input_owner()

    def tearDown(self):
        self.cache.close()
        self.assertEqual((self.cache.ledger.used, self.cache.ledger.reserved,
                          self.cache.ledger.encoded, self.cache.ledger.encoded_reserved), (0, 0, 0, 0))

    def seal(self, raw, inputs=None):
        inputs = self.inputs if inputs is None else inputs
        with inputs.reserve(inputs.buffer_heap(len(raw)), encoded_bytes=len(raw)) as receive:
            return receive.seal(raw)

    def test_seal_splits_credit_without_refunding_live_scratch_or_copy(self):
        raw = b"input"
        cost = self.inputs.buffer_heap(len(raw))
        receive = self.inputs.reserve(cost + 4096, encoded_bytes=2 * len(raw))
        before = self.cache.ledger.inspect()
        ref = receive.seal(raw)
        self.assertEqual((receive.heap_bytes, receive.encoded_bytes), (4096, len(raw)))
        after = self.cache.ledger.inspect()
        self.assertEqual((before["reservedBytes"], before["reservedEncodedBytes"]),
                         (after["reservedBytes"], after["reservedEncodedBytes"]))
        ref.close()
        self.assertEqual(self.cache.ledger.encoded_reserved, len(raw))
        receive.close()

    def test_consuming_baseline_and_proof_still_performs_independent_admission(self):
        raw, _, _ = baseline(self.profile)
        ref = self.seal(raw)
        candidate = self.cache.admit_baseline(ref)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            self.cache.admit_baseline(ref)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()
        head = self.seal(proof(self.cache, candidate))
        view = self.cache.confirm(candidate, head, CLOCK)
        self.assertEqual(view.tag, candidate.tag)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            _ = head.nbytes

    def test_malformed_and_duplicate_header_rejection_consumes_storage(self):
        raw, _, _ = baseline(self.profile)
        for invalid in (b'{"kind":', raw.replace(b'{"', b'{"kind":"baseline","', 1)):
            with self.subTest(invalid=invalid[:30]):
                ref = self.seal(invalid)
                with self.assertRaises(ProtocolError) as saved:
                    self.cache.admit_baseline(ref)
                with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                    _ = ref.nbytes
                self.assertEqual(self.cache.ledger.encoded_reserved, 0)
                self.assertIsNone(saved.exception.__context__)

    def test_four_transaction_batch_consumes_all_inputs(self):
        raw, maps, tag = baseline(self.profile)
        candidate = self.cache.admit_baseline(self.seal(raw))
        refs = []
        for generation in range(2, 6):
            raw, maps, tag = transaction(self.profile, maps, tag, generation, generation)
            refs.append(self.seal(raw))
        result = self.cache.stage_batch(candidate.tag, tuple(refs))
        self.assertEqual(result.tag.native.generation, 5)
        self.assertEqual(self.cache.ledger.encoded_reserved, 0)
        for ref in refs:
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                _ = ref.nbytes

    def test_failed_batch_retires_unvisited_members(self):
        raw, _, _ = baseline(self.profile)
        candidate = self.cache.admit_baseline(self.seal(raw))
        refs = tuple(self.seal(b"invalid") for _ in range(4))
        with self.assertRaises(ProtocolError):
            self.cache.stage_batch(candidate.tag, refs)
        self.assertEqual(self.cache.ledger.encoded_reserved, 0)

    def test_foreign_alias_cannot_consume_or_over_release_other_storage(self):
        other = OwnedSyncCache(self.profile, source_binding("fixture", "other", self.profile.descriptor),
                              ledger=self.cache.ledger)
        try:
            sibling = self.seal(b"sibling", other.input_owner())
            keep = self.seal(b"keep")
            before = self.cache.ledger.encoded_reserved
            with self.assertRaisesRegex(ProtocolError, "sync_input_owner"):
                self.cache.stage(sibling)
            self.assertEqual(self.cache.ledger.encoded_reserved, before - len(b"sibling"))
            self.assertEqual(keep.nbytes, 4)
            sibling.close()
            self.assertEqual(keep.nbytes, 4)
            keep.close()
        finally:
            other.close()

    def test_disconnect_revokes_handles_but_preserves_active_receive_credit(self):
        receive = self.inputs.reserve(8192, encoded_bytes=1024)
        ref = self.seal(b"sealed")
        self.cache.disconnect()
        self.assertEqual(self.cache.ledger.encoded_reserved, 1024)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            receive.seal(b"late")
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            _ = ref.nbytes
        self.cache.close()
        self.assertGreater(self.cache.ledger.reserved, 8192)
        receive.close()
        self.assertEqual(self.cache.ledger.reserved, 0)

    def test_input_owner_close_revokes_views_and_preserves_sibling_and_receive_credit(self):
        enabled = gc.isenabled()
        gc.disable()
        other_profile = CacheProfile()
        other = OwnedSyncCache(other_profile, source_binding("fixture", "sibling", other_profile.descriptor),
                               ledger=self.cache.ledger, request_binding=REQUEST,
                               _now_ms=lambda: 10000, _clock=CLOCK)
        receive = None
        try:
            raw, _, _ = baseline(self.profile)
            candidate = self.cache.admit_baseline(self.seal(raw))
            view = self.cache.confirm(candidate, self.seal(proof(self.cache, candidate)), CLOCK)
            retained = view.lookup("records", IDENTITY)
            other_raw, _, _ = baseline(other_profile)
            other_candidate = other.admit_baseline(other_raw)
            sibling_view = other.confirm(other_candidate, proof(other, other_candidate), CLOCK)
            receive = self.inputs.reserve(8192, encoded_bytes=1024)
            ref = self.seal(b"sealed")
            self.inputs.close()
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                self.cache.acquire()
            with self.assertRaises(ProtocolError):
                _ = view.tag
            with self.assertRaises(ProtocolError):
                _ = candidate.tag
            with self.assertRaises(ProtocolError):
                retained.materialize()
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                _ = ref.nbytes
            for action in (lambda: receive.resize(1), lambda: receive.seal(b"late")):
                with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                    action()
            self.assertEqual(self.cache.ledger.encoded_reserved, 1024)
            self.assertEqual(sibling_view.tag, other_candidate.tag)
            self.assertEqual(other.acquire().tag, other_candidate.tag)
            replacement = self.cache.input_owner()
            self.assertIsNot(replacement, self.inputs)
            candidate = self.cache.admit_baseline(self.seal(raw, replacement))
            view = self.cache.confirm(candidate, self.seal(proof(self.cache, candidate), replacement), CLOCK)
            self.inputs.close()
            self.inputs.close()
            self.assertEqual(view.tag, candidate.tag)
            self.assertEqual(other.acquire().tag, other_candidate.tag)
            self.assertEqual(self.cache.ledger.encoded_reserved, 1024)
        finally:
            if receive is not None:
                receive.close()
            other.close()
            if enabled:
                gc.enable()

    def test_input_owner_close_during_head_callback_cannot_publish(self):
        raw, _, _ = baseline(self.profile)
        candidate = self.cache.admit_baseline(self.seal(raw))
        head = self.seal(proof(self.cache, candidate))
        inputs = self.inputs
        self.profile.head_callback = lambda ctx: inputs.close()
        with self.assertRaises(ProtocolError) as rejected:
            self.cache.confirm(candidate, head, CLOCK)
        self.assertIsNone(rejected.exception.__context__)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()
        self.assertEqual(self.cache.ledger.encoded_reserved, 0)

    def test_resize_is_atomic_when_capacity_is_exhausted(self):
        receive = self.inputs.reserve(100, encoded_bytes=20)
        ledger = self.cache.ledger
        blocker = ledger.reserve(ledger.maximum - ledger.used - ledger.reserved)
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                receive.resize(101, encoded_bytes=21)
            self.assertEqual((receive.heap_bytes, receive.encoded_bytes), (100, 20))
        finally:
            blocker.close()
            receive.close()

    def test_at_limit_rejection_precedes_receive_allocation(self):
        ledger = self.cache.ledger
        blocker = ledger.reserve(ledger.maximum - ledger.used - ledger.reserved)
        received = []
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                with self.inputs.reserve(65536, encoded_bytes=65536):
                    received.append(bytes(65536))
            self.assertEqual(received, [])
        finally:
            blocker.close()

    def test_first_owner_rejection_precedes_owner_control_allocation(self):
        other = OwnedSyncCache(self.profile, source_binding("fixture", "first", self.profile.descriptor))
        ledger = other.ledger
        blocker = ledger.reserve(ledger.maximum - ledger.used - ledger.reserved)
        try:
            with patch("mesh_plus.sync.inputs.InputOwner") as constructor:
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                    other.input_owner()
                constructor.assert_not_called()
        finally:
            blocker.close()
            other.close()

    def test_failed_seal_preserves_original_credit_and_exact_bytes_rule(self):
        receive = self.inputs.reserve(10, encoded_bytes=10)
        before = self.cache.ledger.inspect()
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_input_credit"):
                receive.seal(b"raw")
            with self.assertRaisesRegex(ProtocolError, "sync_input_bytes"):
                receive.seal(bytearray(b"raw"))
            after = self.cache.ledger.inspect()
            self.assertEqual((before["reservedBytes"], before["reservedEncodedBytes"]),
                             (after["reservedBytes"], after["reservedEncodedBytes"]))
        finally:
            receive.close()

    def test_control_slot_bound_rejects_before_mint_and_keeps_existing_credit(self):
        size = self.inputs.buffer_heap(1)
        leases = [self.inputs.reserve(2 * size, encoded_bytes=2)]
        leases.extend(self.inputs.reserve(0) for _ in range(62))
        refs = []
        try:
            refs.append(leases[0].seal(b"x"))  # 63 leases plus one sealed ref
            before = self.cache.ledger.inspect()
            with self.assertRaisesRegex(ProtocolError, "sync_input_slots"):
                leases[0].seal(b"y")
            with self.assertRaisesRegex(ProtocolError, "sync_input_slots"):
                self.inputs.reserve(0)
            after = self.cache.ledger.inspect()
            self.assertEqual((before["reservedBytes"], before["reservedEncodedBytes"]),
                             (after["reservedBytes"], after["reservedEncodedBytes"]))
            refs[0].close()
            refs.append(leases[0].seal(b"y"))
        finally:
            for ref in refs:
                ref.close()
            for lease in leases:
                lease.close()

    def test_failed_proof_consume_retires_input_before_returning_error(self):
        raw, _, _ = baseline(self.profile)
        candidate = self.cache.admit_baseline(self.seal(raw))
        ref = self.seal(proof(self.cache, candidate))
        with self.assertRaisesRegex(ProtocolError, "sync_candidate_retired"):
            self.cache.confirm(object(), ref, CLOCK)
        self.assertEqual(self.cache.ledger.encoded_reserved, 0)
        with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
            _ = ref.nbytes

    def test_callback_disconnect_cannot_leave_a_surviving_publication(self):
        class DisconnectProfile(CacheProfile):
            def admit_baseline(self, ctx):
                patch = super().admit_baseline(ctx)
                self.cache.disconnect()
                return patch

        profile = DisconnectProfile()
        other = OwnedSyncCache(profile, source_binding("fixture", "callback", profile.descriptor))
        profile.cache = other
        try:
            raw, _, _ = baseline(profile)
            ref = self.seal(raw, other.input_owner())
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                other.admit_baseline(ref)
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                other.acquire()
            self.assertEqual(other.ledger.encoded_reserved, 0)
        finally:
            other.close()

    def test_cache_mint_and_no_gc_close(self):
        with self.assertRaisesRegex(ProtocolError, "sync_input_mint"):
            InputOwner(self.cache)
        with self.assertRaisesRegex(ProtocolError, "sync_input_mint"):
            OwnedInputRef(self.inputs)
        enabled = gc.isenabled()
        gc.disable()
        try:
            ref = self.seal(b"retire")
            del ref
            self.assertEqual(self.cache.ledger.encoded_reserved, 0)
        finally:
            if enabled:
                gc.enable()

    def test_shared_ledger_reservation_caps_apply_across_two_alias_owners(self):
        ledger = AllocationLedger(1 << 20, encoded_maximum=16384)
        full = OwnedSyncCache(self.profile, source_binding("fixture", "full", self.profile.descriptor), ledger=ledger)
        active = OwnedSyncCache(self.profile, source_binding("fixture", "active", self.profile.descriptor), ledger=ledger)
        try:
            lease = full.input_owner().reserve(8192, encoded_bytes=ledger.encoded_maximum - ledger.encoded)
            try:
                with self.assertRaisesRegex(ProtocolError, "sync_encoded_capacity"):
                    active.input_owner().reserve(8192, encoded_bytes=1)
            finally:
                lease.close()
        finally:
            full.close()
            active.close()
        self.assertEqual((ledger.used, ledger.reserved, ledger.encoded_reserved), (0, 0, 0))


class IntakeCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_paused_receive_and_repeated_cancel_keep_credit_until_cleanup(self):
        profile = CacheProfile()
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor))
        inputs = cache.input_owner()
        entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def intake():
            receive = inputs.reserve(65536, encoded_bytes=32768)
            try:
                entered.set()
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                while not release.is_set():
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        pass
                receive.close()

        task = asyncio.create_task(intake())
        try:
            await entered.wait()
            task.cancel()
            await cleaning.wait()
            cache.disconnect()
            task.cancel()
            await asyncio.sleep(0)
            self.assertGreaterEqual(cache.ledger.reserved, 65536)
            self.assertEqual(cache.ledger.encoded_reserved, 32768)
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            cache.close()
        self.assertEqual((cache.ledger.used, cache.ledger.reserved, cache.ledger.encoded_reserved), (0, 0, 0))
