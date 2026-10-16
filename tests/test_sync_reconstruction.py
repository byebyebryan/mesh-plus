import unittest
from copy import deepcopy
from dataclasses import replace

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import Atom, canonical, thaw
from mesh_plus.sync.commitment import MerkleMap, binding_digest, body_digest, field_digest, native_root
from mesh_plus.sync.model import (
    SPACES,
    DerivedMembershipOperation,
    DomainIndexPatch,
    FieldTokenWrite,
    HeadRules,
    IndexRemove,
    IndexSpec,
    IndexWrite,
    NativeTag,
    SyncDescriptor,
)
from mesh_plus.sync.reconstruction import Operation, ReconstructionStore

OWNER = "11111111-1111-4111-8111-111111111111"
BINDING = {"hostScope": "fixture", "ownerEpoch": OWNER, "clockDomain": "time:[1]"}
IDENTITY = ["fixture", "reference", "scope", "record", "id"]
BIRTH = [OWNER, 1]


class Profile:
    def __init__(self):
        self.descriptor = SyncDescriptor(
            "reference.mesh-sync.v1", "00" * 32, "reference.sync", 1, "11" * 32,
            canonical({"protocol": "reference.sync", "version": 1}),
            indexes=(IndexSpec("facts", b'{"type":"array"}', b'{"type":"object"}'),))
        self.saved = None
        self.patch_value = None
        self.callback = None

    def _admit(self, ctx):
        writes, tokens = [], []
        for operation in ctx.changed("records"):
            if operation.op != "put":
                continue
            identity = operation.key.materialize()
            slot = operation.value.materialize()
            body = ctx.after.lookup("bodies", slot["body"])
            if body["identity"].materialize() != identity or type(body["value"]) is not int:
                raise ValueError("native domain rejection")
            self.saved = body
            self.patch_value = {"value": body["value"], "body": slot["body"]}
            writes.append(IndexWrite("facts", [identity, slot["birth"]], self.patch_value))
            token = field_digest(bytes.fromhex(self.descriptor.native_descriptor_digest), identity,
                                 slot["birth"], "runtime", {"value": body["value"]}).hex()
            tokens.append(FieldTokenWrite([identity, slot["birth"]], "runtime", token))
        if self.callback is not None:
            self.callback(ctx)
        return DomainIndexPatch(writes=tuple(writes), field_tokens=tuple(tokens))

    def admit_baseline(self, ctx):
        return self._admit(ctx)

    def stage_delta(self, ctx):
        return self._admit(ctx)

    def check_head(self, ctx, head):
        return HeadRules()

    def export_committed(self, view):
        raise AssertionError("full export must not run during admission")


def fixture(profile, value=1, generation=1):
    body = {"identity": IDENTITY, "value": value}
    body_id = body_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), body).hex()
    tables = {name: [] for name in SPACES}
    tables["records"] = [(IDENTITY, {"birth": BIRTH, "body": body_id, "order": IDENTITY, "scope": "scope"})]
    tables["bodies"] = [(body_id, body)]
    tables["observations"] = [([IDENTITY, BIRTH], {"stamp": generation})]
    maps = {name: MerkleMap.baseline(name, values) for name, values in tables.items()}
    tag = NativeTag(binding_digest(BINDING, native=True).hex(), generation,
                    native_root(BINDING, generation, maps).hex())
    return tables, maps, tag, (OWNER, generation, tag.root)


def operations(before, after):
    result = []
    for name in SPACES:
        old = {canonical(k): (k, v) for k, v in before[name].items()}
        new = {canonical(k): (k, v) for k, v in after[name].items()}
        for key in sorted(old.keys() | new.keys()):
            previous = before[name].find((old if key in old else new)[key][0])
            expected = None if key not in old else previous.value_hash.hex()
            if key not in new:
                result.append(Operation(name, "remove", Atom.own(old[key][0]), expected, None))
            elif key not in old or canonical(thaw(old[key][1])) != canonical(thaw(new[key][1])):
                result.append(Operation(name, "put", Atom.own(new[key][0]), expected, Atom.own(thaw(new[key][1]))))
    return tuple(result)


