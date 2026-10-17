"""Generic R2 behavior with a test-only full-DTO codec, not Agent wire evidence."""

import gc
import unittest
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

from test_sync_cache import CLOCK, NATIVE_BINDING, REQUEST, CacheProfile, baseline, proof
from test_sync_reconstruction import BIRTH, IDENTITY, OWNER, operations

from mesh_plus.protocol import ProtocolError, check
from mesh_plus.sync import (
    AliasSpec,
    CodecSpec,
    DerivedMembershipOperation,
    IndexRemove,
    IndexSpec,
    IndexWrite,
    MembershipGroup,
    MembershipGroupChange,
    NativeTag,
    NormalizedEntry,
    NormalizedOperation,
    OwnedSyncCache,
    SyncBudgets,
    source_binding,
)
from mesh_plus.sync.canonical import canonical, decode, decode_reservation
from mesh_plus.sync.commitment import MerkleMap, binding_digest, framed, native_root
from mesh_plus.sync.reconstruction import ReconstructionStore

COHORT = ["reference", "scope", "runtime"]


class Profile(CacheProfile):
    normalization_features = ("provisional-memberships/1",)

    def __init__(self):
        super().__init__()
        self.descriptor = replace(self.descriptor, indexes=(*self.descriptor.indexes,
            IndexSpec("aliases", b'{"type":"integer"}', b'{"type":"array"}')))
        self.intents = self.context = None
        self.bad_expansion = ()

    def _admit(self, ctx):
        patch = super()._admit(ctx)
        writes, removes = list(patch.writes), []
        for op in ctx.changed("records"):
            if op.op == "put":
                slot, identity = op.value.materialize(), op.key.materialize()
                writes.append(IndexWrite("aliases", slot["alias"], [identity, slot["birth"]]))
            else:
                old = ctx.before.lookup("records", op.key.materialize())
                removes.append(IndexRemove("aliases", old["alias"]))
        # Replacement of an alias is a single final write, not two index ops.
        removes = [item for item in removes if item.key not in {write.key for write in writes if write.index == "aliases"}]
        if ctx.compact_memberships:
            self.context = ctx
            self.intents = tuple(ctx.membership_changes())
        return replace(patch, writes=tuple(writes), removes=tuple(removes), membership_expansion=self.bad_expansion)


class Header:
    def __init__(self, plan):
        self.plan = plan

    @property
    def materialization_bytes(self):
        self.plan.check()
        return decode_reservation(canonical(self.plan.header_value)) + 4096

    def materialize(self):
        self.plan.check()
        return deepcopy(self.plan.header_value)


class Plan:
    def __init__(self, raw, budget):
        self.lease = budget.reserve(len(raw) + decode_reservation(raw))
        self.document = decode(raw)
        self.header_value = deepcopy(self.document)
        self.header_value.pop("receiptRefs", None)
        kind = self.document["kind"]
        if kind in ("baseline", "transaction"):
            self.header_value["tables" if kind == "baseline" else "operations"] = {
                name: [] for name in self.document["tables" if kind == "baseline" else "operations"]}
        self.header = Header(self)

    def check(self):
        check(self.document is not None, "fixture_plan_retired")

    def close(self):
        self.document = self.header_value = None
        self.header = None
        self.lease.close()


class Iterator:
    def __init__(self, plan, generator):
        self.plan, self.generator = plan, generator

    def __iter__(self):
        return self

    def __next__(self):
        self.plan.check()
        return next(self.generator)

    def close(self):
        self.generator.close()


class Codec:
    """Intentionally decodes the small whole fixture; never production selected."""

    def __init__(self, profile):
        self.spec = CodecSpec("fixture.compact/1", "ab" * 32, profile.descriptor.native_descriptor_digest,
                              profile.descriptor.fields, AliasSpec("aliases", ("alias",), ("birth",)),
                              Profile.normalization_features)
        self.context = self.plan = self.iterator = self.pack = self.budget = None
        self.on_open = self.on_close = None
        self.calls = []

    def open(self, raw, budget):
        self.calls.append("open")
        self.plan, self.budget = Plan(raw, budget), budget
        if self.on_open:
            self.on_open()
        return self.plan

    def head(self, raw, budget):
        self.calls.append("head")
        return Plan(raw, budget)

    def entries(self, plan, space, ctx):
        self.context = ctx

        def values():
            for row in plan.document["tables"][space]:
                if space == "memberships":
                    yield MembershipGroup(*row)
                else:
                    self.pack = ctx.pack(row[1])
                    yield NormalizedEntry(space, row[0], self.pack)
        self.iterator = Iterator(plan, values())
        return self.iterator

    def operations(self, plan, space, ctx):
        self.context = ctx

        def values():
            for row in plan.document["operations"][space]:
                if space == "memberships":
                    yield MembershipGroupChange(*row)
                else:
                    value = ctx.pack(row[3]) if row[0] == "put" else None
                    yield NormalizedOperation(space, row[0], row[1], row[2], value)
        self.iterator = Iterator(plan, values())
        return self.iterator


