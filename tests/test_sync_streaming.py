import json
import random
import unittest

from test_sync_cache import NATIVE_BINDING, baseline
from test_sync_reconstruction import OWNER, Profile

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, SyncBudgets, source_binding
from mesh_plus.sync.canonical import canonical, decode, decode_reservation
from mesh_plus.sync.commitment import MerkleMap, binding_digest, body_digest, native_root
from mesh_plus.sync.model import SPACES, NativeTag
from mesh_plus.sync.streaming import array_spans, object_spans


class StreamingTests(unittest.TestCase):
    def test_byte_spans_match_strict_decoder_for_nested_unicode_and_escapes(self):
        generator = random.Random(317)

        def value(depth):
            if depth == 0:
                return generator.choice([None, True, 123, "a\\\"b", "雪😀", "[]{}", "line\n\t"])
            return generator.choice([[value(depth - 1) for _ in range(3)],
                                     {"first": value(depth - 1), "other": value(depth - 1)}])

        for _ in range(100):
            data = {"a": value(3), "z": [value(2), value(2)]}
            raw = json.dumps(data, ensure_ascii=False, indent=2).encode()
            fields = object_spans(raw)
            self.assertEqual({key: decode(raw[start:end]) for key, (start, end) in fields.items()}, data)
            self.assertEqual([decode(raw[start:end]) for start, end in array_spans(raw, *fields["z"])], data["z"])

    def test_noncanonical_whitespace_and_escapes_keep_identical_roots(self):
        profile = Profile()
        raw, _, expected = baseline(profile)
        pretty = json.dumps(decode(raw), ensure_ascii=True, indent=2).encode()
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor))
        try:
            candidate = cache.admit_baseline(pretty)
            self.assertEqual(candidate.tag.native, expected)
            self.assertEqual(cache.ledger.reserved, 0)
        finally:
            cache.close()
        self.assertEqual(cache.ledger.used, 0)

    def test_invalid_nested_tokens_duplicate_keys_and_structure_fail_closed(self):
        profile = Profile()
        raw, _, _ = baseline(profile)
        corruptions = [raw + b"x", raw[:-1] + b",}",
                       raw.replace(b'"value":1', b'"value":1.0'),
                       raw.replace(b'"value":1', b'"value":"\xff"'),
                       raw.replace(b'"value":1', b'"value":1,"value":2'),
                       raw.replace(b'"value":1', b'"value":1,"\\u0076alue":2'),
                       raw.replace(b'"value":1', b'"value":"raw\nline"')]
        for invalid in corruptions:
            cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor))
            try:
                with self.assertRaises(ProtocolError):
                    cache.admit_baseline(invalid)
                self.assertIsNone(cache.store.candidate)
                self.assertEqual(cache.ledger.reserved, 0)
                with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                    cache.acquire()
            finally:
                cache.close()
            self.assertEqual(cache.ledger.used, 0)

    def test_nested_depth_includes_outer_native_envelope(self):
        profile = Profile()
        raw, _, _ = baseline(profile)
        nested = b"[" * 62 + b"0" + b"]" * 62
        invalid = raw.replace(b'"metadata":[]', b'"metadata":[["deep",' + nested + b"]]")
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor))
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_tree_depth"):
                cache.admit_baseline(invalid)
            self.assertEqual(cache.ledger.reserved, 0)
        finally:
            cache.close()

    def test_streaming_removes_the_whole_roster_decoder_reservation(self):
        profile = Profile()
        tables = {name: [] for name in SPACES}
        for i in range(300):
            identity = ["fixture", "reference", "scope", "record", f"id-{i}"]
            birth = [OWNER, 1]
            body = {"identity": identity, "value": i, "text": "x" * 4096}
            digest = body_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), body).hex()
            tables["records"].append([identity, {"birth": birth, "body": digest, "order": identity, "scope": "scope"}])
            tables["bodies"].append([digest, body])
            tables["observations"].append([[identity, birth], {"stamp": 1}])
        maps = {name: MerkleMap.baseline(name, rows) for name, rows in tables.items()}
        tag = NativeTag(binding_digest(NATIVE_BINDING, native=True).hex(), 1, native_root(NATIVE_BINDING, 1, maps).hex())
        raw = canonical({"kind": "baseline", "descriptor": decode(profile.descriptor.native_descriptor),
                         "nativeBinding": NATIVE_BINDING, "tag": tag.wire(), "cursor": [OWNER, 1, tag.root], "tables": tables})
        maximum = 6 * 1024 * 1024
        self.assertGreater(decode_reservation(raw), maximum)
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor),
                               SyncBudgets(decoded_bytes=maximum))
        try:
            candidate = cache.admit_baseline(raw)
            self.assertEqual(candidate.tag.native, tag)
            self.assertLess(cache.ledger.peak, maximum)
            self.assertEqual(cache.ledger.reserved, 0)
        finally:
            cache.close()
        self.assertEqual(cache.ledger.used, 0)


if __name__ == "__main__":
    unittest.main()
