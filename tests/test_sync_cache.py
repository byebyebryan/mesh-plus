import copy
import os
import unittest
from hashlib import sha256
from unittest.mock import patch

from test_sync_reconstruction import BINDING, IDENTITY, OWNER, Profile, fixture, operations

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import HeadRules, OriginalReceipt, OwnedSyncCache, source_binding
from mesh_plus.sync.cache import MovedHead
from mesh_plus.sync.canonical import Atom, canonical, decode
from mesh_plus.sync.commitment import MerkleMap, binding_digest, framed, native_root
from mesh_plus.sync.model import NativeTag
from mesh_plus.sync.reconstruction import MaterialRoot

CLOCK = {"bootId": "reader-boot", "timeNamespace": "time:2"}
NATIVE_BINDING = {**BINDING, "uid": os.getuid(), "bootId": "owner-boot", "clockDomain": "time:[1]"}
RECEIPT_KEY = ["reference", "scope", "runtime"]
BRIDGE = "b" * 32
REQUEST = {"readerEpoch": "r" * 32, "channelEpoch": "c" * 32, "bridgeId": BRIDGE,
           "hosts": ["fixture"], "catalog": "revision", "route": "fixed"}


class CacheProfile(Profile):
    def __init__(self):
        super().__init__()
        self.head_calls = 0
        self.head_callback = None
        self.retained_head = None

    def check_head(self, ctx, head):
        self.head_calls += 1
        self.retained_head = head
        values = []
        for entry in ctx.original_receipts:
            key, value = entry[0].materialize(), entry[1].materialize()
            self.asserted = ctx.view.lookup("receipts", key).materialize() == value
            token = sha256(b"mesh-sync-value\0" + framed(b"receipts") + framed(canonical(value))).hexdigest()
            values.append(OriginalReceipt(Atom.own(key), token, value["accepted"], value["health"],
                                          value["expiresBoottimeMs"]))
        if self.head_callback is not None:
            self.head_callback(ctx)
        return HeadRules(tuple(values))


def baseline(profile, value=1, generation=1):
    tables, _, _, _ = fixture(profile, value, generation)
    tables = {name: [[key, value] for key, value in entries] for name, entries in tables.items()}
    tables["receipts"] = [[RECEIPT_KEY, {"accepted": 1, "health": "current", "sampledBoottimeMs": 1000,
                                       "expiresBoottimeMs": 5000}]]
    maps = {name: MerkleMap.baseline(name, entries) for name, entries in tables.items()}
    tag = NativeTag(binding_digest(NATIVE_BINDING, native=True).hex(), generation,
                    native_root(NATIVE_BINDING, generation, maps).hex())
    document = {"kind": "baseline", "descriptor": decode(profile.descriptor.native_descriptor),
                "nativeBinding": NATIVE_BINDING, "tag": tag.wire(), "cursor": [OWNER, generation, tag.root],
                "tables": tables}
    return canonical(document), maps, tag


def transaction(profile, old_maps, old_tag, value, generation):
    _, new_maps, new_tag = baseline(profile, value, generation)
    changes = {name: [] for name in new_maps}
    for change in operations(old_maps, new_maps):
        row = [change.op, decode(change.key.encoded), change.expected]
        if change.op == "put":
            row.append(decode(change.value.encoded))
        changes[change.space].append(row)
    document = {"kind": "transaction", "descriptor": decode(profile.descriptor.native_descriptor),
                "nativeBindingDigest": old_tag.binding, "baseTag": old_tag.wire(), "resultTag": new_tag.wire(),
                "baseCursor": [OWNER, old_tag.generation, old_tag.root],
                "resultCursor": [OWNER, generation, new_tag.root], "operations": changes}
    document["transactionId"] = sha256(b"mesh-sync-transaction\0" + framed(canonical(document))).hexdigest()
    return canonical(document), new_maps, new_tag


