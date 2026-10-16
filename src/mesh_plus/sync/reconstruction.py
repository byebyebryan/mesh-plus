"""Atomic immutable reconstruction, before any freshness/authority publication.

This is the shared material engine for publisher and Reader caches. It does not
grant currentness; a separate owned proof operation must confirm an exact root.
"""

import contextlib
import secrets
import threading
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from ..protocol import ProtocolError, check
from .budget import AllocationLedger, OwnedUnit
from .canonical import Atom, FrozenObject, canonical, decode, thaw
from .commitment import ABSENT, MerkleMap, binding_digest, body_digest_encoded, native_root
from .context import reference
from .model import (
    SPACES,
    DomainIndexPatch,
    FieldTokenWrite,
    IndexRemove,
    IndexWrite,
    NativeTag,
    RuleWrite,
    SyncDescriptor,
    hex_digest,
)
from .ordered import OrderedMap, index_key

TABLE_LIMITS = {"records": 4096, "bodies": 4096, "observations": 4096, "memberships": 9 * 4096,
                "receipts": 32, "cohorts": 32, "scopes": 65536, "metadata": 65536}


@dataclass(frozen=True, slots=True)
class Operation:
    space: str
    op: str
    key: Atom
    expected: str | None
    value: Atom | None


@dataclass(frozen=True, slots=True)
class Change(OwnedUnit):
    space: str
    key: Atom
    removed: bool

    def owned_children(self):
        return (self.space, self.key)


@dataclass(frozen=True, slots=True)
class MaterialRoot(OwnedUnit):
    binding: Atom
    tag: NativeTag
    cursor: tuple
    tables: tuple
    indexes: tuple
    groups: tuple
    changes: tuple
    change_base: NativeTag | None
    affected_scopes: tuple
    invalidations: tuple

    def owned_children(self):
        return (self.binding, self.tables, self.indexes, self.groups, self.changes,
                self.tag, self.cursor, self.change_base, self.affected_scopes, self.invalidations)


class VisitMeter:
    __slots__ = ("_limit", "_lookups", "_iterations")

    def __init__(self, limit):
        self._limit, self._lookups, self._iterations = limit, 0, 0

    @property
    def lookups(self):
        return self._lookups

    @property
    def iterations(self):
        return self._iterations

    def charge(self, *, iteration=False):
        self._iterations += int(iteration)
        self._lookups += int(not iteration)
        check(self._lookups + self._iterations <= self._limit, "sync_callback_visit_capacity")


class BudgetRef:
    __slots__ = ("_ledger", "_reservations")

    def __init__(self, ledger):
        self._ledger, self._reservations = ledger, []

    @property
    def remaining(self):
        return self._ledger.maximum - self._ledger.used - self._ledger.reserved

    @contextlib.contextmanager
    def reserve(self, amount):
        reservation = self._ledger.reserve(amount)
        self._reservations.append(reservation)
        try:
            yield None
        finally:
            reservation.close()

    def charge(self, amount):
        self._reservations.append(self._ledger.reserve(amount))

    def close(self):
        for reservation in self._reservations:
            reservation.close()
        self._reservations.clear()


class PublicOperation:
    __slots__ = ("_store", "_permit", "_index", "space", "op", "expected")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync operation reference")
        object.__setattr__(self, name, value)

    def __init__(self, store, tx, index):
        operation = tx.operations[index]
        self._store, self._permit, self._index = store, tx.permit, index
        self.space, self.op, self.expected = operation.space, operation.op, operation.expected

    @property
    def key(self):
        return reference(self._store, self._permit, ("operation", "key", str(self._index), b""))

    @property
    def value(self):
        return reference(self._store, self._permit, ("operation", "value", str(self._index), b""))


class PublicStateRef:
    __slots__ = ("_store", "_permit", "_side")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync state reference")
        object.__setattr__(self, name, value)

    def __init__(self, store, permit, side):
        self._store, self._permit, self._side = store, permit, side

    def lookup(self, space, key):
        encoded = canonical(key)
        location = (self._side, "table", space, encoded)
        with self._store.borrow(self._permit, location, ()) as value:
            if value is ABSENT:
                return ABSENT
        return reference(self._store, self._permit, location)

    def index(self, name):
        return PublicIndexRef(self._store, self._permit, self._side, name)


