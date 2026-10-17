import gc
import itertools
import unittest
from unittest.mock import patch

from test_sync_cache import CLOCK, REQUEST, CacheProfile, baseline, proof, transaction
from test_sync_commitment import oracle

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import OwnedSyncCache, source_binding
from mesh_plus.sync._packed_nodes import PackedNodeArena
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.commitment import ABSENT, MerkleMap


class PackedNodeTests(unittest.TestCase):
    def setUp(self):
        self.enabled = gc.isenabled()
        gc.disable()
        self.ledger = AllocationLedger()
        self.arena = PackedNodeArena(self.ledger)

    def tearDown(self):
        try:
            self.arena.close()
            self.assertEqual((self.ledger.used, self.ledger.reserved, self.ledger.encoded,
                              self.ledger.encoded_reserved, self.ledger.pending_units), (0, 0, 0, 0, 0))
        finally:
            if self.enabled:
                gc.enable()

    def test_all_permutations_bulk_and_sparse_roots_match_independent_oracle(self):
        rows = [(key, {"value": key}) for key in "abcdef"]
        expected = oracle("records", rows)
        with self.ledger.allocations():
            for permutation in itertools.permutations(rows):
                tree = MerkleMap("records")
                for key, value in permutation:
                    tree = tree.put(key, value)
                self.assertEqual(tree.root, expected)
                tree = None
            tree = MerkleMap.baseline("records", rows)
            self.assertEqual(tree.root, expected)
            self.assertEqual(len(tree), 6)
            self.assertEqual(sorted((key, value["value"]) for key, value in tree.items()),
                             [(key, key) for key in "abcdef"])
            updated = tree.put("c", {"value": "changed"})
            self.assertEqual(tree.root, expected)
            self.assertEqual(updated.root, oracle("records", [(key, {"value": "changed" if key == "c" else key})
                                                               for key in "abcdef"]))
            updated = updated.remove("c")
            self.assertEqual(updated.root, oracle("records", [(key, value) for key, value in rows if key != "c"]))
            with self.assertRaisesRegex(ProtocolError, "sync_expected_value"):
                tree.put("c", 1, expected=ABSENT)
            tree = updated = None
        self.assertEqual(self.arena.live_nodes, 0)

    def test_sparse_work_old_root_and_point_queries(self):
        with self.ledger.allocations():
            tree = MerkleMap.baseline("memberships", [(str(i), "11" * 32) for i in range(2000)])
            root, before = tree.root, tree.work.snapshot()
            reads = self.arena.record_reads
            changed = tree.put("1000", "22" * 32)
            self.assertNotEqual(changed.root, root)
            self.assertEqual(tree.root, root)
            self.assertEqual(tree.work.iterated_entries, before["iterated_entries"])
            self.assertLessEqual(tree.work.node_reads - before["node_reads"], 257)
            self.assertLessEqual(tree.work.branch_hashes - before["branch_hashes"], 256)
            self.assertLess(self.arena.record_reads - reads, 2000)
            self.assertEqual(changed.get("1000"), "22" * 32)
            self.assertEqual(tree.get("1000"), "11" * 32)
            tree = changed = None

    def test_dead_leaf_releases_its_atom_while_page_keeps_other_leaf(self):
        with self.ledger.allocations():
            tree = MerkleMap("records").put("a", "one").put("b", "two")
            self.ledger.retain(tree)
            leaf = tree.find("a")
            old_handle, old_epoch, atom = leaf._handle, self.arena._epoch, leaf.atom
            leaf = None
            survivor = tree.remove("a")
            self.ledger.retain(survivor)
            self.ledger.release(tree)
            tree = None

            self.assertIsNone(self.ledger._state(atom))
            self.assertEqual(self.arena.inspect()["pages"], 1)
            self.assertEqual(survivor.get("b"), "two")
            with self.assertRaisesRegex(ProtocolError, "sync_packed_handle"):
                self.arena._record(old_handle, old_epoch)
            reused = survivor.put("c", "three")
            leaf = reused.find("c")
            self.assertEqual(leaf._handle & (2**32 - 1), old_handle & (2**32 - 1))
            self.assertNotEqual(leaf._handle, old_handle)
            leaf = None
            with self.assertRaisesRegex(ProtocolError, "sync_packed_handle"):
                self.arena._record(old_handle, old_epoch)
            with self.assertRaisesRegex(ProtocolError, "sync_packed_epoch"):
                self.arena._record(reused.node._handle, object())
            reused = None
            self.ledger.release(survivor)
            survivor = None

    def test_duplicate_bulk_input_releases_partial_pages_without_gc(self):
        profile = CacheProfile()
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor), ledger=self.ledger)
        raw, _, _ = baseline(profile)
        # The duplicate appears after other tables and leaf slots have been
        # allocated; the public boundary must release them even while the
        # rejection is held by its caller.
        from mesh_plus.sync.canonical import canonical, decode
        document = decode(raw)
        document["tables"]["records"].append(document["tables"]["records"][0])
        raw = canonical(document)
        saved = None
        try:
            try:
                cache.admit_baseline(raw)
            except ProtocolError as error:
                saved = error
            else:
                self.fail("duplicate baseline accepted")
            self.assertIsNone(saved.__context__)
            self.assertEqual(self.arena.live_nodes, 0)
            self.assertEqual(self.arena.inspect()["pages"], 0)
            self.assertEqual(self.arena.inspect()["controls"], 0)
        finally:
            cache.close()
            cache.close()

    def test_failed_loan_rolls_back_new_slot_edges_without_gc(self):
        with self.ledger.allocations():
            tree = MerkleMap("records").put("a", "one")
            self.ledger.retain(tree)
            before = self.arena.inspect()
            with patch.object(self.arena, "_control", side_effect=ProtocolError("sync_decoded_capacity")):
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                    tree.put("b", "two")
            self.assertEqual(self.arena.live_nodes, before["nodes"])
            self.assertEqual(self.arena.inspect()["keyEncodedCredit"], before["keyEncodedCredit"])
            self.assertEqual(tree.get("a"), "one")
            self.ledger.release(tree)
            tree = None

    def test_compressed_keys_restore_exact_bytes_and_copy_ownership(self):
        key = [["long-provider" * 20, "namespace"], ["host", "provider", "scope", "kind", "id"],
               ["owner-epoch" * 8, 1], "runtime"]
        from mesh_plus.sync.canonical import canonical
        expected = oracle("memberships", [(key, "token")])
        with self.ledger.allocations():
            tree = MerkleMap("memberships").put(key, "token")
            self.assertEqual(tree.root, expected)
            leaf = tree.find(key)
            page, index = self.arena._record(leaf._handle)
            self.assertLess(page.key_sizes[index], 0)
            raw = leaf.key
            self.assertEqual(raw, canonical(key))
            owned = leaf.input_key()
            self.assertEqual(owned.encoded, raw)
            self.assertIsNot(owned.encoded, raw)
            raw = None
            leaf.close()
            leaf = None
            self.assertEqual(owned.encoded, canonical(key))
            owned = tree = None

    def test_full_page_credit_precedes_array_allocation(self):
        other = AllocationLedger(encoded_maximum=65536 + 16384 - 1)
        arena = PackedNodeArena(other)
        try:
            with other.allocations():
                with patch("mesh_plus.sync._packed_nodes.bytearray", create=True,
                           side_effect=AssertionError("unfunded page allocation")):
                    with self.assertRaisesRegex(ProtocolError, "sync_encoded_capacity"):
                        MerkleMap("records").put("a", "one")
            self.assertEqual(arena.live_nodes, 0)
        finally:
            arena.close()
        self.assertEqual((other.used, other.reserved, other.encoded_reserved), (0, 0, 0))

    def test_normalized_callback_failure_and_terminal_close_retire_all_nodes(self):
        profile = CacheProfile()
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor), ledger=self.ledger)
        raw, _, _ = baseline(profile)
        profile.callback = lambda ctx: (_ for _ in ()).throw(ValueError("fixture rejection"))
        saved = None
        try:
            try:
                cache.admit_baseline(raw)
            except ProtocolError as error:
                saved = error
            else:
                self.fail("callback failure accepted")
            self.assertIsNone(saved.__context__)
            self.assertEqual(self.arena.live_nodes, 0)
            profile.callback = None
            candidate = cache.admit_baseline(raw)
            self.assertIsNotNone(candidate.tag)
            with self.assertRaisesRegex(ProtocolError, "sync_unconfirmed"):
                cache.acquire()
        finally:
            cache.close()
        self.assertEqual(self.arena.live_nodes, 0)
        self.assertEqual(self.arena.inspect()["controls"], 0)

    def test_current_predecessor_and_stage_roots_never_reclaim_during_proof(self):
        profile = CacheProfile()
        cache = OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor), ledger=self.ledger,
                               request_binding=REQUEST, _now_ms=lambda: 10000, _clock=CLOCK)
        try:
            raw, maps, tag = baseline(profile)
            candidate = cache.admit_baseline(raw)
            for generation in (1, 2, 3):
                if generation > 1:
                    raw, maps, tag = transaction(profile, maps, tag, generation, generation)
                    candidate = cache.stage(raw)
                before = self.arena.released_nodes
                view = cache.confirm(candidate, proof(cache, candidate), CLOCK)
                self.assertEqual(view.tag.native, tag)
                self.assertEqual(self.arena.released_nodes, before)
                if generation > 1:
                    self.assertIsNotNone(cache.store.previous)
                with self.assertRaisesRegex(ProtocolError, "sync_packed_in_use"):
                    self.arena.close()
        finally:
            cache.close()
        self.assertEqual(self.arena.live_nodes, 0)

