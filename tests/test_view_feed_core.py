"""Focused independent tests for the complete-view feed core."""

import copy
import gc
import unittest
import weakref
from unittest.mock import patch

from publisher_fixture import Publisher
from sdk_fixture import Profile

from mesh_plus.protocol import ProtocolError
from mesh_plus.view_feed import FeedBudget, FeedEncoder, FeedLimits, FeedReceiver


class ViewFeedCoreTests(unittest.TestCase):
    def setUp(self):
        self.was_gc_enabled = gc.isenabled()
        gc.disable()
        self.addCleanup(lambda: gc.enable() if self.was_gc_enabled else None)

    @staticmethod
    def expand_fixture(fixture, count=3):
        sessions = fixture.frame["snapshot"]["sessions"]
        first = copy.deepcopy(sessions[0])
        for index in range(2, count + 1):
            row = copy.deepcopy(first)
            row["sessionId"] = f"${index + 1}"
            row["createdAt"] += index
            row["activityAt"] += index
            row["name"] = f"session-{index}"
            sessions.append(row)

    @staticmethod
    def receiver(profile, *, budget=None, limits=None):
        return FeedReceiver(profile, profile.bind("local", "default"), selector={},
                            budget=budget, limits=limits)

    def test_first_full_replacement_can_admit_coalesced_later_revision(self):
        sender_profile = Profile("tmux")
        sender_codec = sender_profile.bind("local", "default")
        fixture = Publisher("tmux", "local")
        encoder = FeedEncoder(sender_profile, sender_codec, selector={})
        self.addCleanup(encoder.close)

        messages = []
        for revision in range(1, 5):
            if revision > 1:
                fixture.frame["viewRevision"] += 1
                fixture.frame["snapshot"]["sessions"][0]["name"] += "!"
            message = encoder.encode(fixture.wrap())
            self.assertIsNotNone(message)
            self.assertEqual(message.revision, revision)
            messages.append(message)

        # None of the first three messages reached this receiver. A complete
        # replacement at the latest revision is self-contained and can seed it.
        receiver_profile = Profile("tmux")
        receiver = FeedReceiver(receiver_profile, receiver_profile.bind("local", "default"),
                                selector={})
        self.addCleanup(receiver.close)
        replacement = messages[-1].replacement()
        applied = receiver.apply(replacement.payload)
        self.assertEqual(applied.revision, 4)
        self.assertEqual(applied.candidate["ownerFrame"], fixture.frame)
        applied.close()
        replacement.close()

        # After a gap, keep same-stream revision guards. Advance native
        # chronology so this reaches the revision check rather than failing as
        # an old envelope first.
        receiver.mark_gap()
        stale = messages[1].replacement()
        stale_packet = copy.deepcopy(stale.payload)
        stale_packet["envelope"]["sequence"] = messages[-1].payload["envelope"]["sequence"] + 1
        stale_packet["envelope"]["encodedAtMs"] = messages[-1].payload["envelope"]["encodedAtMs"] + 1
        with self.assertRaisesRegex(ProtocolError, "view_feed_revision"):
            receiver.apply(stale_packet)
        stale.close()

        for message in messages:
            message.close()

    def test_replacement_delta_metadata_order_empty_and_null_snapshot_roundtrip(self):
        profile = Profile("tmux")
        codec = profile.bind("local", "default")
        fixture = Publisher("tmux", "local")
        self.expand_fixture(fixture)
        encoder = FeedEncoder(profile, codec, selector={})
        receiver_profile = Profile("tmux")
        receiver = self.receiver(receiver_profile)
        self.addCleanup(encoder.close)
        self.addCleanup(receiver.close)

        def exchange(*, expect_kind=None):
            packet = encoder.encode(fixture.wrap())
            self.assertIsNotNone(packet)
            if expect_kind is not None:
                self.assertEqual(packet.kind, expect_kind)
            applied = receiver.apply(packet.payload)
            self.assertEqual(applied.candidate["ownerFrame"], fixture.frame)
            packet.close()
            return applied

        initial = exchange(expect_kind="replacement")
        self.assertEqual(len(initial.candidate["ownerFrame"]["snapshot"]["sessions"]), 3)
        initial.close()

        # Metadata advances the whole owner digest without changing records.
        fixture.frame["viewRevision"] += 1
        metadata = exchange()
        self.assertEqual(metadata.upserts, [])
        metadata.close()

        # Reordering remains explicit while the reconstructed complete owner
        # retains every original bool, integer, null, and Unicode value.
        fixture.frame["viewRevision"] += 1
        fixture.frame["snapshot"]["sessions"].reverse()
        fixture.frame["snapshot"]["sessions"][0]["name"] = "雪"
        ordered = exchange()
        self.assertEqual(ordered.candidate["ownerFrame"], fixture.frame)
        ordered.close()

        fixture.frame["viewRevision"] += 1
        fixture.frame["snapshot"]["sessions"].pop()
        removed = exchange()
        self.assertEqual(len(removed.candidate["ownerFrame"]["snapshot"]["sessions"]), 2)
        removed.close()

        fixture.frame["viewRevision"] += 1
        fixture.frame["snapshot"]["sessions"].clear()
        empty = exchange()
        self.assertEqual(empty.candidate["ownerFrame"]["snapshot"]["sessions"], [])
        empty.close()

        fixture.frame["snapshot"] = None
        null_snapshot = exchange()
        self.assertIsNone(null_snapshot.candidate["ownerFrame"]["snapshot"])
        null_snapshot.close()

    def test_borrowed_payload_is_immutable_deepcopy_is_detached_and_stays_funded(self):
        profile = Profile("tmux")
        fixture = Publisher("tmux", "local")
        budget = FeedBudget()
        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={}, budget=budget)
        message = encoder.encode(fixture.wrap())
        receiver_profile = Profile("tmux")
        receiver = self.receiver(receiver_profile, budget=budget)
        applied = receiver.apply(message.payload)

        with self.assertRaises(TypeError):
            message.payload["reason"] = "changed"
        with self.assertRaises(TypeError):
            applied.candidate["ownerFrame"]["snapshot"]["sessions"].clear()
        detached = copy.deepcopy(applied.candidate)
        self.assertIs(type(detached), dict)
        self.assertIs(type(detached["ownerFrame"]["snapshot"]["sessions"]), list)
        detached["ownerFrame"]["snapshot"]["sessions"].clear()
        self.assertTrue(applied.candidate["ownerFrame"]["snapshot"]["sessions"])

        borrowed_candidate = applied.candidate
        message.close()
        applied.close()
        encoder.close()
        receiver.close()
        self.assertGreater(budget.inspect()["heapBytes"], 0)
        self.assertTrue(borrowed_candidate["ownerFrame"]["snapshot"]["sessions"])
        del borrowed_candidate
        self.assertEqual(budget.inspect()["heapBytes"], 0)
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

    def test_equal_token_skips_record_hash_and_false_equal_token_forces_checked_replacement(self):
        import mesh_plus.view_feed.core as core

        profile = Profile("tmux")
        fixture = Publisher("tmux", "local")
        fixture.frame["viewRevision"] += 1
        self.expand_fixture(fixture)
        calls = []
        token_calls = []
        original = core._funded_digest

        def token(_record):
            token_calls.append(None)
            return "same-token"

        def digest_spy(scope, value, size=None):
            if isinstance(value, dict) and "sessionId" in value:
                calls.append(value["sessionId"])
            return original(scope, value, size)

        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={},
                              token=token, token_scheme="fixture-v1")
        self.addCleanup(encoder.close)
        with patch.object(core, "_funded_digest", side_effect=digest_spy):
            first = encoder.encode(fixture.wrap())
            self.assertEqual(len(calls), 3)
            first.close()
            calls.clear()
            fixture.frame["viewRevision"] += 1
            second = encoder.encode(fixture.wrap())
            self.assertEqual(calls, [])
            second.close()

            # A false unchanged token omits the changed row; independent full
            # target reconstruction catches that mismatch before output.
            calls.clear()
            fixture.frame["viewRevision"] += 1
            fixture.frame["snapshot"]["sessions"][0]["name"] += "!"
            mismatch = encoder.encode(fixture.wrap())
            self.assertEqual(mismatch.kind, "replacement")
            self.assertEqual(mismatch.payload["reason"], "token_mismatch")
            self.assertEqual(len(calls), 3)
            mismatch.close()

            token_count = len(token_calls)
            fixture.frame["viewRevision"] += 1
            after_disable = encoder.encode(fixture.wrap())
            self.assertEqual(len(token_calls), token_count)
            after_disable.close()

    def test_duplicate_scope_base_target_and_operation_corruption_refuse_then_gap_repairs(self):
        profile = Profile("tmux")
        fixture = Publisher("tmux", "local")
        self.expand_fixture(fixture)
        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={})
        self.addCleanup(encoder.close)
        baseline = encoder.encode(fixture.wrap())
        fixture.frame["viewRevision"] += 1
        fixture.frame["snapshot"]["sessions"][0]["name"] += "changed"
        delta = encoder.encode(fixture.wrap())
        self.assertEqual(delta.kind, "delta")

        receiver_profile = Profile("tmux")

        def with_baseline():
            result = self.receiver(receiver_profile)
            applied = result.apply(baseline.payload)
            applied.close()
            return result

        # A forged whole record retains its key but no longer proves the
        # sender's independently admitted target digest.
        receiver = with_baseline()
        tampered_row = copy.deepcopy(delta.payload)
        tampered_row["upserts"][0]["record"]["name"] = "forged"
        with self.assertRaisesRegex(ProtocolError, "view_feed_target_digest"):
            receiver.apply(tampered_row)
        self.assertFalse(receiver.inspect()["valid"])
        receiver.mark_gap()
        replacement = delta.replacement()
        repaired = receiver.apply(replacement.payload)
        self.assertEqual(repaired.candidate["ownerFrame"], fixture.frame)
        repaired.close()
        replacement.close()
        receiver.close()

        invalid_packets = (
            ("view_feed_base", lambda p: p["base"].__setitem__("digest", "sha256:" + "0" * 64)),
            ("view_feed_base", lambda p: p["target"].__setitem__("revision", p["target"]["revision"] + 1)),
            ("view_feed_envelope", lambda p: p["target"].__setitem__("digest", "sha256:" + "0" * 64)),
            ("view_feed_upsert_identity", lambda p: p["upserts"][0]["key"].__setitem__(0, "foreign")),
            ("view_feed_removal_missing", lambda p: p["removals"].append(["foreign"])),
            ("view_feed_operations", lambda p: p["removals"].append(p["upserts"][0]["key"][:])),
        )
        for code, corrupt in invalid_packets:
            with self.subTest(code=code):
                receiver = with_baseline()
                packet = copy.deepcopy(delta.payload)
                corrupt(packet)
                with self.assertRaisesRegex(ProtocolError, code):
                    receiver.apply(packet)
                self.assertFalse(receiver.inspect()["valid"])
                receiver.close()

        receiver = self.receiver(receiver_profile)
        duplicate_order = copy.deepcopy(baseline.payload)
        duplicate_order["order"].append(duplicate_order["order"][0][:])
        with self.assertRaisesRegex(ProtocolError, "view_feed_order"):
            receiver.apply(duplicate_order)
        self.assertFalse(receiver.inspect()["valid"])
        receiver.close()

        duplicate_profile = Profile("tmux")
        duplicate_fixture = Publisher("tmux", "local")
        duplicate_fixture.frame["snapshot"]["sessions"].append(
            copy.deepcopy(duplicate_fixture.frame["snapshot"]["sessions"][0]))
        duplicate_encoder = FeedEncoder(duplicate_profile,
                                        duplicate_profile.bind("local", "default"), selector={})
        with self.assertRaisesRegex(ProtocolError, "view_feed_duplicate_identity"):
            duplicate_encoder.encode(duplicate_fixture.wrap())
        self.assertIsNone(duplicate_encoder.inspect()["revision"])
        duplicate_encoder.close()

        limited_profile = Profile("tmux")
        limited_fixture = Publisher("tmux", "local")
        self.expand_fixture(limited_fixture)
        limited = FeedEncoder(limited_profile, limited_profile.bind("local", "default"), selector={},
                              limits=FeedLimits(max_records=2))
        with self.assertRaisesRegex(ProtocolError, "view_feed_record_capacity"):
            limited.encode(limited_fixture.wrap())
        self.assertIsNone(limited.inspect()["revision"])
        limited.close()

    def test_callback_and_restore_errors_keep_credits_until_traceback_drop(self):
        class RestoreFailureProfile(Profile):
            def __init__(self):
                super().__init__("tmux")
                self.restores = 0

            def restore_native(self, owner, records):
                self.restores += 1
                if self.restores == 2:
                    raise RuntimeError("restore callback failure")
                return super().restore_native(owner, records)

        fixture = Publisher("tmux", "local")
        profile = Profile("tmux")
        budget = FeedBudget()
        retained_arguments = []

        def fail_token(record):
            retained_arguments.append(record)
            raise RuntimeError("token callback failure")

        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={}, budget=budget,
                              token=fail_token, token_scheme="failure-v1")
        caught = None
        try:
            encoder.encode(fixture.wrap())
        except RuntimeError as error:
            caught = error
        self.assertIsNotNone(caught)
        encoder.close()
        self.assertGreater(budget.inspect()["heapBytes"], 0)
        retained_arguments.clear()
        self.assertGreater(budget.inspect()["heapBytes"], 0)
        caught = None
        self.assertEqual(budget.inspect()["heapBytes"], 0)

        failed_profile = RestoreFailureProfile()
        failed_budget = FeedBudget()
        failed_encoder = FeedEncoder(failed_profile, failed_profile.bind("local", "default"),
                                     selector={}, budget=failed_budget)
        restore_error = None
        try:
            failed_encoder.encode(fixture.wrap())
        except RuntimeError as error:
            restore_error = error
        self.assertIsNotNone(restore_error)
        failed_encoder.close()
        self.assertGreater(failed_budget.inspect()["heapBytes"], 0)
        restore_error = None
        self.assertEqual(failed_budget.inspect()["heapBytes"], 0)

        sender_profile = Profile("tmux")
        sender_budget = FeedBudget()
        sender = FeedEncoder(sender_profile, sender_profile.bind("local", "default"),
                             selector={}, budget=sender_budget)
        packet = sender.encode(fixture.wrap())

        class ReceiverRestoreFailure(Profile):
            def __init__(self):
                super().__init__("tmux")
                self.restores = 0

            def restore_native(self, owner, records):
                self.restores += 1
                if self.restores == 2:
                    raise RuntimeError("receiver restore failure")
                return super().restore_native(owner, records)

        receiver_profile = ReceiverRestoreFailure()
        receiver_budget = FeedBudget()
        receiver = self.receiver(receiver_profile, budget=receiver_budget)
        receiver_error = None
        try:
            receiver.apply(packet.payload)
        except RuntimeError as error:
            receiver_error = error
        self.assertIsNotNone(receiver_error)
        packet.close()
        sender.close()
        receiver.close()
        self.assertGreater(receiver_budget.inspect()["heapBytes"], 0)
        receiver_error = None
        self.assertEqual(receiver_budget.inspect()["heapBytes"], 0)
        self.assertEqual(receiver_budget.inspect()["encodedBytes"], 0)

    def test_reentrant_close_rolls_back_and_shared_capacity_refuses_before_callback(self):
        fixture = Publisher("tmux", "local")
        profile = Profile("tmux")
        shared = FeedBudget()
        holder = {}

        def close_from_callback(_record):
            holder["encoder"].close()
            return "token"

        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={}, budget=shared,
                              token=close_from_callback, token_scheme="reentrant-v1")
        holder["encoder"] = encoder
        caught = None
        try:
            encoder.encode(fixture.wrap())
        except ProtocolError as error:
            caught = error
        self.assertIsNotNone(caught)
        self.assertTrue(encoder.inspect()["closed"])
        self.assertIsNone(encoder.inspect()["revision"])
        self.assertGreater(shared.inspect()["heapBytes"], 0)
        caught = None
        self.assertEqual(shared.inspect()["heapBytes"], 0)

        tiny_budget = FeedBudget(FeedLimits(heap_bytes=20_000, encoded_bytes=1_000_000))
        calls = []
        refused = FeedEncoder(profile, profile.bind("local", "default"), selector={}, budget=tiny_budget,
                              token=lambda _record: calls.append(None) or "token",
                              token_scheme="tiny-v1")
        with self.assertRaisesRegex(ProtocolError, "view_feed_capacity"):
            refused.encode(fixture.wrap())
        self.assertEqual(calls, [])
        refused.close()
        self.assertEqual(tiny_budget.inspect()["heapBytes"], 0)

    def test_shared_budget_sibling_and_public_lease_retire_without_gc(self):
        profile_a, profile_b = Profile("tmux"), Profile("tmux")
        budget = FeedBudget()
        encoder_a = FeedEncoder(profile_a, profile_a.bind("local", "default"), selector={}, budget=budget)
        encoder_b = FeedEncoder(profile_b, profile_b.bind("local", "default"), selector={}, budget=budget)
        message_b = encoder_b.encode(Publisher("tmux", "local").wrap())
        encoder_a.close()
        self.assertFalse(encoder_b.inspect()["closed"])
        replacement = message_b.replacement()
        message_b.close()
        replacement.close()
        encoder_b.close()
        self.assertEqual(budget.inspect()["heapBytes"], 0)
        self.assertEqual(budget.inspect()["encodedBytes"], 0)

        public_budget = FeedBudget()
        reference = weakref.ref(public_budget)
        lease = public_budget.reserve(heap=128, encoded=64)
        del public_budget
        self.assertIsNotNone(reference())
        lease.release()
        del lease
        self.assertIsNone(reference())


if __name__ == "__main__":
    unittest.main()
