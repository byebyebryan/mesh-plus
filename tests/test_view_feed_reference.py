"""Independent operation model versus actual runtime packets and native targets."""

import copy
import gc
import importlib.util
import unittest
from pathlib import Path

from sdk_fixture import Profile, Publisher

from mesh_plus.protocol import ProtocolError, encode
from mesh_plus.view_feed import FeedEncoder, FeedReceiver

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("feed_reference", ROOT / "contracts/view-feed-v1/reference.py")
REFERENCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(REFERENCE)


class ViewFeedReferenceTests(unittest.TestCase):
    def setUp(self):
        was_enabled = gc.isenabled()
        gc.disable()
        self.addCleanup(lambda: gc.enable() if was_enabled else None)

    def test_exact_positive_and_negative_reference_vectors(self):
        result = REFERENCE.run()
        self.assertEqual(len(result["positive"]), 9)
        self.assertEqual(len(result["negative"]), 24)

    def test_accidentally_mutating_profile_cannot_emit_unverified_first_replacement(self):
        class MutatingProfile(Profile):
            def record_identity(self, record):
                key = super().record_identity(record)
                record["name"] = "mutated during identity callback"
                return key

        profile = MutatingProfile("tmux")
        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={})
        with self.assertRaisesRegex(ProtocolError, "view_feed_sender_reconstruction"):
            encoder.encode(Publisher("tmux", "local").wrap())
        self.assertIsNone(encoder.inspect()["revision"])
        encoder.close()
        self.assertEqual(encoder.budget.inspect()["heapBytes"], 0)

    def test_actual_packets_independent_merge_and_sparse_payload_bytes(self):
        source = Publisher("tmux", "local")
        profile = Profile("tmux")
        encoder = FeedEncoder(profile, profile.bind("local", "default"), selector={})
        receiver = FeedReceiver(profile, profile.bind("local", "default"), selector={})
        template = source.frame["snapshot"]["sessions"][0]
        source.frame["snapshot"]["sessions"] = [
            {**copy.deepcopy(template), "sessionId": "$" + str(index), "name": "unchanged-" + "x" * 200}
            for index in range(64)]
        previous = None
        sizes = []

        def identity(row):
            return [row[k] for k in ("hostId", "serverGeneration", "sessionId", "createdAt")]

        def restore(owner, rows):
            return {**owner["service"], "snapshot": {**owner["metadata"], "sessions": rows}}

        try:
            for stage in range(5):
                rows = source.frame["snapshot"]["sessions"]
                if stage == 1:
                    rows[0]["name"] = "changed"
                elif stage == 2:
                    rows.reverse()
                elif stage == 3:
                    rows.pop()
                elif stage == 4:
                    rows.clear()
                source.frame["viewRevision"] += 1
                candidate = source.wrap()
                message = encoder.encode(candidate)
                packet = copy.deepcopy(message.payload)
                model = REFERENCE.reconstruct(previous, packet, identity=identity, restore=restore)
                self.assertEqual(model["native"], candidate["ownerFrame"])
                previous = model
                applied = receiver.apply(packet)
                self.assertEqual(applied.candidate, candidate)
                if stage == 1:
                    self.assertEqual(message.kind, "delta")
                    self.assertEqual(len(packet["upserts"]), 1)
                    self.assertIsNone(packet["order"])
                    self.assertLess(len(encode(packet)), len(encode(candidate)) // 4)
                sizes.append((len(encode(packet)), len(encode(candidate))))
                applied.close()
                message.close()
            self.assertGreater(sizes[0][0], sizes[1][0])
        finally:
            encoder.close()
            receiver.close()