class PublicIndexRef:
    __slots__ = ("_store", "_permit", "_side", "_name")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync index reference")
        object.__setattr__(self, name, value)

    def __init__(self, store, permit, side, name):
        self._store, self._permit, self._side, self._name = store, permit, side, name

    def get(self, key):
        location = (self._side, "index", self._name, canonical(key))
        with self._store.borrow(self._permit, location, ()) as value:
            if value is ABSENT:
                return ABSENT
        return reference(self._store, self._permit, location)

    def iter_keys(self, prefix=None):
        rank = None
        while True:
            result = self._store.index_next(self._permit, self._side, self._name, rank, prefix)
            if result is None:
                return
            rank, key = result
            yield key


class PublicStageContext:
    __slots__ = ("_store", "_permit", "descriptor", "binding", "base_tag", "proposed_tag",
                 "before", "after", "operations", "budget", "visits")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync stage context")
        object.__setattr__(self, name, value)

    def __init__(self, store, transaction):
        self._store, self._permit = store, transaction.permit
        self.descriptor = store.descriptor
        self.base_tag = None if transaction.before is None else transaction.before.tag
        self.proposed_tag = transaction.tag
        self.before = PublicStateRef(store, transaction.permit, "before")
        self.after = PublicStateRef(store, transaction.permit, "after")
        self.binding = reference(store, transaction.permit, ("after", "binding", "", b""))
        self.operations = tuple(PublicOperation(store, transaction, i) for i in range(len(transaction.operations)))
        self.budget, self.visits = transaction.budget, transaction.visits

    def changed(self, space):
        for operation in self.operations:
            if operation.space == space:
                self.visits.charge(iteration=True)
                yield operation

    def index(self, name):
        return self.before.index(name)

    def field_token(self, record_ref, field):
        values = self.after.index("$fields").get(record_ref)
        return ABSENT if values is ABSENT else values.get(field, ABSENT)

    def scope(self, key):
        return self.after.lookup("scopes", key)

    def cohort_members(self, cohort):
        yield from self._store.group_members(self._permit, cohort)

    def dependents(self, dependency):
        index = self.before.index("dependencies").get(dependency)
        if index is not ABSENT:
            for value in index:
                self.visits.charge(iteration=True)
                yield value


class _Transaction:
    def __init__(self, store, before, binding, tag, cursor, operations, tables, groups):
        self.store, self.before, self.binding, self.tag, self.cursor = store, before, binding, tag, cursor
        self.operations, self.tables, self.groups = operations, tables, groups
        self.indexes = dict(before.indexes) if before is not None else {
            name: OrderedMap() if spec.ordered else MerkleMap("index/" + name)
            for name, spec in store.index_specs.items()}
        self.indexes.setdefault("$fields", MerkleMap("index/$fields"))
        self.indexes.setdefault("$body_refs", MerkleMap("index/$body_refs"))
        self.indexes.setdefault("$rules", MerkleMap("index/$rules"))
        self.changes = []
        self.permit = secrets.token_hex(16)
        self.visits = VisitMeter(2_000_000 if before is None else 256 + len(operations) * 128)
        self.budget = BudgetRef(store.ledger)
        self.retired_refs = []
        self.member_operations = [operation for operation in operations if operation.space == "memberships"]
        self.affected_scopes, self.invalidations = (), ()


