import asyncio
import gc
import unittest
import weakref
from unittest.mock import patch

from test_sync_cache import CLOCK, IDENTITY, REQUEST, CacheProfile, baseline, proof, transaction

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import InputOwner, OwnedInputRef, OwnedSyncCache, RelayInputRef, source_binding
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.inputs import input_bytes
from mesh_plus.sync.reconstruction import MaterialRoot


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

    def test_ref_retirement_query_keeps_healthy_pin_and_revoked_physical_credit(self):
        enabled = gc.isenabled()
        gc.disable()
        owner, ledger = self.inputs, self.cache.ledger
        receive = owner.reserve(4096, encoded_bytes=256)
        ref = self.seal(b"x" * 1753)
        try:
            consumed = self.seal(b"successful consume")
            with input_bytes(self.cache, consumed) as (raw, _):
                self.assertIs(owner.ref_is_retired(consumed), False)
                raw = None
            self.assertIs(owner.ref_is_retired(consumed), True)
            failed = self.seal(b"invalid native material")
            with self.assertRaises(ProtocolError) as failed_admission:
                self.cache.admit_baseline(failed)
            self.assertIs(owner.ref_is_retired(failed), True)
            self.assertIsNone(failed_admission.exception.__context__)
            self.assertIs(owner.ref_is_retired(ref), False)
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired") as saved:
                with input_bytes(self.cache, ref) as (raw, owned):
                    self.assertTrue(owned)
                    self.assertEqual(len(raw), 1753)
                    with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                        _ = ref.nbytes
                    before = ledger.inspect()
                    for _ in range(100):
                        self.assertIs(owner.ref_is_retired(ref), False)
                    self.assertEqual(ledger.inspect(), before)
                    ref.close()
                    self.assertEqual(ledger.encoded_reserved, 1753 + 256)
                    before = ledger.inspect()
                    self.assertIs(owner.ref_is_retired(ref), True)
                    self.assertEqual(ledger.inspect(), before)
                    owner.close()
                    owner.close()
                    self.assertIs(owner.ref_is_retired(ref), True)
                    self.assertEqual(ledger.encoded_reserved, 1753 + 256)
                    raw = None  # Drop the test consumer's alias before pin unwind/refund.
            self.assertIsNone(saved.exception.__context__)
            self.assertEqual(ledger.encoded_reserved, 256)
            self.assertIs(owner.ref_is_retired(ref), True)
            replacement = self.cache.input_owner()
            keep = self.seal(b"replacement", replacement)
            before = ledger.inspect()
            for query, value in ((replacement, ref), (owner, keep)):
                with self.assertRaisesRegex(ProtocolError, "sync_input_owner"):
                    query.ref_is_retired(value)
            self.assertEqual(ledger.inspect(), before)
            owner.close()
            self.assertIs(replacement.ref_is_retired(keep), False)
            keep.close()
        finally:
            receive.close()
            if enabled:
                gc.enable()

    def test_ref_retirement_wrong_handles_do_not_mutate_shared_siblings(self):
        other = OwnedSyncCache(self.profile, source_binding("fixture", "other", self.profile.descriptor),
                               ledger=self.cache.ledger)
        errors = []
        malformed = OwnedInputRef.__new__(OwnedInputRef)
        wrong_role = RelayInputRef.__new__(RelayInputRef)
        try:
            own = self.seal(b"own")
            another = self.seal(b"another")
            sibling_owner = other.input_owner()
            sibling = self.seal(b"sibling", sibling_owner)
            before = self.cache.ledger.inspect()
            for value in (None, b"raw", object(), sibling, malformed, wrong_role):
                with self.assertRaisesRegex(ProtocolError, "sync_input_owner") as rejected:
                    self.inputs.ref_is_retired(value)
                errors.append(rejected.exception)
                self.assertEqual(self.cache.ledger.inspect(), before)
                self.assertIs(self.inputs.ref_is_retired(own), False)
                self.assertIs(sibling_owner.ref_is_retired(sibling), False)
                self.assertEqual((own.nbytes, sibling.nbytes), (3, 7))
            key = own._key
            try:
                own._key = another._key
                with self.assertRaisesRegex(ProtocolError, "sync_input_owner") as rejected:
                    self.inputs.ref_is_retired(own)
                errors.append(rejected.exception)
                own._key = []
                with self.assertRaisesRegex(ProtocolError, "sync_input_owner") as rejected:
                    self.inputs.ref_is_retired(own)
                errors.append(rejected.exception)
            finally:
                own._key = key
            self.assertEqual(self.cache.ledger.inspect(), before)
            self.assertTrue(all(error.__context__ is None for error in errors))
            class Payload:
                pass

            def caller_failure():
                payload = Payload()
                marker = weakref.ref(payload)
                try:
                    raise ValueError("caller error")
                except ValueError as error:
                    return error, marker

            parent, marker = caller_failure()
            parent.__cause__ = RuntimeError("caller cause")
            try:
                raise parent
            except ValueError:
                caller_trace, caller_cause = parent.__traceback__, parent.__cause__
                with self.assertRaisesRegex(ProtocolError, "sync_input_owner") as rejected:
                    self.inputs.ref_is_retired(None)
                errors.append(rejected.exception)
                self.assertIsNone(rejected.exception.__context__)
                self.assertIs(parent.__traceback__, caller_trace)
                self.assertIs(parent.__cause__, caller_cause)
                self.assertIsNotNone(marker())
            finally:
                parent.__traceback__ = parent.__cause__ = None
                caller_trace = None
            own.close()
            another.close()
            sibling.close()
        finally:
            other.close()

    def test_ref_retirement_query_runs_no_semantic_or_allocation_callbacks(self):
        raw, _, _ = baseline(self.profile)
        candidate = self.cache.admit_baseline(self.seal(raw))
        view = self.cache.confirm(candidate, self.seal(proof(self.cache, candidate)), CLOCK)
        context = view.context(10000, CLOCK)
        ref = self.seal(b"opaque unvalidated bytes")
        before, calls = self.cache.ledger.inspect(), self.profile.head_calls
        with (patch.object(self.inputs, "_check", side_effect=AssertionError("owner check")),
              patch.object(self.cache, "_check", side_effect=AssertionError("cache check")),
              patch.object(self.profile, "check_head", side_effect=AssertionError("profile callback")),
              patch.object(self.cache.ledger, "reserve", side_effect=AssertionError("reservation")),
              patch.object(self.cache.ledger, "release", side_effect=AssertionError("material reclamation"))):
            self.assertIs(self.inputs.ref_is_retired(ref), False)
        self.assertEqual(self.cache.ledger.inspect(), before)
        self.assertEqual(self.profile.head_calls, calls)
        self.assertEqual(view.context(10000, CLOCK), context)
        self.assertEqual(self.cache.acquire().tag, view.tag)
        ref.close()
        before = self.cache.ledger.inspect()
        self.assertIs(self.inputs.ref_is_retired(ref), True)
        self.assertEqual(self.cache.ledger.inspect(), before)

    def test_ref_retirement_has_no_terminal_history_or_held_error_owner_cycle(self):
        enabled = gc.isenabled()
        gc.disable()
        retained = []
        try:
            for _ in range(70):
                ref = self.seal(b"terminal")
                ref.close()
                retained.append(ref)
                before = self.cache.ledger.inspect()
                self.assertIs(self.inputs.ref_is_retired(ref), True)
                self.assertEqual(self.cache.ledger.inspect(), before)
                self.assertEqual(len(self.inputs._buffers), 0)
            self.inputs.close()
            self.assertTrue(all(self.inputs.ref_is_retired(ref) is True for ref in retained))

            def held_failure():
                profile = CacheProfile()
                cache = OwnedSyncCache(profile, source_binding("fixture", "error", profile.descriptor))
                owner = cache.input_owner()
                ref = self.seal(b"retained", owner)
                refs = (weakref.ref(owner), weakref.ref(cache), weakref.ref(cache.ledger))
                saved = None
                try:
                    owner.ref_is_retired(None)
                except ProtocolError as error:
                    saved = error
                owner.close()
                cache.close()
                owner = cache = None
                return refs, saved, ref

            refs, saved, ref = held_failure()
            self.assertEqual(str(saved), "sync_input_owner")
            self.assertIsNone(saved.__context__)
            self.assertTrue(all(item() is None for item in refs))
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                _ = ref.nbytes
            self.assertFalse(gc.isenabled())
        finally:
            if enabled:
                gc.enable()

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
            self.assertTrue(view.context(10000, CLOCK)["receipts"][0]["current"])
            self.assertTrue(self.cache.acquire().context(10000, CLOCK)["receipts"][0]["current"])
            retained = view.lookup("records", IDENTITY)
            other_raw, _, _ = baseline(other_profile)
            other_candidate = other.admit_baseline(other_raw)
            sibling_view = other.confirm(other_candidate, proof(other, other_candidate), CLOCK)
            receive = self.inputs.reserve(8192, encoded_bytes=1024)
            ref = self.seal(b"sealed")
            late_proof = proof(self.cache, candidate)
            late_owned_proof = self.seal(late_proof)
            self.inputs.close()
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                self.cache.acquire()
            with self.assertRaises(ProtocolError):
                _ = view.tag
            with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
                view.context(10000, CLOCK)
            with self.assertRaises(ProtocolError):
                _ = candidate.tag
            with self.assertRaises(ProtocolError):
                retained.materialize()
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                _ = ref.nbytes
            with self.assertRaisesRegex(ProtocolError, "sync_candidate_retired"):
                self.cache.confirm(candidate, late_proof, CLOCK)
            with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                self.cache.confirm(candidate, late_owned_proof, CLOCK)
            for action in (lambda: receive.resize(1), lambda: receive.seal(b"late")):
                with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                    action()
            self.assertEqual(self.cache.ledger.encoded_reserved, 1024)
            self.assertEqual((receive.heap_bytes, receive.encoded_bytes), (8192, 1024))
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
            self.cache.disconnect()
            with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
                view.context(10000, CLOCK)
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                self.cache.acquire()
            renewed = self.cache.input_owner()
            self.assertIsNot(renewed, replacement)
            candidate = self.cache.admit_baseline(self.seal(raw, renewed))
            view = self.cache.confirm(candidate, self.seal(proof(self.cache, candidate), renewed), CLOCK)
            replacement.close()
            self.assertTrue(view.context(10000, CLOCK)["receipts"][0]["current"])
            self.assertTrue(other.acquire().context(10000, CLOCK)["receipts"][0]["current"])
            self.assertEqual((receive.heap_bytes, receive.encoded_bytes), (8192, 1024))
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

    def test_head_close_keeps_live_material_charged_until_material_cleanup(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            for owned in (False, True):
                for close in ("owner", "disconnect"):
                    with self.subTest(owned=owned, close=close):
                        self.check_head_retirement(owned, close)
        finally:
            if enabled:
                gc.enable()

    def check_head_retirement(self, owned, close):
        cache, ledger = self.cache, self.cache.ledger
        inputs = cache.input_owner()
        raw, _, _ = baseline(self.profile)
        candidate = cache.admit_baseline(self.seal(raw, inputs))
        material = cache.store.candidate
        head = proof(cache, candidate)
        supplied = self.seal(head, inputs) if owned else head
        release = ledger.release
        material_releases, callback_counts = [], []

        def audit(value):
            if isinstance(value, MaterialRoot):
                material_releases.append(value)
            return release(value)

        def callback(ctx):
            # At this point the physical root is on both confirmation frames.
            used, encoded = ledger.used, ledger.encoded
            (inputs.close if close == "owner" else cache.disconnect)()
            callback_counts.append((used, encoded, ledger.used, ledger.encoded))
            self.assertEqual(material_releases, [])
            self.assertIs(cache.store.candidate, material)
            self.assertIn(id(material), ledger._roots)
            if owned:
                # Revocation rejects public use while the consumer still owns
                # the same raw proof on its active confirmation frames.
                self.assertEqual(ledger.encoded_reserved, len(head))
                with self.assertRaisesRegex(ProtocolError, "sync_input_retired"):
                    _ = supplied.nbytes
            with self.assertRaises(ProtocolError):
                _ = candidate.tag
            with self.assertRaises(ProtocolError):
                ctx.view.lookup("records", IDENTITY).materialize()
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                cache.acquire()
            # Revocation may release small capability controls, but the full
            # material allocation cannot become reusable callback scratch.
            material_cost = ledger.entries[id(material)].cost
            free = ledger.maximum - ledger.used - ledger.reserved
            blocker = ledger.reserve(free)
            try:
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                    ledger.reserve(material_cost)
            finally:
                blocker.close()
            with self.assertRaisesRegex(ProtocolError, "sync_reentrant_admission"):
                cache.stage(b"invalid")

        self.profile.head_callback = callback
        with patch.object(ledger, "release", side_effect=audit):
            with self.assertRaises(ProtocolError) as rejected:
                cache.confirm(candidate, supplied, CLOCK)
            # Includes owned-input failure cleanup after check_head has unwound.
            self.assertEqual(material_releases, [])
        self.assertIsNone(rejected.exception.__context__)
        self.assertEqual(len(callback_counts), 1)
        self.assertIs(cache.store.candidate, material)
        self.assertIn(id(material), ledger._roots)
        self.assertEqual(ledger.encoded_reserved, 0)
        self.profile.head_callback = None
        # The next material replacement is an allowed reclamation boundary.
        fresh = cache.admit_baseline(raw)
        self.assertNotIn(id(material), ledger._roots)
        cache.confirm(fresh, proof(cache, fresh), CLOCK)

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