def fixture(profile, value=1, generation=1, *, member=True):
    raw, _, _ = baseline(profile, value, generation)
    document = decode(raw)
    tables = document["tables"]
    tables["records"][0][1]["alias"] = 7
    if member:
        from mesh_plus.sync.commitment import field_digest
        token = field_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), IDENTITY, BIRTH,
                             "runtime", {"value": value}).hex()
        rows = [([IDENTITY, BIRTH, "runtime"], token)]
        tree = MerkleMap.baseline("cohort-members", rows)
        tables["memberships"] = [[[COHORT, *key], token] for key, token in rows]
        tables["cohorts"] = [[COHORT, {"receipt": COHORT, "seal": [generation, tree.root.hex(), 1]}]]
    return seal_document(profile, document)


def seal_document(profile, document):
    maps = {name: MerkleMap.baseline(name, rows) for name, rows in document["tables"].items()}
    generation = document["tag"][1]
    tag = NativeTag(binding_digest(NATIVE_BINDING, native=True).hex(), generation,
                    native_root(NATIVE_BINDING, generation, maps).hex())
    document["tag"], document["cursor"] = tag.wire(), [OWNER, generation, tag.root]
    return document, maps, tag


def compact(document):
    result = deepcopy(document)
    result["tables"]["memberships"] = [[COHORT, [IDENTITY, BIRTH], 1]] if document["tables"]["memberships"] else []
    return canonical(result)


def transaction(profile, before, after, *, groups=()):
    old_doc, old_maps, old_tag = before
    new_doc, new_maps, new_tag = after
    changes = {space: [] for space in new_maps}
    for op in operations(old_maps, new_maps):
        if op.space == "memberships":
            continue
        row = [op.op, decode(op.key.encoded), op.expected]
        if op.op == "put":
            row.append(decode(op.value.encoded))
        changes[op.space].append(row)
    changes["memberships"] = list(groups)
    doc = {"kind": "transaction", "descriptor": decode(profile.descriptor.native_descriptor),
           "nativeBindingDigest": old_tag.binding, "baseTag": old_tag.wire(), "resultTag": new_tag.wire(),
           "baseCursor": old_doc["cursor"], "resultCursor": new_doc["cursor"], "operations": changes,
           "receiptRefs": {"before": [COHORT], "after": [COHORT]}}
    return resign(doc)


def resign(document):
    document.pop("transactionId", None)
    document["transactionId"] = sha256(b"mesh-sync-transaction\0" + framed(canonical(document))).hexdigest()
    return canonical(document)


