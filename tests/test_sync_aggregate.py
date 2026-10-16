import unittest

from test_sync_cache import BRIDGE, CLOCK, CacheProfile, baseline, proof

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, source_binding
from mesh_plus.sync.aggregate import AggregateState, UnavailableHost
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import canonical, decode
from mesh_plus.sync.commitment import MerkleMap, binding_digest, body_digest, native_root
from mesh_plus.sync.model import NativeTag


class AggregateTests(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.profile = CacheProfile()
        self.ledger = AllocationLedger()
        self.state = AggregateState(source="source", profile=self.profile, hosts=("other", "fixture"),
                                    catalog_revision="rev", routes=("route2", "route1"), reader_epoch="r" * 32,
                                    request_id="request", ledger=self.ledger)
        self.caches = []

    def tearDown(self):
        self.state.close()
        for cache in self.caches:
            cache.close()
        self.assertEqual((self.ledger.used, self.ledger.reserved, self.ledger.pending_units), (0, 0, 0))

    def cache(self, host, *, confirmed=True, channel="c"):
        request = {"readerEpoch": "r" * 32, "requestId": "request", "channelEpoch": channel * 32,
                   "bridgeId": BRIDGE, "hosts": ["other", "fixture"], "catalogRevision": "rev",
                   "route": "route2" if host == "other" else "route1"}
        cache = OwnedSyncCache(self.profile, source_binding(host, "source", self.profile.descriptor),
                               request_binding=request, ledger=self.ledger, _now_ms=lambda: self.now, _clock=CLOCK)
        self.caches.append(cache)
        raw, _, _ = baseline(self.profile)
        document = decode(raw)
        if host != "fixture":
            document["nativeBinding"]["hostScope"] = host
            row = document["tables"]["records"][0]
            row[0][0] = row[1]["order"][0] = host
            body = document["tables"]["bodies"][0]
            body[1]["identity"][0] = host
            body[0] = body_digest(bytes.fromhex(self.profile.descriptor.native_descriptor_digest), body[1]).hex()
            row[1]["body"] = body[0]
            document["tables"]["observations"][0][0][0][0] = host
            maps = {name: MerkleMap.baseline(name, rows) for name, rows in document["tables"].items()}
            binding = document["nativeBinding"]
            tag = NativeTag(binding_digest(binding, native=True).hex(), 1, native_root(binding, 1, maps).hex())
            document["tag"], document["cursor"][2] = tag.wire(), tag.root
        candidate = cache.admit_baseline(canonical(document))
        if confirmed:
            encoded = decode(proof(cache, candidate))
            encoded["requestBinding"] = request
            encoded["head"]["ownerClock"]["hostScope"] = host
            cache.confirm(candidate, canonical(encoded), CLOCK)
        return cache

    def test_ordered_hosts_never_promote_a_candidate_and_other_hosts_keep_their_leases(self):
        a, b = self.cache("fixture"), self.cache("other", confirmed=False)
        self.state.attach("fixture", a)
        self.state.attach("other", b)
        commit = self.state.capture()
        self.assertEqual([item["host"] for item in commit.hosts()], ["other", "fixture"])
        self.assertIsInstance(commit.host("other"), UnavailableHost)
        self.assertEqual(commit.host("fixture").tag, a.acquire().tag)
        self.state.revoke_host("other", "head_moved")
        self.assertTrue(commit.host("fixture").context(self.now, CLOCK)["receipts"][0]["current"])
        self.assertIsInstance(commit.host("other"), UnavailableHost)
        self.now = 20000
        self.assertFalse(commit.host("fixture").context(self.now, CLOCK)["receipts"][0]["current"])

    def test_one_host_revokes_immediately_without_cross_host_transaction(self):
        for host in ("fixture", "other"):
            self.state.attach(host, self.cache(host))
        commit = self.state.capture()
        self.state.revoke_host("fixture", "head_moved")
        self.assertEqual(commit.host("fixture"), UnavailableHost("fixture", "head_moved"))
        self.assertEqual(commit.host("other").lookup("metadata", "absent"),
                         self.caches[1].acquire().lookup("metadata", "absent"))
        self.assertEqual(commit.hosts()[1]["tag"], None)

    def test_same_tag_on_new_channel_does_not_reuse_an_old_aggregate_authority(self):
        first = self.cache("fixture")
        self.state.attach("fixture", first)
        commit = self.state.capture()
        second = self.cache("fixture", channel="d")
        self.assertEqual(first.acquire().tag, second.acquire().tag)
        self.state.attach("fixture", second)
        self.assertEqual(commit.host("fixture"), UnavailableHost("fixture", "channel_replaced"))
        self.assertEqual(self.state.capture().host("fixture").tag, second.acquire().tag)

    def test_request_replacement_closes_all_owned_caches_and_retires_handles(self):
        cache = self.cache("fixture")
        self.state.attach("fixture", cache)
        commit = self.state.capture()
        retained = commit.host("fixture").lookup("receipts", ["reference", "scope", "runtime"])
        self.state.close("catalog_changed")
        self.assertEqual(commit.host("fixture"), UnavailableHost("fixture", "catalog_changed"))
        with self.assertRaisesRegex(ProtocolError, "sync_cache_closed"):
            retained.materialize()

    def test_cache_from_another_request_cannot_be_relabeled(self):
        cache = self.cache("fixture")
        self.state.close()
        self.state = AggregateState(source="source", profile=self.profile, hosts=("fixture",),
                                    catalog_revision="different", routes=("route1",), reader_epoch="r" * 32,
                                    request_id="other", ledger=self.ledger)
        with self.assertRaisesRegex(ProtocolError, "sync_aggregate_request_binding"):
            self.state.attach("fixture", cache)


if __name__ == "__main__":
    unittest.main()