def proof(cache, candidate, *, native_time=2000, tag=None):
    challenge = cache._proof_request(candidate)
    root = cache._candidate(candidate)
    tag = root.tag if tag is None else tag
    receipts = [[decode(leaf.key), decode(leaf.atom.encoded)] for leaf in dict(root.tables)["receipts"].leaves()]
    head = {"kind": "head", "descriptor": decode(cache.descriptor.native_descriptor),
            "nativeBindingDigest": tag.binding, "tag": tag.wire(), "challenge": challenge,
            "ownerClock": {**{key: NATIVE_BINDING[key] for key in ("bootId", "clockDomain", "uid", "hostScope", "ownerEpoch")},
                           "boottimeMs": native_time},
            "originalReceipts": receipts, "cohortHeads": [],
            "attenuation": [[key, max(0, value["expiresBoottimeMs"] - native_time)] for key, value in receipts]}
    bridge_time = native_time + 10
    return canonical({"protocol": "mesh.state-sync/1", "kind": "proof", "descriptor": cache.descriptor.wire(),
                      "sourceBinding": decode(cache._binding.encoded), "sourceTag": cache._tag(tag).wire(),
                      "requestBinding": REQUEST, "challenge": challenge, "bridgeId": BRIDGE,
                      "bridgeClock": {"bootId": "owner-boot", "timeNamespace": "time:1", "boottimeMs": bridge_time},
                      "head": head, "remaining": [[key, max(0, value["expiresBoottimeMs"] - bridge_time)]
                                                 for key, value in receipts]})


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.now = 10_000
        self.profile = CacheProfile()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   request_binding=REQUEST, _now_ms=lambda: self.now, _clock=CLOCK)
        raw, self.maps, self.tag = baseline(self.profile)
        self.candidate = self.cache.admit_baseline(raw)

    def tearDown(self):
        self.cache.close()
        self.assertEqual(self.cache.ledger.used, 0)
        self.assertEqual(self.cache.ledger.reserved, 0)

    def confirm(self):
        raw = proof(self.cache, self.candidate)
        self.now += 20
        return self.cache.confirm(self.candidate, raw, CLOCK)

    def test_confirmation_never_reclaims_an_older_material_generation(self):
        self.confirm()
        for generation in (2, 3, 4):
            raw, self.maps, self.tag = transaction(self.profile, self.maps, self.tag, generation, generation)
            self.candidate = self.cache.stage(raw)
            self.assertIsNone(self.cache.store.previous)
            original = self.cache.ledger.release

            def release(value):
                self.assertNotIsInstance(value, MaterialRoot, "material reclamation entered compact confirmation")
                return original(value)

            with patch.object(self.cache.ledger, "release", side_effect=release):
                self.confirm()
            self.assertEqual(self.cache.store.current.tag.generation, generation)

    def test_only_fresh_proof_publishes_and_old_receipt_is_not_renewed(self):
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()
        view = self.confirm()
        body_id = view.lookup("records", IDENTITY)["body"]
        self.assertEqual(view.lookup("bodies", body_id)["value"], 1)
        self.assertTrue(self.profile.asserted)
        self.assertTrue(view.context(self.now, CLOCK)["receipts"][0]["current"])
        expiry = view.context(self.now, CLOCK)["receipts"][0]["expiresMs"]
        self.assertEqual(expiry, 12_890)
        with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
            self.profile.retained_head.materialize()
        self.now = 11_000
        raw = proof(self.cache, self.candidate, native_time=3000)
        self.now += 20
        refreshed = self.cache.confirm(self.candidate, raw, CLOCK)
        self.assertEqual(refreshed.context(self.now, CLOCK)["receipts"][0]["expiresMs"], expiry)
        self.assertFalse(refreshed.context(expiry, CLOCK)["receipts"][0]["current"])
        self.now = expiry + 1
        self.assertFalse(refreshed.context(11_020, CLOCK)["receipts"][0]["current"])

    def test_nonce_consumption_and_cross_cache_capability(self):
        raw = proof(self.cache, self.candidate)
        self.cache.confirm(self.candidate, raw, CLOCK)
        with self.assertRaisesRegex(ProtocolError, "sync_missing_proof_request"):
            self.cache.confirm(self.candidate, raw, CLOCK)
        other = OwnedSyncCache(self.profile, source_binding("fixture", "other", self.profile.descriptor))
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_candidate_retired"):
                other._proof_request(self.candidate)
        finally:
            other.close()

    def test_moved_head_revokes_old_view_before_any_catchup(self):
        view = self.confirm()
        retained = view.lookup("records", IDENTITY)
        _, _, moved = baseline(self.profile, 2, 2)
        raw = proof(self.cache, self.candidate, tag=moved)
        with self.assertRaises(MovedHead) as result:
            self.cache.confirm(self.candidate, raw, CLOCK)
        self.assertEqual(result.exception.tag, moved)
        with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
            retained.materialize()
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    def test_known_moved_head_cannot_reauthorize_the_older_material(self):
        self.confirm()
        _, _, moved = baseline(self.profile, 2, 2)
        with self.assertRaises(MovedHead):
            self.cache.confirm(self.candidate, proof(self.cache, self.candidate, tag=moved), CLOCK)
        with self.assertRaisesRegex(ProtocolError, "sync_head_regression"):
            self.cache.confirm(self.candidate, proof(self.cache, self.candidate), CLOCK)
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    def test_validation_time_is_inside_proof_deadline(self):
        def slow(ctx):
            self.now += 2001

        self.profile.head_callback = slow
        raw = proof(self.cache, self.candidate)
        with self.assertRaisesRegex(ProtocolError, "sync_proof_deadline"):
            self.cache.confirm(self.candidate, raw, CLOCK)
        self.assertIsNone(self.cache.store.current)
        self.assertIsNotNone(self.cache.store.candidate)

    def test_pre_copy_bound_does_not_decode_or_export_the_roster(self):
        view = self.confirm()
        body = view.lookup("bodies", view.lookup("records", IDENTITY)["body"])
        size = body.materialization_bytes
        self.assertGreaterEqual(size, 248 + 72 * 2)
        self.assertEqual(body["identity"].materialization_bytes, size)
        detached = body.materialize()
        detached["identity"][0] = "other"
        self.assertEqual(body["identity"][0], "fixture")
        self.cache.disconnect()
        with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
            body.materialization_bytes

    def test_public_failure_traceback_keeps_no_private_stage_frames(self):
        self.profile.head_callback = lambda ctx: (_ for _ in ()).throw(ValueError("native_domain_rejected"))
        saved = None
        try:
            self.cache.confirm(self.candidate, proof(self.cache, self.candidate), CLOCK)
        except ProtocolError as error:
            saved = error
        self.assertIsNotNone(saved)
        self.assertEqual(str(saved), "native_domain_rejected")
        self.assertIsNone(saved.__cause__)
        self.assertIsNone(saved.__context__)
        trace = saved.__traceback__
        while trace is not None:
            name = trace.tb_frame.f_code.co_name
            self.assertNotIn(name, {"confirm", "_head_rules", "stage_baseline", "stage_delta"})
            trace = trace.tb_next
        self.cache.close()
        self.assertEqual(self.cache.ledger.used, 0)

    def test_receipt_and_clock_mutations_fail_closed(self):
        cases = [lambda doc: doc["head"]["originalReceipts"][0][1].update(accepted=2),
                 lambda doc: doc["remaining"][0].__setitem__(1, 99999),
                 lambda doc: doc["bridgeClock"].update(timeNamespace="time:9"),
                 lambda doc: doc["requestBinding"].update(route="other")]
        for mutate in cases:
            document = decode(proof(self.cache, self.candidate))
            mutate(document)
            with self.assertRaises(ProtocolError):
                self.cache.confirm(self.candidate, canonical(document), CLOCK)
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                self.cache.acquire()

    def test_contiguous_batch_changes_and_exact_duplicate_do_not_readmit(self):
        view = self.confirm()
        base = view.tag
        first, maps2, tag2 = transaction(self.profile, self.maps, self.tag, 2, 2)
        second, _, _ = transaction(self.profile, maps2, tag2, 3, 3)
        self.candidate = self.cache.stage_batch(base, (first, second))
        with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
            view.lookup("records", IDENTITY)
        updated = self.confirm()
        self.assertEqual(updated.index("facts").get([IDENTITY, [OWNER, 1]])["value"], 3)
        changes = updated.changes(base)
        self.assertEqual(changes.base, base)
        self.assertTrue(any(key[0] == "records" for key in changes.keys))
        current_permit = self.cache._view_permit
        self.assertIs(self.cache.stage(second), self.candidate)
        self.assertEqual(self.cache._view_permit, current_permit)
        self.assertEqual(self.profile.head_calls, 2)

    def test_batch_failure_discards_intermediate_stage_and_releases_reservations(self):
        view = self.confirm()
        first, maps2, tag2 = transaction(self.profile, self.maps, self.tag, 2, 2)
        second, _, _ = transaction(self.profile, maps2, tag2, 3, 3)
        corrupted = decode(second)
        corrupted["transactionId"] = "0" * 64
        with self.assertRaisesRegex(ProtocolError, "sync_transaction_id"):
            self.cache.stage_batch(view.tag, (first, canonical(corrupted)))
        self.assertIsNone(self.cache.store.candidate)
        self.assertEqual(self.cache.store.current.tag, self.tag)
        self.assertEqual(self.cache.ledger.reserved, 0)

    def test_disconnect_retires_candidate_query_and_iterator(self):
        view = self.confirm()
        iterator = view.index("facts").iter_keys()
        self.cache.disconnect()
        with self.assertRaisesRegex(ProtocolError, "sync_view_retired"):
            next(iterator)
        with self.assertRaisesRegex(ProtocolError, "sync_candidate_retired"):
            self.candidate.tag
        with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
            self.cache.acquire()

    def test_closed_json_frame_and_hard_input_reservation(self):
        raw, _, _ = baseline(self.profile)
        document = decode(raw)
        document["extra"] = True
        with self.assertRaisesRegex(ProtocolError, "sync_baseline_shape"):
            self.cache.admit_baseline(canonical(document))
        with self.assertRaisesRegex(ProtocolError, "sync_message_capacity"):
            self.cache.admit_baseline(bytearray(raw))
        changed = copy.deepcopy(document)
        changed.pop("extra")
        changed["descriptor"]["version"] = 2
        with self.assertRaisesRegex(ProtocolError, "sync_native_descriptor"):
            self.cache.admit_baseline(canonical(changed))


if __name__ == "__main__":
    unittest.main()