class ReconstructionTests(unittest.TestCase):
    def test_atomic_index_key_replacement_needs_only_final_declared_capacity(self):
        class Churn(Profile):
            def _admit(self, ctx):
                result = super()._admit(ctx)
                value = result.writes[0].value["value"]
                return replace(result, writes=(IndexWrite("facts", [value], {"value": value}),),
                               removes=() if ctx.base_tag is None else (IndexRemove("facts", [value - 1]),))

        profile = Churn()
        profile.descriptor = replace(profile.descriptor, indexes=(replace(profile.descriptor.indexes[0], max_entries=1),))
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, before, tag, cursor = fixture(profile)
            store.stage_baseline(BINDING, tag, cursor, tables)
            store.advance_material()
            _, after, target, cursor = fixture(profile, 2, 2)
            root = store.stage_delta(tag, target, cursor, operations(before, after))
            self.assertEqual([(key, thaw(value)) for key, value in dict(root.indexes)["facts"].items()],
                             [([2], {"value": 2})])
        finally:
            store.close()

    def test_removing_field_token_cannot_leave_an_unchanged_membership_cell(self):
        class RemoveField(Profile):
            def stage_delta(self, ctx):
                return DomainIndexPatch(field_tokens=(FieldTokenWrite([IDENTITY, BIRTH], "runtime", None),))

        profile = RemoveField()
        tables, _, _, _ = fixture(profile)
        token = field_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), IDENTITY,
                             BIRTH, "runtime", {"value": 1}).hex()
        cohort = ["provider", "scope", "runtime"]
        members = MerkleMap.baseline("cohort-members", [([IDENTITY, BIRTH, "runtime"], token)])
        tables["memberships"] = [([cohort, IDENTITY, BIRTH, "runtime"], token)]
        tables["cohorts"] = [(cohort, {"seal": [1, members.root.hex(), 1]})]
        maps = {name: MerkleMap.baseline(name, values) for name, values in tables.items()}
        binding = binding_digest(BINDING, native=True).hex()
        before = NativeTag(binding, 1, native_root(BINDING, 1, maps).hex())
        target = NativeTag(binding, 2, native_root(BINDING, 2, maps).hex())
        store = ReconstructionStore(profile, host="fixture")
        try:
            store.stage_baseline(BINDING, before, (OWNER, 1, before.root), tables)
            store.advance_material()
            with self.assertRaisesRegex(ProtocolError, "sync_member_content_token"):
                store.stage_delta(before, target, (OWNER, 2, target.root), ())
            self.assertIsNone(store.candidate)
            self.assertEqual(store.current.tag, before)
        finally:
            store.close()

    def test_interleaved_field_groups_with_distinct_equal_refs_keep_all_tokens(self):
        class Interleaved(Profile):
            def _admit(self, ctx):
                result = super()._admit(ctx)
                extras = tuple(FieldTokenWrite(deepcopy(item.record_ref), field, "44" * 32)
                               for field in ("phase", 'runtime"tail', "雪") for item in result.field_tokens)
                return replace(result, field_tokens=extras + result.field_tokens)

        profile = Interleaved()
        profile.descriptor = replace(profile.descriptor, fields=(*profile.descriptor.fields, 'runtime"tail', "雪"))
        tables, _, _, _ = fixture(profile)
        other = [*IDENTITY[:-1], "other"]
        body = {"identity": other, "value": 2}
        digest = body_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), body).hex()
        tables["records"].append((other, {"birth": BIRTH, "body": digest, "order": other, "scope": "scope"}))
        tables["bodies"].append((digest, body))
        tables["observations"].append(([other, BIRTH], {"stamp": 1}))
        cohort = ["provider", "scope", "support"]
        members = [([identity, BIRTH, field], "44" * 32)
                   for identity in (IDENTITY, other) for field in ("phase", 'runtime"tail', "雪")]
        tree = MerkleMap.baseline("cohort-members", members)
        tables["memberships"] = [([cohort, *key], value) for key, value in members]
        tables["cohorts"] = [(cohort, {"seal": [1, tree.root.hex(), len(tree)]})]
        maps = {name: MerkleMap.baseline(name, values) for name, values in tables.items()}
        tag = NativeTag(binding_digest(BINDING, native=True).hex(), 1, native_root(BINDING, 1, maps).hex())
        store = ReconstructionStore(profile, host="fixture")
        try:
            root = store.stage_baseline(BINDING, tag, (OWNER, 1, tag.root), tables)
            for identity in (IDENTITY, other):
                values = dict(root.indexes)["$fields"].get([identity, BIRTH])
                self.assertEqual(set(values), {"runtime", "phase", 'runtime"tail', "雪"})
                self.assertEqual(values["phase"], "44" * 32)
        finally:
            store.close()

    def test_failed_schema_setup_releases_already_prepared_index_schemas(self):
        profile = Profile()
        large = IndexSpec("large", canonical({"type": "string", "description": "x" * 8192}), b"{}")
        profile.descriptor = replace(profile.descriptor, indexes=(*profile.descriptor.indexes, large))
        ledger = AllocationLedger(24 * 1024)
        with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
            ReconstructionStore(profile, host="fixture", ledger=ledger)
        self.assertEqual((ledger.used, ledger.reserved, ledger.encoded, ledger.pending_units), (0, 0, 0, 0))

    def test_atomic_baseline_delta_detachment_and_retired_callback_refs(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, before, tag, cursor = fixture(profile)
            root = store.stage_baseline(BINDING, tag, cursor, tables)
            tables["bodies"][0][1]["value"] = 999
            self.assertEqual(dict(root.indexes)["facts"].get([IDENTITY, BIRTH])["value"], 1)
            profile.patch_value["value"] = 888
            self.assertEqual(dict(root.indexes)["facts"].get([IDENTITY, BIRTH])["value"], 1)
            with self.assertRaisesRegex(ProtocolError, "sync_reference_retired"):
                profile.saved.materialize()
            store.advance_material()
            _, after, next_tag, next_cursor = fixture(profile, 2, 2)
            updated = store.stage_delta(tag, next_tag, next_cursor, operations(before, after))
            self.assertEqual(dict(updated.indexes)["facts"].get([IDENTITY, BIRTH])["value"], 2)
            self.assertEqual(dict(store.current.indexes)["facts"].get([IDENTITY, BIRTH])["value"], 1)
            store.advance_material()
            self.assertEqual(store.previous.tag, tag)
            self.assertEqual(store.current.tag, next_tag)
        finally:
            store.close()
        self.assertEqual(store.ledger.used, 0)

    def test_invalid_result_and_late_callback_rejection_publish_no_patch(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, before, tag, cursor = fixture(profile)
            store.stage_baseline(BINDING, tag, cursor, tables)
            store.advance_material()
            _, after, next_tag, next_cursor = fixture(profile, 2, 2)
            wrong = replace(next_tag, root="ff" * 32)
            with self.assertRaisesRegex(ProtocolError, "sync_result_root"):
                store.stage_delta(tag, wrong, (OWNER, 2, wrong.root), operations(before, after))
            self.assertIsNone(store.candidate)
            self.assertEqual(store.current.tag, tag)
            self.assertEqual(dict(store.current.indexes)["facts"].get([IDENTITY, BIRTH])["value"], 1)
            profile.callback = lambda ctx: (_ for _ in ()).throw(ValueError("domain rejected"))
            with self.assertRaises(ValueError):
                store.stage_delta(tag, next_tag, next_cursor, operations(before, after))
            self.assertIsNone(store.candidate)
            self.assertEqual(store.current.tag, tag)
        finally:
            store.close()
        self.assertEqual(store.ledger.used, 0)

    def test_chained_stage_retires_predecessor_before_next_callback(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, maps, tag, cursor = fixture(profile)
            store.stage_baseline(BINDING, tag, cursor, tables)
            store.advance_material()
            for generation in (2, 3):
                _, after, next_tag, next_cursor = fixture(profile, generation, generation)
                store.stage_delta(tag, next_tag, next_cursor, operations(maps, after))
                if generation == 2:
                    store.advance_material()
                maps, tag = after, next_tag
            self.assertIsNotNone(store.previous)
            profile.callback = lambda ctx: self.assertIsNone(store.previous)
            _, after, next_tag, next_cursor = fixture(profile, 4, 4)
            store.stage_delta(tag, next_tag, next_cursor, operations(maps, after))
            self.assertEqual(store.current.tag.generation, 2)
            self.assertEqual(store.candidate.tag.generation, 4)
        finally:
            store.close()
        self.assertEqual((store.ledger.used, store.ledger.reserved), (0, 0))

    def test_duplicate_wrong_base_and_wrong_old_value_are_atomic(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, before, tag, cursor = fixture(profile)
            store.stage_baseline(BINDING, tag, cursor, tables)
            store.advance_material()
            _, after, next_tag, next_cursor = fixture(profile, 2, 2)
            ops = operations(before, after)
            with self.assertRaisesRegex(ProtocolError, "sync_duplicate_operation"):
                store.stage_delta(tag, next_tag, next_cursor, (*ops, ops[0]))
            with self.assertRaisesRegex(ProtocolError, "sync_wrong_base"):
                store.stage_delta(next_tag, next_tag, next_cursor, ops)
            invalid = replace(ops[0], expected="00" * 32)
            with self.assertRaisesRegex(ProtocolError, "sync_expected_value"):
                store.stage_delta(tag, next_tag, next_cursor, (invalid, *ops[1:]))
            self.assertIsNone(store.candidate)
            self.assertEqual(store.current.tag, tag)
        finally:
            store.close()

    def test_equal_descriptor_replacement_retires_owned_roots(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        tables, _, tag, cursor = fixture(profile)
        store.stage_baseline(BINDING, tag, cursor, tables)
        store.advance_material()
        profile.descriptor = replace(profile.descriptor)
        with self.assertRaisesRegex(ProtocolError, "sync_profile_changed"):
            store.advance_material()
        self.assertEqual(store.ledger.used, 0)

    def test_reentrant_admission_cannot_publish_even_when_callback_catches(self):
        profile = Profile()
        store = ReconstructionStore(profile, host="fixture")
        tables, _, tag, cursor = fixture(profile)

        def reenter(ctx):
            try:
                store.stage_baseline(BINDING, tag, cursor, tables)
            except ProtocolError:
                pass

        profile.callback = reenter
        with self.assertRaisesRegex(ProtocolError, "sync_cache_closed"):
            store.stage_baseline(BINDING, tag, cursor, tables)
        self.assertEqual(store.ledger.used, 0)
        self.assertIsNone(store.candidate)

    def test_index_iteration_is_lazy_and_revocable(self):
        profile = Profile()
        retained = []

        def enumerate_once(ctx):
            iterator = ctx.after.index("facts").iter_keys()
            retained.append(iterator)
            # Index writes are staged after callback, so initial enumeration is
            # empty without materializing a table/roster.
            self.assertEqual(list(iterator), [])
            retained.append(ctx.after)
            retained.append(ctx.budget)

        profile.callback = enumerate_once
        store = ReconstructionStore(profile, host="fixture")
        try:
            tables, _, tag, cursor = fixture(profile)
            store.stage_baseline(BINDING, tag, cursor, tables)
            with self.assertRaisesRegex(ProtocolError, "sync_reference_retired"):
                retained[-2].lookup("records", IDENTITY)
            with self.assertRaisesRegex(ProtocolError, "sync_reference_retired"):
                retained[-1].charge(1)
            with self.assertRaisesRegex(ProtocolError, "sync_reference_retired"):
                with retained[-1].reserve(1):
                    self.fail("retired callback budget was usable")
        finally:
            store.close()

    def test_orphan_observation_with_equal_count_is_rejected(self):
        profile = Profile()
        tables, _, _, _ = fixture(profile)
        tables["observations"][0] = ([IDENTITY, [OWNER, 0]], {"stamp": 1})
        maps = {name: MerkleMap.baseline(name, values) for name, values in tables.items()}
        tag = NativeTag(binding_digest(BINDING, native=True).hex(), 1, native_root(BINDING, 1, maps).hex())
        store = ReconstructionStore(profile, host="fixture")
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_observation_record_birth"):
                store.stage_baseline(BINDING, tag, (OWNER, 1, tag.root), tables)
            self.assertIsNone(store.candidate)
        finally:
            store.close()

    def test_boolean_birth_cannot_alias_integer_generation_in_derived_indexes(self):
        class InvalidBirth(Profile):
            def _admit(self, ctx):
                result = super()._admit(ctx)
                return replace(result, field_tokens=tuple(replace(token, record_ref=[IDENTITY, [OWNER, True]])
                                                         for token in result.field_tokens))

        profile = InvalidBirth()
        tables, _, tag, cursor = fixture(profile)
        store = ReconstructionStore(profile, host="fixture")
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_record_ref"):
                store.stage_baseline(BINDING, tag, cursor, tables)
            self.assertIsNone(store.candidate)
        finally:
            store.close()

    def test_derived_membership_obeys_birth_and_content_checks(self):
        class MembershipProfile(Profile):
            def _admit(self, ctx):
                patch = super()._admit(ctx)
                ref = [IDENTITY, BIRTH]
                token = patch.field_tokens[0].token
                key = [["provider", "scope", "runtime"], *ref, "runtime"]
                if self.callback is not None:
                    key[2] = [OWNER, 0]
                return replace(patch, membership_expansion=(DerivedMembershipOperation("put", key, None, token),))

        profile = MembershipProfile()
        tables, _, _, _ = fixture(profile)
        token = field_digest(bytes.fromhex(profile.descriptor.native_descriptor_digest), IDENTITY,
                             BIRTH, "runtime", {"value": 1}).hex()
        cohort = ["provider", "scope", "runtime"]
        group = MerkleMap.baseline("cohort-members", [([IDENTITY, BIRTH, "runtime"], token)])
        tables["cohorts"] = [(cohort, {"seal": [1, group.root.hex(), 1]})]
        logical = {name: MerkleMap.baseline(name, values) for name, values in tables.items()}
        logical["memberships"] = logical["memberships"].put([cohort, IDENTITY, BIRTH, "runtime"], token)
        tag = NativeTag(binding_digest(BINDING, native=True).hex(), 1, native_root(BINDING, 1, logical).hex())
        store = ReconstructionStore(profile, host="fixture")
        try:
            store.stage_baseline(BINDING, tag, (OWNER, 1, tag.root), tables)
            self.assertEqual(len(dict(store.candidate.tables)["memberships"]), 1)
        finally:
            store.close()
        profile.callback = lambda ctx: None
        store = ReconstructionStore(profile, host="fixture")
        try:
            with self.assertRaisesRegex(ProtocolError, "sync_member_content_token"):
                store.stage_baseline(BINDING, tag, (OWNER, 1, tag.root), tables)
            self.assertIsNone(store.candidate)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
