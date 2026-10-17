"""Private phase topology; fixture DTO costs are not aggregate resource proof."""

import gc
import sys
import unittest
import weakref
from dataclasses import replace
from unittest.mock import patch

from test_sync_cache import CLOCK, REQUEST, proof
from test_sync_compact import Codec, Profile, compact, fixture, resign, transaction
from test_sync_reconstruction import BIRTH, IDENTITY

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync import IndexSpec, IndexWrite, OwnedSyncCache, RuleWrite, SyncBudgets, source_binding
from mesh_plus.sync.canonical import canonical, decode, thaw
from mesh_plus.sync.ordered import OrderedMap
from mesh_plus.sync.reconstruction import ReconstructionStore


class PatchWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.enabled = gc.isenabled()
        gc.disable()
        self.profile = Profile()
        self.profile.descriptor = replace(self.profile.descriptor, indexes=(*self.profile.descriptor.indexes,
            IndexSpec("ranked", b'{"type":"array"}', b'{"type":"object"}', ordered=True)))
        self.codec = Codec(self.profile)
        self.cache = self.make_cache()
        self.errors = []

    def make_cache(self, **kwargs):
        return OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                              native_codec=self.codec, request_binding=REQUEST, _now_ms=lambda: 10000,
                              _clock=CLOCK, **kwargs)

    def tearDown(self):
        self.cache.close()
        ledger = self.cache.ledger
        self.assertEqual((ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
                          ledger.pending_units, ledger.pending_encoded), (0, 0, 0, 0, 0, 0))
        if self.enabled:
            gc.enable()

    def reject(self, callback, code):
        try:
            callback()
        except ProtocolError as error:
            self.errors.append(error)
            self.assertEqual(str(error), code)
        else:
            self.fail("expected " + code)

    def test_index_workspace_retires_before_fields_with_caller_credit_held(self):
        from mesh_plus.sync._patch_workspace import _IndexWorkspace

        original, init, field = self.profile._admit, _IndexWorkspace.__init__, ReconstructionStore._field_patch
        refs, observed = [], []
        caller_credit = 256 * 1024

        def admit(ctx):
            ctx.budget.charge(caller_credit)
            result = original(ctx)
            writes = tuple(IndexWrite(name, ["extra", i], {"value": i})
                           for name in ("facts", "ranked") for i in range(128))
            return replace(result, writes=result.writes + writes)

        def capture(work, *args, **kwargs):
            init(work, *args, **kwargs)
            refs.append(weakref.ref(work))

        def fields(store, tx, items, layout):
            self.assertTrue(refs)
            self.assertTrue(all(ref() is None for ref in refs))
            self.assertGreaterEqual(tx.budget._charged.amount, caller_credit)
            observed.append(True)
            return field(store, tx, items, layout)
        self.profile._admit = admit
        with patch.object(_IndexWorkspace, "__init__", capture), patch.object(ReconstructionStore, "_field_patch", fields):
            self.cache.admit_baseline(compact(fixture(self.profile, member=False)[0]))
        self.assertEqual(observed, [True])
        self.assertEqual(len(refs), 1)
        root = self.cache.store.candidate
        self.assertEqual(len(dict(root.indexes)["facts"]), 129)
        ranked = dict(root.indexes)["ranked"]
        self.assertEqual([ranked.leaf_at(i).atom.value["value"] for i in range(len(ranked))], list(range(128)))

    def test_compact_duplicate_fields_reject_before_unbounded_reference_growth(self):
        self.cache.close()
        self.cache = self.make_cache(budgets=SyncBudgets(decoded_bytes=2 * 1024 * 1024))
        original, produced = self.profile._admit, []

        def admit(ctx):
            result = original(ctx)
            ctx.budget.charge(4096 + 16384 * 8)  # caller owns the repeated-reference tuple
            produced.append(True)
            return replace(result, field_tokens=(result.field_tokens[0],) * 16384)
        self.profile._admit = admit
        self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile, member=False)[0])),
                    "sync_duplicate_field_token")
        self.assertEqual(produced, [True])
        self.assertIsNone(self.cache.store.candidate)

    def test_field_groups_borrow_exact_after_alias_owners_on_both_backends(self):
        from mesh_plus.sync._packed_nodes import PackedNodeArena

        original, observed = ReconstructionStore._field_patch, []

        def fields(store, tx, items, layout):
            groups = original(store, tx, items, layout)
            observed.append((len(groups), all(group[0] is tx.compact.alias_atom(7, "after") and
                                             group[0].encoded == canonical([IDENTITY, BIRTH]) and
                                             group[0]._allocation_owner is store.ledger
                                             for group in groups.values())))
            return groups
        for backend in ("default", "packed"):
            with self.subTest(backend=backend):
                self.cache.close()
                arena = PackedNodeArena(self.cache.ledger) if backend == "packed" else None
                self.cache = self.make_cache(ledger=self.cache.ledger)
                expanded = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor))
                try:
                    first = fixture(self.profile)
                    with patch.object(ReconstructionStore, "_field_patch", fields):
                        candidate = self.cache.admit_baseline(compact(first[0]))
                    expanded.admit_baseline(canonical(first[0]))
                    self.assertEqual(candidate.tag.native, first[2])
                    def indexes(root):
                        return [(name, tuple((table.leaf_at(i).key.encoded, table.leaf_at(i).atom.encoded)
                                             for i in range(len(table))) if type(table) is OrderedMap else table.root)
                                for name, table in root.indexes]
                    self.assertEqual(indexes(self.cache.store.candidate), indexes(expanded.store.candidate))
                    self.assertTrue(observed[-1][1])
                finally:
                    expanded.close()
                    self.cache.close()
                    if arena is not None:
                        arena.close()
        self.assertEqual([row[0] for row in observed], [1, 1])

    def test_field_groups_keep_retired_and_reused_alias_birth_owners_distinct(self):
        from copy import deepcopy

        from test_sync_compact import COHORT, seal_document
        from test_sync_reconstruction import OWNER

        from mesh_plus.sync import FieldTokenWrite
        from mesh_plus.sync.commitment import MerkleMap, body_digest, field_digest

        first = fixture(self.profile)
        self.cache.admit_baseline(compact(first[0]))
        other, birth = [*IDENTITY[:-1], "replacement"], [OWNER, 2]
        changed = deepcopy(fixture(self.profile, 2, 2, member=False)[0])
        body = {"identity": other, "value": 2}
        digest = body_digest(bytes.fromhex(self.profile.descriptor.native_descriptor_digest), body).hex()
        changed["tables"]["records"] = [[other, {"alias": 7, "birth": birth, "body": digest,
                                                 "order": other, "scope": "scope"}]]
        changed["tables"]["bodies"] = [[digest, body]]
        changed["tables"]["observations"] = [[[other, birth], {"stamp": 2}]]
        token = field_digest(bytes.fromhex(self.profile.descriptor.native_descriptor_digest), other, birth,
                             "runtime", {"value": 2}).hex()
        changed["tables"]["memberships"] = [[[COHORT, other, birth, "runtime"], token]]
        tree = MerkleMap.baseline("cohort-members", [([other, birth, "runtime"], token)])
        changed["tables"]["cohorts"] = [[COHORT, {"receipt": COHORT, "seal": [2, tree.root.hex(), 1]}]]
        second = seal_document(self.profile, changed)
        admit, field = self.profile._admit, ReconstructionStore._field_patch
        observed = []

        def removed(ctx):
            result = admit(ctx)
            return replace(result, field_tokens=result.field_tokens +
                           (FieldTokenWrite([IDENTITY, BIRTH], "runtime", None),))

        def fields(store, tx, items, layout):
            groups = field(store, tx, items, layout)
            old, new = groups[canonical([IDENTITY, BIRTH])][0], groups[canonical([other, birth])][0]
            observed.append((old is tx.retired_refs[canonical([IDENTITY, BIRTH])],
                             new is tx.compact.alias_atom(7, "after"), old is not new,
                             old.encoded != new.encoded))
            return groups
        self.profile._admit = removed
        raw = transaction(self.profile, first, second,
                          groups=[[COHORT, [IDENTITY, BIRTH], 1, None, 0],
                                  [COHORT, None, None, [other, birth], 1]])
        with patch.object(ReconstructionStore, "_field_patch", fields):
            candidate = self.cache.stage(raw)
        self.assertEqual(candidate.tag.native, second[2])
        self.assertEqual(observed, [(True,) * 4])

    def test_unmatched_field_births_and_foreign_refs_preserve_rollback(self):
        from test_sync_reconstruction import OWNER

        original = self.profile._admit
        invalid = (([IDENTITY, [OWNER, 2]], "sync_field_record_birth"),
                   ([IDENTITY, [OWNER, True]], "sync_record_ref"),
                   ([["foreign", *IDENTITY[1:]], BIRTH], "sync_record_ref"))
        for ref, code in invalid:
            with self.subTest(ref=ref):
                self.profile._admit = original
                first, second = fixture(self.profile, member=False), fixture(self.profile, 2, 2, member=False)
                candidate = self.cache.admit_baseline(compact(first[0]))
                self.cache.confirm(candidate, proof(self.cache, candidate), CLOCK)
                current = self.cache.store.current

                def admit(ctx):
                    result = original(ctx)
                    return replace(result, field_tokens=tuple(replace(item, record_ref=ref)
                                                             for item in result.field_tokens))
                self.profile._admit = admit
                self.reject(lambda: self.cache.stage(transaction(self.profile, first, second)), code)
                self.assertIs(self.cache.store.current, current)
                self.assertIsNone(self.cache.store.candidate)
                self.reject(self.cache.acquire, "sync_unconfirmed")

    def test_field_ref_encoded_prepayment_precedes_comparison_buffer(self):
        from mesh_plus.sync import normalization

        original, constructed = normalization.CompactState.field_ref, []

        def at_limit(state, value):
            ledger = state.store.ledger
            maximum = ledger.encoded_maximum
            ledger.encoded_maximum = ledger.encoded + ledger.pending_encoded + ledger.encoded_reserved
            try:
                with patch.object(normalization, "canonical", lambda *args: constructed.append(args)):
                    return original(state, value)
            finally:
                ledger.encoded_maximum = maximum
        with patch.object(normalization.CompactState, "field_ref", at_limit):
            self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_encoded_capacity")
        self.assertEqual(constructed, [])
        self.assertIsNone(self.cache.store.candidate)

    def test_ordered_and_unordered_baseline_delta_match_expanded_route(self):
        original = self.profile._admit

        def admit(ctx):
            ctx.budget.charge(128 * 1024)
            result = original(ctx)
            value = result.writes[0].value["value"]
            return replace(result, writes=result.writes + tuple(
                IndexWrite(name, [i], {"value": i + value})
                for name in ("facts", "ranked") for i in reversed(range(64))))

        def indexes(root):
            return [(name, tuple((canonical(thaw(table.leaf_at(i).key.value)), table.leaf_at(i).atom.encoded)
                                for i in range(len(table))) if type(table) is OrderedMap else table.root)
                    for name, table in root.indexes]
        self.profile._admit = admit
        expanded = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor))
        try:
            first, second = fixture(self.profile, member=False), fixture(self.profile, 2, 2, member=False)
            self.cache.admit_baseline(compact(first[0]))
            expanded.admit_baseline(canonical(first[0]))
            self.assertEqual(indexes(self.cache.store.candidate), indexes(expanded.store.candidate))
            raw = transaction(self.profile, first, second)
            document = decode(raw)
            document.pop("receiptRefs")
            self.cache.stage(raw)
            expanded.stage(resign(document))
            self.assertEqual(self.cache.store.candidate.tag, expanded.store.candidate.tag)
            self.assertEqual(indexes(self.cache.store.candidate), indexes(expanded.store.candidate))
        finally:
            expanded.close()
        self.assertEqual((expanded.ledger.used, expanded.ledger.reserved, expanded.ledger.pending_units), (0, 0, 0))

    def test_duplicate_index_and_rule_operations_still_roll_back_confirmed_material(self):
        original = self.profile._admit
        for kind in ("index", "rule"):
            with self.subTest(kind=kind):
                self.profile._admit = original
                first, second = fixture(self.profile, member=False), fixture(self.profile, 2, 2, member=False)
                candidate = self.cache.admit_baseline(compact(first[0]))
                self.cache.confirm(candidate, proof(self.cache, candidate), CLOCK)
                current = self.cache.store.current

                def admit(ctx):
                    result = original(ctx)
                    if kind == "index":
                        return replace(result, writes=result.writes + (result.writes[0],))
                    return replace(result, changed_rules=(RuleWrite([IDENTITY, BIRTH], {"kind": "ok"}),),
                                   removed_rules=([IDENTITY, BIRTH],))
                self.profile._admit = admit
                self.reject(lambda: self.cache.stage(transaction(self.profile, first, second)),
                            "sync_duplicate_index_operation" if kind == "index" else "sync_duplicate_rule")
                self.assertIs(self.cache.store.current, current)
                self.assertIsNone(self.cache.store.candidate)
                self.reject(self.cache.acquire, "sync_unconfirmed")

    def test_workspace_slots_and_bulk_rows_prepay_growth(self):
        from mesh_plus.sync._patch_workspace import _IndexWorkspace
        from mesh_plus.sync.budget import AllocationLedger
        from mesh_plus.sync.canonical import Atom, packed

        ledger = AllocationLedger()
        with ledger.allocations():
            work = _IndexWorkspace(ledger, baseline=True)
            key = value = owned = None
            try:
                for i in range(128):
                    key, value = Atom.own([i]), packed(Atom.own({"value": i}))
                    owned = work.remember("facts", key, "sync_duplicate_index_operation")
                    work.append("facts", owned.encoded, value)
                actual = (2 * sys.getsizeof(work.seen) + sum(sys.getsizeof(marker) for marker in work.seen) +
                          sys.getsizeof(work.entries) + sum(2 * sys.getsizeof(rows) +
                          sum(sys.getsizeof(row) for row in rows) for rows in work.entries.values()))
                self.assertGreaterEqual(work.credit.amount, actual)
                self.assertTrue(all(marker[1] is atom.encoded and atom._allocation_owner is ledger
                                    for marker, atom in work.seen.items()))
                key = Atom.own([999])
                maximum = ledger.maximum
                ledger.maximum = ledger.used + ledger.reserved
                try:
                    with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                        work.remember("facts", key, "sync_duplicate_index_operation")
                    self.assertEqual(len(work.seen), 128)
                    with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                        work.append("facts", key.encoded, value)
                    self.assertEqual(len(work.entries["facts"]), 128)
                finally:
                    ledger.maximum = maximum
            finally:
                key = value = owned = None
                work.close()
        self.assertEqual((ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
                          ledger.pending_units, ledger.pending_encoded), (0, 0, 0, 0, 0, 0))

    def test_reentrant_validator_close_keeps_workspace_receive_and_sibling_credit(self):
        from mesh_plus.sync._patch_workspace import _IndexWorkspace
        from mesh_plus.sync._schema import OwnedSchema

        owner = self.cache.input_owner()
        receive = owner.reserve(4096, encoded_bytes=1024)
        sibling = self.make_cache(ledger=self.cache.ledger)
        refs, observed = [], []
        init, validate = _IndexWorkspace.__init__, OwnedSchema.validate

        def capture(work, *args, **kwargs):
            init(work, *args, **kwargs)
            refs.append(weakref.ref(work))

        def close(schema, atom, ledger):
            if refs and not observed:
                work = refs[-1]()
                self.assertIsNotNone(work)
                credit = work.credit.amount
                owner.close()
                self.assertFalse(work.credit.closed)
                self.assertGreaterEqual(ledger.reserved, credit)
                self.assertTrue(work.seen)
                self.assertEqual(receive.encoded_bytes, 1024)
                child = sibling.input_owner().reserve(32, encoded_bytes=8)
                child.close()
                observed.append(True)
                raise RuntimeError("held index validator failure")
            return validate(schema, atom, ledger)
        try:
            with patch.object(_IndexWorkspace, "__init__", capture), patch.object(OwnedSchema, "validate", close):
                self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile, member=False)[0])),
                            "sync_admission_rejected")
            self.assertEqual(observed, [True])
            self.assertTrue(all(ref() is None for ref in refs))
            self.assertIsNone(self.cache.store.candidate)
        finally:
            receive.close()
            sibling.close()


if __name__ == "__main__":
    unittest.main()