class CompactTests(unittest.TestCase):
    def setUp(self):
        self.enabled = gc.isenabled()
        gc.disable()
        self.profile = Profile()
        self.codec = Codec(self.profile)
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   native_codec=self.codec, request_binding=REQUEST, _now_ms=lambda: 10000, _clock=CLOCK)
        self.errors = []

    def tearDown(self):
        self.cache.close()
        self.assertEqual((self.cache.ledger.used, self.cache.ledger.reserved, self.cache.ledger.encoded,
                          self.cache.ledger.encoded_reserved, self.cache.ledger.pending_units), (0, 0, 0, 0, 0))
        if self.enabled:
            gc.enable()

    def reject(self, callback, code):
        try:
            callback()
        except ProtocolError as error:
            self.errors.append(error)  # retain public errors, no cyclic collection
            self.assertIn(code, str(error))
        else:
            self.fail("expected " + code)

    def test_baseline_matches_all_expanded_tables_indexes_and_seals(self):
        doc, _, tag = fixture(self.profile)
        candidate = self.cache.admit_baseline(compact(doc))
        self.assertEqual(candidate.tag.native, tag)
        expanded = ReconstructionStore(Profile(), host="fixture")
        try:
            root = expanded.stage_baseline(doc["nativeBinding"], tag, tuple(doc["cursor"]), doc["tables"])
            actual = self.cache.store.candidate
            self.assertEqual([(name, table.root) for name, table in actual.tables],
                             [(name, table.root) for name, table in root.tables])
            self.assertEqual([(name, table.root) for name, table in actual.indexes],
                             [(name, table.root) for name, table in root.indexes])
        finally:
            expanded.close()

    def test_token_change_with_omitted_or_equal_mask_expands_exact_cells(self):
        for equal in (False, True):
            with self.subTest(equal=equal):
                first, second = fixture(self.profile), fixture(self.profile, 2, 2)
                self.cache.admit_baseline(compact(first[0]))
                groups = [[COHORT, [IDENTITY, BIRTH], 1, [IDENTITY, BIRTH], 1]] if equal else []
                candidate = self.cache.stage(transaction(self.profile, first, second, groups=groups))
                self.assertEqual(candidate.tag.native, second[2])
                self.assertEqual(dict(self.cache.store.candidate.tables)["memberships"].root, second[1]["memberships"].root)

    def test_explicit_add_and_remove_groups_match_expanded_roots(self):
        first = fixture(self.profile, member=False)
        second = fixture(self.profile, generation=2)
        third = fixture(self.profile, generation=3, member=False)
        self.cache.admit_baseline(compact(first[0]))
        added = self.cache.stage(transaction(self.profile, first, second,
                                            groups=[[COHORT, None, None, [IDENTITY, BIRTH], 1]]))
        self.assertEqual(added.tag.native, second[2])
        removed = self.cache.stage(transaction(self.profile, second, third,
                                              groups=[[COHORT, [IDENTITY, BIRTH], 1, None, 0]]))
        self.assertEqual(removed.tag.native, third[2])

    def test_missing_or_removed_semantic_token_cannot_survive_retained_bit(self):
        from mesh_plus.sync import FieldTokenWrite
        doc, _, _ = fixture(self.profile)
        invalid = decode(compact(doc))
        invalid["tables"]["memberships"][0][2] = 2  # phase has no validated token
        self.reject(lambda: self.cache.admit_baseline(canonical(invalid)), "sync_member_content_token")
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        self.cache.admit_baseline(compact(first[0]))
        original = self.profile._admit

        def removed(ctx):
            result = original(ctx)
            return replace(result, field_tokens=(FieldTokenWrite([IDENTITY, BIRTH], "runtime", None),))
        self.profile._admit = removed
        self.reject(lambda: self.cache.stage(transaction(self.profile, first, second)), "sync_member_content_token")

    def test_failed_stage_preserves_prior_material_and_revokes_confirmed_claim(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        candidate = self.cache.admit_baseline(compact(first[0]))
        document = decode(proof(self.cache, candidate))
        document["head"]["cohortHeads"] = [[COHORT, {"seal": first[0]["tables"]["cohorts"][0][1]["seal"]}]]
        view = self.cache.confirm(candidate, canonical(document), CLOCK)
        self.assertEqual(self.cache.acquire().tag, view.tag)
        self.reject(lambda: self.cache.stage(transaction(self.profile, first, second,
                         groups=[[COHORT, [IDENTITY, BIRTH], 2, [IDENTITY, BIRTH], 1]])), "sync_membership_old_mask")
        self.assertEqual(self.cache.store.current.tag, first[2])
        self.assertIsNone(self.cache.store.candidate)
        self.reject(self.cache.acquire, "sync_unconfirmed")

    def test_old_mask_null_zero_bool_and_range_reject_atomically(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        bad = [(None, None, [IDENTITY, BIRTH], 1), ([IDENTITY, BIRTH], 2, [IDENTITY, BIRTH], 1),
               ([IDENTITY, BIRTH], True, [IDENTITY, BIRTH], 1), ([IDENTITY, BIRTH], 1, [IDENTITY, BIRTH], 512),
               ([IDENTITY, BIRTH], 1, None, 1), (None, None, None, 0)]
        for fields in bad:
            with self.subTest(fields=fields):
                self.cache.admit_baseline(compact(first[0]))
                self.reject(lambda: self.cache.stage(transaction(self.profile, first, second, groups=[[COHORT, *fields]])), "sync_membership")
                self.assertIsNone(self.cache.store.candidate)

    def test_duplicate_group_and_competing_callback_writer_reject(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        group = [COHORT, [IDENTITY, BIRTH], 1, [IDENTITY, BIRTH], 1]
        self.cache.admit_baseline(compact(first[0]))
        self.reject(lambda: self.cache.stage(transaction(self.profile, first, second, groups=[group, group])), "sync_duplicate_membership_group")
        token = second[0]["tables"]["memberships"][0][1]
        writer = DerivedMembershipOperation("put", [COHORT, IDENTITY, BIRTH, "runtime"], None, token)
        for expansion in ((object(),), (writer,), (writer, writer)):
            self.cache.admit_baseline(compact(first[0]))
            self.profile.bad_expansion = expansion
            self.reject(lambda: self.cache.stage(transaction(self.profile, first, second)), "sync_compact_membership_writer")
            self.profile.bad_expansion = ()

    def test_root_failure_retires_provisional_refs_intents_and_plan(self):
        doc, _, _ = fixture(self.profile)
        doc["tag"][2] = doc["cursor"][2] = "ff" * 32
        self.reject(lambda: self.cache.admit_baseline(compact(doc)), "sync_result_root")
        for callback in (lambda: self.codec.context.aliases.after.get(7), lambda: self.codec.context.pack({}),
                         lambda: self.profile.intents[0].new_mask, lambda: self.profile.intents[0].cohort,
                         lambda: next(self.codec.iterator), lambda: self.codec.budget.reserve(1)):
            self.reject(callback, "retired")
        self.assertIsNone(self.cache.store.candidate)

    def test_alias_definition_conflict_and_in_place_rebirth_reject(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        self.cache.admit_baseline(compact(first[0]))
        changed = deepcopy(second[0])
        changed["tables"]["records"][0][1]["birth"] = [OWNER, 2]
        changed = seal_document(self.profile, changed)
        self.reject(lambda: self.cache.stage(transaction(self.profile, first, changed)), "sync_alias_rebirth")
        doc = deepcopy(first[0])
        doc["tables"]["records"].append([[*IDENTITY[:-1], "other"], deepcopy(doc["tables"]["records"][0][1])])
        doc, _, _ = seal_document(self.profile, doc)
        self.reject(lambda: self.cache.admit_baseline(compact(doc)), "sync_alias_conflict")

    def test_raw_transaction_id_commits_original_reference_dictionaries(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        self.cache.admit_baseline(compact(first[0]))
        doc = decode(transaction(self.profile, first, second))
        doc["receiptRefs"]["after"] = []
        self.reject(lambda: self.cache.stage(canonical(doc)), "sync_transaction_id")

    def test_exact_duplicate_transaction_preserves_candidate_and_history(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        self.cache.admit_baseline(compact(first[0]))
        raw = transaction(self.profile, first, second)
        candidate = self.cache.stage(raw)
        history = self.cache._transaction_tokens
        self.assertIs(self.cache.stage(raw), candidate)
        self.assertEqual(self.cache._transaction_tokens, history)

    def test_missing_capability_and_changed_codec_configuration_reject(self):
        profile = Profile()
        profile.normalization_features = ()
        self.reject(lambda: OwnedSyncCache(profile, source_binding("fixture", "source", profile.descriptor),
                                          native_codec=Codec(profile)), "sync_codec_features")
        self.codec.spec = replace(self.codec.spec, encoding_id="different/1")
        self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_profile_changed")

    def test_head_uses_separate_codec_path_and_no_body_plan(self):
        doc, _, _ = fixture(self.profile, member=False)
        candidate = self.cache.admit_baseline(compact(doc))
        raw = proof(self.cache, candidate)
        view = self.cache.confirm(candidate, raw, CLOCK)
        self.assertEqual(self.codec.calls, ["open", "head"])
        self.assertEqual(view.tag, candidate.tag)
        self.assertEqual(self.cache.acquire().tag, view.tag)

    def test_before_and_after_alias_views_are_birth_guarded(self):
        doc, _, _ = fixture(self.profile)

        def inspect(ctx):
            if ctx.compact_memberships:
                ref = self.codec.context.aliases.after.resolve(7, BIRTH)
                self.assertEqual(ref.materialize(), [IDENTITY, BIRTH])
                self.reject(lambda: self.codec.context.aliases.after.resolve(7, [OWNER, 2]), "sync_alias_birth")
                self.reject(lambda: ctx.after.lookup("memberships", [COHORT, IDENTITY, BIRTH, "runtime"]),
                            "sync_memberships_pending")
                self.reject(lambda: ctx.field_token([IDENTITY, BIRTH], "runtime"), "sync_memberships_pending")
                self.assertEqual(ctx.membership_mask(COHORT, [IDENTITY, BIRTH], side="before"), 0)
                self.assertEqual(ctx.membership_mask(COHORT, [IDENTITY, BIRTH], side="after"), 1)
        self.profile.callback = inspect
        self.cache.admit_baseline(compact(doc))

    def test_same_generation_remove_put_and_missing_alias_patch_reject(self):
        first, second = fixture(self.profile), fixture(self.profile, 2, 2)
        self.cache.admit_baseline(compact(first[0]))
        doc = decode(transaction(self.profile, first, second))
        doc["operations"]["records"].append(["remove", IDENTITY, first[1]["records"].find(IDENTITY).value_hash.hex()])
        self.reject(lambda: self.cache.stage(resign(doc)), "sync_duplicate_operation")
        original = self.profile._admit

        def missing(ctx):
            result = original(ctx)
            return replace(result, writes=tuple(item for item in result.writes if item.index != "aliases"))
        self.profile._admit = missing
        self.reject(lambda: self.cache.admit_baseline(compact(first[0])), "sync_alias_patch")

    def test_alias_reuse_keeps_before_identity_and_new_birth_independent(self):
        first = fixture(self.profile, member=False)
        self.cache.admit_baseline(compact(first[0]))
        other = [*IDENTITY[:-1], "replacement"]
        changed = deepcopy(fixture(self.profile, 2, 2, member=False)[0])
        from mesh_plus.sync.commitment import body_digest
        body = {"identity": other, "value": 2}
        digest = body_digest(bytes.fromhex(self.profile.descriptor.native_descriptor_digest), body).hex()
        changed["tables"]["records"] = [[other, {"alias": 7, "birth": [OWNER, 2], "body": digest,
                                                 "order": other, "scope": "scope"}]]
        changed["tables"]["bodies"] = [[digest, body]]
        changed["tables"]["observations"] = [[[other, [OWNER, 2]], {"stamp": 2}]]
        second = seal_document(self.profile, changed)

        def inspect(ctx):
            self.assertEqual(self.codec.context.aliases.before.resolve(7, BIRTH).materialize(), [IDENTITY, BIRTH])
            self.assertEqual(self.codec.context.aliases.after.resolve(7, [OWNER, 2]).materialize(), [other, [OWNER, 2]])
            self.reject(lambda: self.codec.context.aliases.after.resolve(7, BIRTH), "sync_alias_birth")
        self.profile.callback = inspect
        candidate = self.cache.stage(transaction(self.profile, first, second))
        self.assertEqual(candidate.tag.native, second[2])

    def test_single_consume_pack_and_unconsumed_pack_reject(self):
        original = self.codec.entries

        def entries(plan, space, ctx):
            if space == "records":
                ctx.pack({"unused": True})
            return original(plan, space, ctx)
        self.codec.entries = entries
        # Configure a fresh cache so this callback is the captured identity.
        self.cache.close()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   native_codec=self.codec)
        self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_canonical_value_unconsumed")
        self.assertIsNone(self.codec.pack._atom)

    def test_retirement_inside_callback_revokes_late_publication_and_keeps_sibling(self):
        doc, _, _ = fixture(self.profile, member=False)
        owner = self.cache.input_owner()
        lease = owner.reserve(4096, encoded_bytes=256)
        sibling = OwnedSyncCache(Profile(), source_binding("fixture", "sibling", self.profile.descriptor),
                                 ledger=self.cache.ledger)
        try:
            before = self.cache.ledger.reserved

            def retire(ctx):
                owner.close()
                self.assertGreaterEqual(self.cache.ledger.reserved, 4096)
                self.assertEqual(lease.encoded_bytes, 256)
            self.profile.callback = retire
            self.reject(lambda: self.cache.admit_baseline(compact(doc)), "sync_input_retired")
            self.assertIsNone(self.cache.store.candidate)
            sibling.input_owner().reserve(0).close()
            self.assertGreaterEqual(self.cache.ledger.reserved, before)
        finally:
            lease.close()
            sibling.close()

    def test_late_malformed_value_and_strict_raw_reject_without_old_route_fallback(self):
        doc, _, _ = fixture(self.profile)
        doc["tables"]["metadata"] = [["late", 1.5]]
        # Raw strict JSON decoder independently rejects floats before adoption.
        import json
        self.reject(lambda: self.cache.admit_baseline(json.dumps(doc).encode()), "sync_json")
        self.reject(lambda: self.cache.admit_baseline(b'{"kind":"baseline","kind":"baseline"}'), "sync_duplicate_key")
        self.assertIsNone(self.cache.store.candidate)

    def test_sparse_stage_never_enumerates_unchanged_record_or_alias_rosters(self):
        first = fixture(self.profile)
        self.cache.admit_baseline(compact(first[0]))
        target = deepcopy(first[0])
        target["tag"][1] = target["cursor"][1] = 2
        target["tables"]["observations"][0][1]["stamp"] = 2
        second = seal_document(self.profile, target)
        from unittest.mock import patch
        original = MerkleMap.leaves

        def leaves(table):
            self.assertNotIn(table.space, ("records", "bodies", "observations", "index/aliases"))
            yield from original(table)
        raw = transaction(self.profile, first, second)
        with patch.object(MerkleMap, "leaves", leaves):
            self.cache.stage(raw)
        self.assertLess(self.cache.store.last_work["callbackLookups"], 64)

    def test_reused_canonical_value_rejects_second_consumption(self):
        def entries(plan, space, ctx):
            def values():
                if space == "records":
                    row = plan.document["tables"][space][0]
                    value = ctx.pack(row[1])
                    yield NormalizedEntry(space, row[0], value)
                    yield NormalizedEntry(space, [*row[0][:-1], "different"], value)
            return Iterator(plan, values())
        self.codec.entries = entries
        self.cache.close()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   native_codec=self.codec)
        self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_canonical_value_owner")

    def test_header_copy_is_refused_before_allocation_at_shared_limit(self):
        from unittest.mock import patch
        copied = []
        self.cache.close()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   native_codec=self.codec, budgets=SyncBudgets(decoded_bytes=128 * 1024))
        with patch.object(Header, "materialization_bytes", property(lambda _: 1024 * 1024)), \
                patch.object(Header, "materialize", lambda _: copied.append(True)):
            self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_decoded_capacity")
        self.assertEqual(copied, [])

    def test_iterator_failure_keeps_scratch_credit_until_owned_close_returns(self):
        closed = []

        def entries(plan, space, ctx):
            def values():
                lease = ctx.budget.reserve(4096, encoded=256)
                scratch = bytearray(4096)
                try:
                    yield NormalizedEntry(space, 1.5, ctx.pack({"invalid": True}))
                finally:
                    scratch = None
                    before = self.cache.ledger.reserved
                    lease.close()
                    self.assertEqual(self.cache.ledger.reserved, before)
                    closed.append(scratch)
            return Iterator(plan, values())
        self.codec.entries = entries
        self.cache.close()
        self.cache = OwnedSyncCache(self.profile, source_binding("fixture", "source", self.profile.descriptor),
                                   native_codec=self.codec)
        self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_json_type")
        self.assertEqual(closed, [None])

    def test_callback_and_plan_close_failure_leave_no_candidate_or_late_refs(self):
        doc, _, _ = fixture(self.profile)

        def fail(ctx):
            raise ValueError("opaque callback detail")
        self.profile.callback = fail
        self.reject(lambda: self.cache.admit_baseline(compact(doc)), "sync_admission_rejected")
        self.profile.callback = None
        from unittest.mock import patch
        original = Plan.close

        def close(plan):
            original(plan)
            raise RuntimeError("opaque close detail")
        with patch.object(Plan, "close", close):
            self.reject(lambda: self.cache.admit_baseline(compact(doc)), "sync_admission_rejected")
        self.assertIsNone(self.cache.store.candidate)

    def test_reentrant_plan_close_pins_material_credit_until_callback_unwinds(self):
        from unittest.mock import patch
        owner = self.cache.input_owner()
        receive = owner.reserve(4096, encoded_bytes=256)
        original = Plan.close
        observed = []

        def close(plan):
            original(plan)
            used = self.cache.ledger.used
            owner.close()
            self.assertIsNone(self.cache.store.candidate)
            self.assertEqual(self.cache.ledger.used, used)
            self.assertEqual(receive.encoded_bytes, 256)
            observed.append(True)
        try:
            with patch.object(Plan, "close", close):
                self.reject(lambda: self.cache.admit_baseline(compact(fixture(self.profile)[0])), "sync_input_retired")
            self.assertEqual(observed, [True])
        finally:
            receive.close()


if __name__ == "__main__":
    unittest.main()