class ReconstructionStore:
    """One atomic material root, predecessor and candidate; no current claims.

    Native frame decoding and proof transport are separate boundaries. The
    normalized entry/operation methods below are internal to the owned cache.
    """

    def __init__(self, profile, *, host, ledger=None):
        self.profile, self.descriptor, self.host = profile, profile.descriptor, host
        check(type(self.descriptor) is SyncDescriptor, "sync_descriptor")
        self.ledger = AllocationLedger() if ledger is None else ledger
        self.current = self.previous = self.candidate = None
        self._transaction = None
        self._lock = threading.RLock()
        self._closed = False
        self.index_specs = {spec.name: spec for spec in self.descriptor.indexes}
        self.validators = {spec.name: (Draft202012Validator(decode(spec.key_schema)),
                                      Draft202012Validator(decode(spec.value_schema)))
                           for spec in self.descriptor.indexes}
        self._fingerprint = self.fingerprint()
        self._metadata = (self.descriptor, self.host)
        self.ledger.retain(self._metadata)
        self.last_work = {}
        self.native_descriptor_digest = bytes.fromhex(self.descriptor.native_descriptor_digest)

    def fingerprint(self):
        objects = [self.profile.descriptor]
        objects.extend(getattr(self.profile.descriptor, name) for name in self.descriptor.__slots__)
        for spec in self.profile.descriptor.indexes:
            objects.append(spec)
            objects.extend(getattr(spec, name) for name in spec.__slots__)
        for name in ("admit_baseline", "stage_delta", "check_head", "export_committed"):
            callback = getattr(self.profile, name, None)
            check(callable(callback), "sync_profile_interface")
            objects.extend((getattr(callback, "__func__", callback), getattr(callback, "__self__", None)))
        return tuple(objects)

    def _check(self):
        check(not self._closed, "sync_cache_closed")
        try:
            current = self.fingerprint()
        except Exception:
            self.close()
            raise ProtocolError("sync_profile_changed") from None
        if len(current) != len(self._fingerprint) or any(a is not b for a, b in zip(current, self._fingerprint)):
            self.close()
            raise ProtocolError("sync_profile_changed")

    def check_permit(self, permit):
        self._check()
        tx = self._transaction
        check(tx is not None and tx.permit == permit, "sync_reference_retired")
        return tx

    @contextlib.contextmanager
    def borrow(self, permit, location, path):
        with self._lock:
            tx = self.check_permit(permit)
            tx.visits.charge()
            side, kind, space, encoded = location
            check(side in {"before", "after", "operation"}, "sync_reference_side")
            if side == "operation":
                operation = tx.operations[int(space)]
                atom = operation.key if kind == "key" else operation.value
                value = None if atom is None else atom.value
            elif kind == "binding":
                value = tx.binding.value
            else:
                if side == "before":
                    root = tx.before
                    maps = {} if root is None else dict(root.tables if kind == "table" else root.indexes)
                else:
                    maps = tx.tables if kind == "table" else tx.indexes
                table = maps.get(space)
                leaf = ABSENT if table is None else table.find(decode(encoded))
                value = ABSENT if leaf is ABSENT else leaf.atom.value
            for part in path:
                value = value[part]
            yield value

    def index_next(self, permit, side, name, rank, prefix):
        with self._lock:
            tx = self.check_permit(permit)
            indexes = tx.indexes if side == "after" else ({} if tx.before is None else dict(tx.before.indexes))
            table = indexes.get(name)
            if table is None:
                return None
            if rank is None:
                rank = table.lower_bound(prefix) if prefix is not None and type(table) is OrderedMap else 0
            while rank < len(table):
                leaf = table.leaf_at(rank)
                rank += 1
                key = index_key(leaf) if type(table) is OrderedMap else decode(leaf.key)
                tx.visits.charge(iteration=True)
                if prefix is None or key[:len(prefix)] == prefix:
                    return rank, key
                if type(table) is OrderedMap:
                    return None
            return None

    def group_members(self, permit, cohort):
        rank, encoded = 0, canonical(cohort)
        while True:
            with self._lock:
                tx = self.check_permit(permit)
                group = tx.groups.get(encoded)
                if group is None or rank >= len(group[1]):
                    return
                leaf = group[1].leaf_at(rank)
                rank += 1
                tx.visits.charge(iteration=True)
                key, value = decode(leaf.key), thaw(leaf.atom.value)
            yield key, value

    def _groups(self, table):
        grouped = {}
        for leaf in table.leaves():
            key = decode(leaf.key)
            check(type(key) is list and len(key) == 4, "sync_membership_key")
            check(key[3] in self.descriptor.fields, "sync_membership_field")
            hex_digest(thaw(leaf.atom.value))
            cohort, remainder = key[0], key[1:]
            encoded = canonical(cohort)
            grouped.setdefault(encoded, (Atom.own(cohort), []))[1].append((remainder, leaf.atom))
        check(len(grouped) <= 32, "sync_cohort_capacity")
        return {key: (cohort, MerkleMap.baseline_atoms("cohort-members", values))
                for key, (cohort, values) in grouped.items()}

    def _apply(self, tx, operation):
        check(type(operation) is Operation and operation.space in SPACES, "sync_operation")
        check(operation.op in {"put", "remove"}, "sync_operation_kind")
        key = thaw(operation.key.value)
        old = tx.tables[operation.space]
        expected = ABSENT if operation.expected is None else bytes.fromhex(hex_digest(operation.expected))
        if operation.op == "put":
            check(type(operation.value) is Atom, "sync_operation_value")
            if operation.space == "bodies":
                check(type(key) is str and body_digest_encoded(self.native_descriptor_digest,
                                                              operation.value.encoded).hex() == key, "sync_body_digest")
            tx.tables[operation.space] = old.put_atom(key, operation.value, expected=expected)
        else:
            check(operation.expected is not None and operation.value is None, "sync_remove_shape")
            tx.tables[operation.space] = old.remove(key, expected=expected)
        check(len(tx.tables[operation.space]) <= TABLE_LIMITS[operation.space], "sync_table_capacity")
        if operation.space == "memberships":
            check(type(key) is list and len(key) == 4, "sync_membership_key")
            check(key[3] in self.descriptor.fields, "sync_membership_field")
            if operation.op == "put":
                hex_digest(thaw(operation.value.value))
            encoded = canonical(key[0])
            cohort, group = tx.groups.get(encoded, (Atom.own(key[0]), MerkleMap("cohort-members")))
            if operation.op == "put":
                group = group.put_atom(key[1:], operation.value)
            else:
                group = group.remove(key[1:])
            if len(group):
                tx.groups[encoded] = (cohort, group)
            else:
                tx.groups.pop(encoded, None)
            check(len(tx.groups) <= 32, "sync_cohort_capacity")
        tx.changes.append(Change(operation.space, operation.key, operation.op == "remove"))

    def _patch(self, tx, patch):
        check(type(patch) is DomainIndexPatch, "sync_domain_patch")
        seen = set()
        for write in patch.writes:
            check(type(write) is IndexWrite and write.index in self.index_specs, "sync_index_write")
            key, value = Atom.own(write.key), Atom.own(write.value)
            check((write.index, key.encoded) not in seen, "sync_duplicate_index_operation")
            seen.add((write.index, key.encoded))
            spec = self.index_specs[write.index]
            check(len(value.encoded) <= spec.max_value_bytes, "sync_index_value_capacity")
            self.validators[write.index][0].validate(thaw(key.value))
            self.validators[write.index][1].validate(thaw(value.value))
            tx.indexes[write.index] = tx.indexes[write.index].put_atom(thaw(key.value), value)
            check(len(tx.indexes[write.index]) <= spec.max_entries, "sync_index_entry_capacity")
        for remove in patch.removes:
            check(type(remove) is IndexRemove and remove.index in self.index_specs, "sync_index_remove")
            key = Atom.own(remove.key)
            check((remove.index, key.encoded) not in seen, "sync_duplicate_index_operation")
            seen.add((remove.index, key.encoded))
            tx.indexes[remove.index] = tx.indexes[remove.index].remove(thaw(key.value))
        fields = {}
        changed_fields = []
        for item in patch.field_tokens:
            check(type(item) is FieldTokenWrite and item.field in self.descriptor.fields, "sync_field_token")
            key = Atom.own(item.record_ref)
            ref = thaw(key.value)
            check(type(ref) is list and len(ref) == 2, "sync_record_ref")
            slot = tx.tables["records"].get(ref[0])
            check(item.token is None or slot is not ABSENT and thaw(slot["birth"]) == ref[1],
                  "sync_field_record_birth")
            check(("$fields", key.encoded, item.field) not in seen, "sync_duplicate_field_token")
            seen.add(("$fields", key.encoded, item.field))
            if key.encoded not in fields:
                old = tx.indexes["$fields"].get(thaw(key.value))
                fields[key.encoded] = (key, {} if old is ABSENT else thaw(old))
            values = fields[key.encoded][1]
            if item.token is None:
                # Record removal already retires its complete field/rule index.
                check(item.field in values or ref in tx.retired_refs, "sync_missing_field_token")
                values.pop(item.field, None)
            else:
                token = hex_digest(item.token)
                if values.get(item.field) != token:
                    changed_fields.append((key, item.field, token))
                values[item.field] = token
        for key, values in fields.values():
            if values:
                tx.indexes["$fields"] = tx.indexes["$fields"].put(thaw(key.value), values)
            elif tx.indexes["$fields"].get(thaw(key.value)) is not ABSENT:
                tx.indexes["$fields"] = tx.indexes["$fields"].remove(thaw(key.value))
        for operation in patch.membership_expansion:
            # Normalization of compact groups is a native-adapter responsibility;
            # the engine still independently checks exact old tokens and roots.
            from .model import DerivedMembershipOperation
            check(type(operation) is DerivedMembershipOperation, "sync_membership_expansion")
            value = None if operation.op == "remove" else Atom.own(hex_digest(operation.value))
            normalized = Operation("memberships", operation.op, Atom.own(operation.key), operation.expected, value)
            check(all(normalized.key.encoded != old.key.encoded for old in tx.member_operations),
                  "sync_duplicate_operation")
            tx.member_operations.append(normalized)
            self._apply(tx, normalized)
        # Cross-check affected field/member links using at most 32 cohort heads,
        # without another N-cell reverse index or a walk over untouched members.
        for record, field, token in changed_fields:
            ref = thaw(record.value)
            check(type(ref) is list and len(ref) == 2, "sync_record_ref")
            for cohort, _ in tx.groups.values():
                leaf = tx.tables["memberships"].find([thaw(cohort.value), *ref, field])
                check(leaf is ABSENT or leaf.atom.value == token, "sync_member_content_token")
        for operation in tx.member_operations:
            if operation.op != "put":
                continue
            key = thaw(operation.key.value)
            values = tx.indexes["$fields"].get(key[1:3])
            check(values is not ABSENT and values.get(key[3]) == operation.value.value, "sync_member_content_token")
        for item in patch.changed_rules:
            check(type(item) is RuleWrite, "sync_rule_write")
            key, value = Atom.own(item.key), Atom.own(item.value)
            check(("$rules", key.encoded) not in seen, "sync_duplicate_rule")
            seen.add(("$rules", key.encoded))
            ref = thaw(key.value)
            check(type(ref) is list and len(ref) == 2, "sync_record_ref")
            slot = tx.tables["records"].get(ref[0])
            check(slot is not ABSENT and thaw(slot["birth"]) == ref[1], "sync_rule_record_birth")
            check(len(value.encoded) <= 16384, "sync_rule_capacity")
            tx.indexes["$rules"] = tx.indexes["$rules"].put_atom(ref, value)
        for key in patch.removed_rules:
            owned = Atom.own(key)
            check(("$rules", owned.encoded) not in seen, "sync_duplicate_rule")
            seen.add(("$rules", owned.encoded))
            if tx.indexes["$rules"].get(thaw(owned.value)) is not ABSENT:
                tx.indexes["$rules"] = tx.indexes["$rules"].remove(thaw(owned.value))
        # These remain immutable, bounded data. They describe affected output;
        # they never grant authority or bypass receipt/head checks.
        tx.affected_scopes = tuple(Atom.own(key) for key in patch.affected_scopes)
        tx.invalidations = tuple(Atom.own(item) for item in patch.invalidations)
        check(len(tx.affected_scopes) <= TABLE_LIMITS["scopes"] and
              len(tx.invalidations) <= 4096, "sync_patch_capacity")

    def _links(self, tx):
        """Maintain record/body/observation references using affected keys only."""
        touched = {}
        for operation in tx.operations:
            if operation.space == "records":
                touched[operation.key.encoded] = thaw(operation.key.value)
            elif operation.space == "observations":
                key = thaw(operation.key.value)
                check(type(key) is list and len(key) == 2, "sync_observation_key")
                touched[canonical(key[0])] = key[0]
                if operation.op == "put":
                    slot = tx.tables["records"].get(key[0])
                    check(slot is not ABSENT and thaw(slot["birth"]) == key[1],
                          "sync_observation_record_birth")
            elif operation.space == "bodies" and tx.before is not None:
                identity = dict(tx.before.indexes)["$body_refs"].get(thaw(operation.key.value))
                if identity is not ABSENT:
                    touched[canonical(thaw(identity))] = thaw(identity)
        old_records = None if tx.before is None else dict(tx.before.tables)["records"]
        links = tx.indexes["$body_refs"]
        updates = []
        for identity in touched.values():
            check(type(identity) is list and len(identity) == 5 and identity[0] == self.host and
                  all(type(part) is str and part for part in identity), "sync_record_identity")
            old = ABSENT if old_records is None else old_records.get(identity)
            new = tx.tables["records"].get(identity)
            for value in (old, new):
                if value is not ABSENT:
                    check(type(value) is FrozenObject and "body" in value and "birth" in value, "sync_record_slot")
                    hex_digest(value["body"])
                    check(type(value["birth"]) is tuple and len(value["birth"]) == 2, "sync_record_birth")
            if old is not ABSENT and (new is ABSENT or old["body"] != new["body"]):
                links = links.remove(old["body"])
            if old is not ABSENT and (new is ABSENT or old["birth"] != new["birth"]):
                ref = [identity, thaw(old["birth"])]
                tx.retired_refs.append(ref)
                if tx.indexes["$fields"].get(ref) is not ABSENT:
                    tx.indexes["$fields"] = tx.indexes["$fields"].remove(ref)
                if tx.indexes["$rules"].get(ref) is not ABSENT:
                    tx.indexes["$rules"] = tx.indexes["$rules"].remove(ref)
            if new is not ABSENT:
                check(new["birth"][0] == tx.cursor[0] and type(new["birth"][1]) is int and
                      0 <= new["birth"][1] <= tx.tag.generation, "sync_record_birth")
                check(tx.tables["bodies"].find(new["body"]) is not ABSENT, "sync_dangling_body")
                check(tx.tables["observations"].find([identity, thaw(new["birth"])]) is not ABSENT,
                      "sync_missing_observations")
                if old is ABSENT or old["body"] != new["body"]:
                    updates.append((new["body"], identity))
        for body, identity in updates:
            check(links.find(body) is ABSENT, "sync_shared_record_body")
            links = links.put(body, identity)
        tx.indexes["$body_refs"] = links
        check(len(links) == len(tx.tables["bodies"]) == len(tx.tables["records"]), "sync_orphan_body")
        check(len(tx.tables["observations"]) == len(tx.tables["records"]), "sync_orphan_observations")

    def _member_links(self, tx):
        for identity, birth in tx.retired_refs:
            cohorts = {encoded: cohort for encoded, (cohort, _) in tx.groups.items()}
            if tx.before is not None:
                cohorts.update({encoded: cohort for encoded, (cohort, _) in tx.before.groups})
            for cohort in cohorts.values():
                for field in self.descriptor.fields:
                    check(tx.tables["memberships"].find([thaw(cohort.value), identity, birth, field]) is ABSENT,
                          "sync_retired_membership")
        for operation in tx.member_operations:
            if operation.op != "put":
                continue
            key = thaw(operation.key.value)
            check(type(key) is list and len(key) == 4, "sync_membership_key")
            slot = tx.tables["records"].get(key[1])
            check(slot is not ABSENT and thaw(slot["birth"]) == key[2], "sync_member_record_birth")

    def _seals(self, tx):
        # The native first sync family names its generic seal tuple `seal`.
        # Domain support/reobservation meaning remains in the pure profile.
        for leaf in tx.tables["cohorts"].leaves():
            cohort, value = decode(leaf.key), leaf.atom.value
            check(type(value) is FrozenObject and "seal" in value, "sync_cohort_seal")
            seal = value["seal"]
            check(type(seal) is tuple and len(seal) == 3 and type(seal[0]) is int and
                  0 <= seal[0] <= tx.tag.generation and type(seal[2]) is int and seal[2] >= 0, "sync_cohort_seal")
            group = tx.groups.get(canonical(cohort))
            tree = MerkleMap("cohort-members") if group is None else group[1]
            check(seal[1] == tree.root.hex() and seal[2] == len(tree), "sync_cohort_seal_root")
            if tx.before is not None:
                old = dict(tx.before.tables)["cohorts"].get(cohort)
                if old is not ABSENT:
                    previous = old["seal"]
                    check(seal[0] >= previous[0], "sync_cohort_seal_regression")
                    if seal[1:] != previous[1:]:
                        check(seal[0] > previous[0], "sync_cohort_seal_version")
        for encoded in tx.groups:
            check(tx.tables["cohorts"].find(decode(encoded)) is not ABSENT, "sync_missing_cohort_head")

    def _finish(self, tx, patch, reservation):
        self._check()
        self._patch(tx, patch)
        self._member_links(tx)
        self._seals(tx)
        tx.budget.close()
        computed = native_root(thaw(tx.binding.value), tx.tag.generation, tx.tables).hex()
        check(computed == tx.tag.root, "sync_result_root")
        continuing = tx.before is not None and tx.before is self.candidate
        changes = {} if not continuing else {(item.space, item.key.encoded): item for item in tx.before.changes}
        changes.update({(item.space, item.key.encoded): item for item in tx.changes})
        change_base = None if tx.before is None else tx.before.change_base if continuing else tx.before.tag
        root = MaterialRoot(tx.binding, tx.tag, tx.cursor, tuple(tx.tables.items()), tuple(tx.indexes.items()),
                            tuple(tx.groups.items()), tuple(changes.values()), change_base,
                            tx.affected_scopes, tx.invalidations)
        self.ledger.retain(root, reservation=reservation)
        if self.candidate is not None:
            self.ledger.release(self.candidate)
        self.candidate = root
        self.last_work = {"callbackLookups": tx.visits.lookups, "callbackIterations": tx.visits.iterations,
                          "changedKeys": len(tx.changes), **self.ledger.inspect()}
        return root

    def stage_baseline(self, binding, tag, cursor, tables, *, reservation=None):
        with self._lock:
            self._check()
            if self._transaction is not None:
                self.close()
                raise ProtocolError("sync_reentrant_admission")
            check(type(tag) is NativeTag and set(tables) == set(SPACES), "sync_baseline_shape")
            owned_binding = Atom.own(binding)
            private_binding = thaw(owned_binding.value)
            check(private_binding.get("hostScope") == self.host, "sync_host_binding")
            check(binding_digest(private_binding, native=True).hex() == tag.binding, "sync_binding_digest")
            check(type(cursor) is tuple and cursor == (private_binding["ownerEpoch"], tag.generation, tag.root), "sync_cursor")
            check(all(len(tables[name]) <= TABLE_LIMITS[name] for name in SPACES), "sync_table_capacity")
            built = {name: MerkleMap.baseline(name, tables[name]) for name in SPACES}
            check(all(len(built[name]) <= TABLE_LIMITS[name] for name in SPACES), "sync_table_capacity")
            for leaf in built["bodies"].leaves():
                check(body_digest_encoded(self.native_descriptor_digest, leaf.atom.encoded).hex() == decode(leaf.key),
                      "sync_body_digest")
            operations = tuple(Operation(name, "put", Atom.own(decode(leaf.key)), None, leaf.atom)
                               for name in SPACES for leaf in built[name].leaves())
            tx = _Transaction(self, None, owned_binding, tag, cursor, operations, built, self._groups(built["memberships"]))
            self._transaction = tx
            try:
                self._links(tx)
                patch = self.profile.admit_baseline(PublicStageContext(self, tx))
                return self._finish(tx, patch, reservation)
            finally:
                tx.budget.close()
                self._transaction = None

    def stage_delta(self, base, result, cursor, operations, *, reservation=None):
        with self._lock:
            self._check()
            if self._transaction is not None:
                self.close()
                raise ProtocolError("sync_reentrant_admission")
            before = self.candidate if self.candidate is not None else self.current
            check(before is not None and before.tag == base, "sync_wrong_base")
            check(type(result) is NativeTag and result.binding == base.binding and
                  result.generation > base.generation, "sync_result_tag")
            check(cursor == (before.cursor[0], result.generation, result.root), "sync_cursor")
            tx = _Transaction(self, before, before.binding, result, cursor, tuple(operations),
                              dict(before.tables), dict(before.groups))
            seen = set()
            self._transaction = tx
            try:
                for operation in tx.operations:
                    check(type(operation) is Operation, "sync_operation")
                    key = (operation.space, operation.key.encoded)
                    check(key not in seen, "sync_duplicate_operation")
                    seen.add(key)
                    self._apply(tx, operation)
                self._links(tx)
                patch = self.profile.stage_delta(PublicStageContext(self, tx))
                return self._finish(tx, patch, reservation)
            finally:
                tx.budget.close()
                self._transaction = None

    def advance_material(self):
        """Internal material publication; grants no lease/currentness handle."""
        with self._lock:
            self._check()
            check(self._transaction is None and self.candidate is not None, "sync_no_candidate")
            if self.previous is not None:
                self.ledger.release(self.previous)
            self.previous, self.current, self.candidate = self.current, self.candidate, None
            return self.current.tag

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for name in ("previous", "current", "candidate"):
                root = getattr(self, name)
                if root is not None:
                    self.ledger.release(root)
                    setattr(self, name, None)
            self.ledger.release(self._metadata)
            self._metadata = self._fingerprint = ()
            self.validators.clear()
            self.index_specs.clear()
