"""Atomic immutable reconstruction, before any freshness/authority publication.

This is the shared material engine for publisher and Reader caches. It does not
grant currentness; a separate owned proof operation must confirm an exact root.
"""

import contextlib
import secrets
import sys
import threading
from dataclasses import dataclass
from functools import wraps

from ..protocol import ProtocolError, check
from ._boundary import admission_boundary
from ._patch_workspace import apply_indexes, apply_rules
from ._schema import OwnedSchema
from .budget import AllocationLedger, OwnedUnit
from .canonical import (
    Atom,
    FrozenObject,
    InputKey,
    PackedAtom,
    canonical,
    decode,
    decode_reservation,
    packed,
    thaw,
)
from .commitment import ABSENT, MerkleMap, binding_digest, body_digest_encoded, native_root_encoded
from .context import reference
from .decoder import DecoderArena
from .model import (
    SPACES,
    DomainIndexPatch,
    FieldTokenWrite,
    NativeTag,
    SyncDescriptor,
    hex_digest,
)
from .ordered import OrderedMap, index_key

TABLE_LIMITS = {"records": 4096, "bodies": 4096, "observations": 4096, "memberships": 9 * 4096,
                "receipts": 32, "cohorts": 32, "scopes": 65536, "metadata": 65536}


def _record_ref(ref, tx):
    check(type(ref) is list and len(ref) == 2 and type(ref[0]) is list and len(ref[0]) == 5 and
          all(type(part) is str and part for part in ref[0]) and ref[0][0] == tx.store.host and
          type(ref[1]) is list and len(ref[1]) == 2 and type(ref[1][0]) is str and
          ref[1][0] == tx.cursor[0] and type(ref[1][1]) is int and
          0 <= ref[1][1] <= tx.tag.generation, "sync_record_ref")


def _decoding(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        with self.ledger.allocations(), self._arena.active():
            return method(self, *args, **kwargs)
    return run


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
    __slots__ = ("_ledger", "_reservations", "_charged", "_closed")

    def __init__(self, ledger):
        self._ledger, self._reservations = ledger, set()
        self._charged, self._closed = None, False

    @property
    def remaining(self):
        check(not self._closed, "sync_reference_retired")
        return self._ledger.maximum - self._ledger.used - self._ledger.reserved

    @contextlib.contextmanager
    def reserve(self, amount):
        check(not self._closed, "sync_reference_retired")
        check(len(self._reservations) < 64, "sync_reservation_capacity")
        reservation = self._ledger.reserve(amount)
        self._reservations.add(reservation)
        try:
            yield None
        finally:
            reservation.close()
            self._reservations.discard(reservation)

    def charge(self, amount):
        check(not self._closed, "sync_reference_retired")
        if self._charged is None:
            self._charged = self._ledger.reserve(amount)
        else:
            self._charged.grow(amount)

    def close(self):
        self._closed = True
        if self._charged is not None:
            self._charged.close()
            self._charged = None
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

    @admission_boundary
    def lookup(self, space, key):
        encoded = canonical(key)
        location = (self._side, "table", space, encoded)
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

    @admission_boundary
    def get(self, key):
        location = (self._side, "index", self._name, canonical(key))
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

    @property
    @admission_boundary
    def compact_memberships(self):
        return self._store.check_permit(self._permit).compact is not None

    @admission_boundary
    def membership_mask(self, cohort, record_ref, *, side):
        tx = self._store.check_permit(self._permit)
        tx.visits.charge()
        check(side in ("before", "after"), "sync_reference_side")
        if tx.compact is not None:
            return tx.compact.mask(cohort, record_ref, side)
        table = (None if tx.before is None else dict(tx.before.tables)["memberships"]) if side == "before" else tx.tables["memberships"]
        return 0 if table is None else sum(1 << i for i, field in enumerate(self.descriptor.fields)
                                          if table.find([cohort, *record_ref, field]) is not ABSENT)

    @admission_boundary
    def membership_changes(self):
        from .normalization import _IntentIterator
        self._store.check_permit(self._permit)
        return _IntentIterator(self._store, self._permit)


class _Transaction:
    def __init__(self, store, before, binding, tag, cursor, operations, tables, groups):
        self.store, self.before, self.binding, self.tag, self.cursor = store, before, binding, tag, cursor
        self.operations, self.tables, self.groups = operations, tables, groups
        self.indexes = dict(before.indexes) if before is not None else {
            name: OrderedMap.owned() if spec.ordered else MerkleMap("index/" + name)
            for name, spec in store.index_specs.items()}
        self.indexes.setdefault("$fields", MerkleMap("index/$fields"))
        self.indexes.setdefault("$body_refs", MerkleMap("index/$body_refs"))
        self.indexes.setdefault("$rules", MerkleMap("index/$rules"))
        self.changes = []
        self.permit = secrets.token_hex(16)
        self.visits = VisitMeter(2_000_000 if before is None else 256 + len(operations) * 128)
        self.budget = BudgetRef(store.ledger)
        self.budget.charge(1024 + len(operations) * (sys.getsizeof(object.__new__(PublicOperation)) + 16))
        self.retired_refs = {}
        self.member_operations = (operations.members() if isinstance(operations, _BaselineOperations) else
                                  [operation for operation in operations if operation.space == "memberships"])
        self.affected_scopes, self.invalidations = (), ()
        self.compact = None


class _BaselineOperations:
    """Private paged baseline view; public context.operations remains a tuple.

    Material tables already own each key/value. Recreate only the requested
    private normalized operation instead of retaining another N key wrapper
    graph. Baseline enumeration may be O(N); deltas never use this view.
    """

    def __init__(self, tables):
        self.tables = tuple((name, tables[name]) for name in SPACES)
        self.count = sum(len(table) for _, table in self.tables)
        self.cached_index, self.cached = None, None

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        check(type(index) is int and 0 <= index < self.count, "sync_operation_index")
        if index != self.cached_index:
            rank = index
            for name, table in self.tables:
                if rank < len(table):
                    leaf = table.leaf_at(rank)
                    key = leaf.input_key() if hasattr(leaf, "input_key") else InputKey.borrow(leaf.key)
                    self.cached = Operation(name, "put", key, None, leaf.atom)
                    self.cached_index = index
                    break
                rank -= len(table)
        return self.cached

    def __iter__(self):
        for name, table in self.tables:
            for leaf in table.leaves():
                key = leaf.input_key() if hasattr(leaf, "input_key") else InputKey.borrow(leaf.key)
                yield Operation(name, "put", key, None, leaf.atom)

    def members(self):
        return _BaselineMembers(dict(self.tables)["memberships"])


class _BaselineMembers:
    def __init__(self, table):
        self.table, self.extra = table, []

    def __len__(self):
        return len(self.table) + len(self.extra)

    def append(self, operation):
        self.extra.append(operation)

    def __iter__(self):
        for leaf in self.table.leaves():
            yield Operation("memberships", "put", leaf.input_key(), None, leaf.atom)
        yield from self.extra


class ReconstructionStore:
    """One atomic material root, predecessor and candidate; no current claims.

    Native frame decoding and proof transport are separate boundaries. The
    normalized entry/operation methods below are internal to the owned cache.
    """

    def __init__(self, profile, *, host, ledger=None, codec_binding=None):
        self.profile, self.descriptor, self.host = profile, profile.descriptor, host
        self._codec_binding = codec_binding
        check(type(self.descriptor) is SyncDescriptor, "sync_descriptor")
        self.ledger = AllocationLedger() if ledger is None else ledger
        self.current = self.previous = self.candidate = None
        self._transaction = None
        self._lock = threading.RLock()
        self._closed = False
        self.index_specs = {spec.name: spec for spec in self.descriptor.indexes}
        self.validators = {}
        self._fingerprint = self.fingerprint()
        schemas, retained = [], False
        try:
            for spec in self.descriptor.indexes:
                pair = []
                for raw in (spec.key_schema, spec.value_schema):
                    schema = OwnedSchema.retain(raw, self.ledger)
                    schemas.append(schema)
                    pair.append(schema)
                self.validators[spec.name] = tuple(pair)
            self._metadata = (self.descriptor, self.host, tuple(schemas))
            self.ledger.retain(self._metadata)
            retained = True
            self._arena = DecoderArena(self.ledger)
        except BaseException:
            if retained:
                self.ledger.release(self._metadata)
            self.validators.clear()
            raise
        finally:
            for schema in schemas:
                self.ledger.release(schema)
        self.last_work = {}
        self.native_descriptor_digest = bytes.fromhex(self.descriptor.native_descriptor_digest)

    def fingerprint(self):
        objects = [self.profile.descriptor]
        # SyncDescriptor/IndexSpec are exact frozen slotted types, containing
        # only immutable scalars/bytes/tuples. Identity replacement is checked;
        # there is no mutable field dictionary to walk on every value lookup.
        for name in ("admit_baseline", "stage_delta", "check_head", "export_committed"):
            callback = getattr(self.profile, name, None)
            check(callable(callback), "sync_profile_interface")
            objects.extend((getattr(callback, "__func__", callback), getattr(callback, "__self__", None)))
        if self._codec_binding is not None:
            objects.extend(self._codec_binding.fingerprint())
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

    def _atom_at(self, tx, location):
        side, kind, space, encoded = location
        check(side in {"before", "after", "operation", "compact"}, "sync_reference_side")
        if side == "compact":
            check(tx.compact is not None, "sync_reference_retired")
            return tx.compact.atom_at(kind, space)
        if side == "after" and tx.compact is not None and not tx.compact.complete:
            check(not (kind == "table" and space == "memberships" or kind == "index" and space == "$fields"),
                  "sync_memberships_pending")
        if side == "operation":
            operation = tx.operations[int(space)]
            return operation.key if kind == "key" else operation.value
        if kind == "binding":
            return tx.binding
        if side == "before":
            root = tx.before
            maps = {} if root is None else dict(root.tables if kind == "table" else root.indexes)
        else:
            maps = tx.tables if kind == "table" else tx.indexes
        table = maps.get(space)
        leaf = ABSENT if table is None else (table.find(decode(encoded)) if type(table) is OrderedMap
                                            else table.find_encoded(encoded))
        return ABSENT if leaf is ABSENT else leaf.atom

    @contextlib.contextmanager
    def peek(self, permit, location):
        with self._lock:
            tx = self.check_permit(permit)
            tx.visits.charge()
            with self._arena.active():
                yield self._atom_at(tx, location)

    @contextlib.contextmanager
    def borrow(self, permit, location, path):
        with self.peek(permit, location) as atom:
            value = atom if atom is ABSENT or atom is None else atom.value
            for part in path:
                value = value[part]
            yield value

    def materialization_budget(self, permit, location):
        with self._lock:
            tx = self.check_permit(permit)
            tx.visits.charge()
            atom = self._atom_at(tx, location)
            return 0 if atom is None or atom is ABSENT else atom.copy_budget

    @admission_boundary
    def index_next(self, permit, side, name, rank, prefix):
        with self._lock:
            tx = self.check_permit(permit)
            check(not (side == "after" and name == "$fields" and tx.compact is not None and
                       not tx.compact.complete), "sync_memberships_pending")
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
            result = self._group_next(permit, encoded, rank)
            if result is None:
                return
            rank, key, value = result
            yield key, value

    @admission_boundary
    def _group_next(self, permit, encoded, rank):
        with self._lock:
            tx = self.check_permit(permit)
            check(tx.compact is None or tx.compact.complete, "sync_memberships_pending")
            group = tx.groups.get(encoded)
            if group is None or rank >= len(group[1]):
                return None
            leaf = group[1].leaf_at(rank)
            tx.visits.charge(iteration=True)
            return rank + 1, decode(leaf.key), thaw(leaf.atom.value)

    def _groups(self, table):
        grouped = {}
        with self.ledger.reserve(1024) as scratch:
            try:
                for leaf in table.leaves():
                    with self.ledger.reserve(decode_reservation(leaf.key)):
                        key = decode(leaf.key)
                        check(type(key) is list and len(key) == 4, "sync_membership_key")
                        check(key[3] in self.descriptor.fields, "sync_membership_field")
                        hex_digest(thaw(leaf.atom.value))
                        encoded = canonical(key[0])
                        if encoded not in grouped:
                            check(len(grouped) < 32, "sync_cohort_capacity")
                            scratch.grow(1024)
                            grouped[encoded] = Atom.own(key[0]), MerkleMap("cohort-members"), []
                        _, tree, leaves = grouped[encoded]
                        if len(leaves) % 64 == 0:
                            scratch.grow(24 * 64)
                        member, hashed = tree._key(key[1:])
                        leaves.append(tree._leaf(member, hashed, leaf.atom))
                return {key: (cohort, tree._baseline_leaves(leaves))
                        for key, (cohort, tree, leaves) in grouped.items()}
            finally:
                grouped.clear()

    def _apply(self, tx, operation):
        check(type(operation) is Operation and operation.space in SPACES, "sync_operation")
        check(operation.op in {"put", "remove"}, "sync_operation_kind")
        key = thaw(operation.key.value)
        old = tx.tables[operation.space]
        expected = ABSENT if operation.expected is None else bytes.fromhex(hex_digest(operation.expected))
        if operation.op == "put":
            check(type(operation.value) in (Atom, PackedAtom), "sync_operation_value")
            if operation.space == "bodies":
                check(type(key) is str and body_digest_encoded(self.native_descriptor_digest,
                                                              operation.value.encoded).hex() == key, "sync_body_digest")
            atom = (operation.value if operation.space in {"receipts", "cohorts", "metadata"}
                    else packed(operation.value))
            tx.tables[operation.space] = old.put_atom(key, atom, expected=expected)
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
        if tx.compact is not None:
            check(type(patch.membership_expansion) is tuple and patch.membership_expansion == (),
                  "sync_compact_membership_writer")
        if tx.compact is None:
            count = sum(len(getattr(patch, name)) for name in patch.__slots__)
            tx.budget.charge(1024 + count * 256 + len(tx.member_operations) * 128)
        else:
            columns = len(self.descriptor.fields) if patch.field_tokens or tx.member_operations else 0
            # Bounded current layout/token-dictionary scratch. Per-record
            # lists/offsets pay separately; immutable patch DTOs remain
            # caller-prepaid, not copied into another generic DTO roster.
            tx.budget.charge(4096 + columns * 256 + len(tx.member_operations) * 128 +
                             (len(patch.membership_expansion) + len(patch.affected_scopes) +
                              len(patch.invalidations)) * 256)
        apply_indexes(self, tx, patch)
        layout = ({name: (position, len(canonical(name))) for position, name in enumerate(self.descriptor.fields)}
                  if patch.field_tokens or tx.member_operations else {})
        fields = self._field_patch(tx, patch.field_tokens, layout)
        if tx.compact is not None:
            tx.compact.verify_alias_patch(patch)
            tx.compact.expand(fields)
        member_keys = ({operation.key.encoded: operation.key for operation in tx.member_operations}
                       if patch.membership_expansion else {})
        for operation in patch.membership_expansion:
            # Normalization of compact groups is a native-adapter responsibility;
            # the engine still independently checks exact old tokens and roots.
            from .model import DerivedMembershipOperation
            check(type(operation) is DerivedMembershipOperation, "sync_membership_expansion")
            value = None if operation.op == "remove" else Atom.own(hex_digest(operation.value))
            normalized = Operation("memberships", operation.op, Atom.own(operation.key), operation.expected, value)
            check(normalized.key.encoded not in member_keys, "sync_duplicate_operation")
            member_keys[normalized.key.encoded] = normalized.key
            tx.member_operations.append(normalized)
            self._apply(tx, normalized)
        # Cross-check affected field/member links using at most 32 cohort heads,
        # without another N-cell reverse index or a walk over untouched members.
        for group in fields.values():
            record, _, _, changed, _ = group
            if not changed:
                continue
            ref = thaw(record.value)
            for cohort, _ in tx.groups.values():
                for position, field in enumerate(self.descriptor.fields):
                    if changed & (1 << position):
                        token = self._group_token(group, field, layout)
                        leaf = tx.tables["memberships"].find([thaw(cohort.value), *ref, field])
                        check(leaf is ABSENT or leaf.atom.encoded == token, "sync_member_content_token")
        for operation in tx.member_operations:
            if operation.op != "put":
                continue
            key = thaw(operation.key.value)
            ref = canonical(key[1:3])
            current = fields.get(ref)
            if current is None:
                tx.budget.charge(512 + len(layout) * 40)
                record = packed(Atom.own(key[1:3]))
                leaf = tx.indexes["$fields"].find_encoded(ref)
                atom = ABSENT if leaf is ABSENT else leaf.atom
                offsets = None if atom is ABSENT else self._token_offsets(atom, atom.value, layout)
                current = fields[record.encoded] = [record, None, atom, 0, offsets]
            token = self._group_token(current, key[3], layout)
            check(token is not ABSENT and token == operation.value.encoded, "sync_member_content_token")
        apply_rules(self, tx, patch)
        # These remain immutable, bounded data. They describe affected output;
        # they never grant authority or bypass receipt/head checks.
        tx.affected_scopes = tuple(Atom.own(key) for key in patch.affected_scopes)
        tx.invalidations = tuple(Atom.own(item) for item in patch.invalidations)
        check(len(tx.affected_scopes) <= TABLE_LIMITS["scopes"] and
              len(tx.invalidations) <= 4096, "sync_patch_capacity")

    @staticmethod
    def _token_offsets(atom, keys, layout):
        """Offsets into the canonical flat, hex-only private field dictionary.

        Tokens were independently shape-checked before construction. Offsets
        retain no decoded string/container graph and do not copy encoded bytes.
        """
        offsets, position = [-1] * len(layout), 1
        for number, name in enumerate(sorted(keys)):
            column, size = layout[name]
            position += int(number > 0) + size + 1
            offsets[column] = position
            position += 66  # quotes and exactly 64 ASCII hex digits
        check(position + 1 == len(atom.encoded), "sync_field_encoding")
        return tuple(offsets)

    @staticmethod
    def _group_token(group, field, layout):
        if group[2] is ABSENT:
            return ABSENT
        offset = group[4][layout[field][0]]
        return ABSENT if offset < 0 else memoryview(group[2].encoded)[offset:offset + 66]

    def _field_patch(self, tx, items, layout):
        """Group compact owned refs; decode field dictionaries one at a time."""
        groups, last_ref, last_key = {}, None, None
        for item in items:
            check(type(item) is FieldTokenWrite and item.field in self.descriptor.fields, "sync_field_token")
            if last_key is not None and item.record_ref is last_ref:
                key = last_key
            else:
                key = (packed(Atom.own(item.record_ref)) if tx.compact is None else
                       tx.compact.field_ref(item.record_ref))
                last_ref, last_key = item.record_ref, key
            group = groups.get(key.encoded)
            if group is None:
                tx.budget.charge(512 + len(layout) * 40)
                group = groups[key.encoded] = [key, [], ABSENT, 0, None]
            else:
                last_key = group[0]
            # Bound the borrowed-reference list before growing it. The same
            # exact record/field duplicate was previously rejected in the
            # second pass, after an arbitrarily long list could accumulate.
            if tx.compact is not None:
                bit = 1 << layout[item.field][0]
                check(not group[3] & bit, "sync_duplicate_field_token")
                group[3] |= bit
            group[1].append(item)
        baseline_entries = [] if tx.before is None else None
        for key, changes, _, _, _ in groups.values():
            ref = thaw(key.value)
            _record_ref(ref, tx)
            slot = tx.tables["records"].get(ref[0])
            valid = slot is not ABSENT and thaw(slot["birth"]) == ref[1]
            old = tx.indexes["$fields"].get(ref)
            values, seen, changed = {} if old is ABSENT else thaw(old), set(), 0
            for item in changes:
                check(item.token is None or valid, "sync_field_record_birth")
                check(item.field not in seen, "sync_duplicate_field_token")
                seen.add(item.field)
                previous = values.get(item.field, ABSENT)
                if item.token is None:
                    # Record retirement has already removed this whole index.
                    check(previous is not ABSENT or key.encoded in tx.retired_refs, "sync_missing_field_token")
                    values.pop(item.field, None)
                    different = previous is not ABSENT
                else:
                    token = hex_digest(item.token)
                    values[item.field] = token
                    different = previous != token
                if different:
                    changed |= 1 << self.descriptor.fields.index(item.field)
            atom = packed(Atom.own(values)) if values else ABSENT
            if values:
                if baseline_entries is None:
                    tx.indexes["$fields"] = tx.indexes["$fields"].put_atom(ref, atom)
                else:
                    baseline_entries.append((key.encoded, atom))
            elif old is not ABSENT:
                tx.indexes["$fields"] = tx.indexes["$fields"].remove(ref)
            group = groups[key.encoded]
            group[1].clear()  # borrowed patch entries are no longer needed
            group[2], group[3] = atom, changed
            group[4] = None if atom is ABSENT else self._token_offsets(atom, values, layout)
        if baseline_entries:
            tx.indexes["$fields"] = MerkleMap._from_encoded_atoms("index/$fields", baseline_entries)
        return groups

    def _links(self, tx):
        """Maintain record/body/observation references using affected keys only."""
        touched = set()
        records = tx.tables["records"]
        old_records = None if tx.before is None else dict(tx.before.tables)["records"]

        def touch(encoded):
            if encoded not in touched:
                if len(touched) % 64 == 0:
                    tx.budget.charge(128 * 64)  # touched set and update pointer list
                touched.add(encoded)

        def touch_identity(identity):
            leaf = records.find(identity)
            if leaf is ABSENT and old_records is not None:
                leaf = old_records.find(identity)
            check(leaf is not ABSENT, "sync_observation_record_birth")
            touch(leaf.key)  # borrow a charged leaf buffer, never an N-row DTO

        for operation in tx.operations:
            if operation.space == "records":
                touch(operation.key.encoded)
            elif operation.space == "observations":
                key = thaw(operation.key.value)
                check(type(key) is list and len(key) == 2, "sync_observation_key")
                touch_identity(key[0])
                if operation.op == "put":
                    slot = tx.tables["records"].get(key[0])
                    check(slot is not ABSENT and thaw(slot["birth"]) == key[1],
                          "sync_observation_record_birth")
            elif operation.space == "bodies" and tx.before is not None:
                identity = dict(tx.before.indexes)["$body_refs"].get(thaw(operation.key.value))
                if identity is not ABSENT:
                    touch_identity(thaw(identity))
        links = tx.indexes["$body_refs"]
        updates = []
        for encoded in touched:
            with self.ledger.reserve(decode_reservation(encoded)):
                identity = decode(encoded)
                links, update = self._record_links(tx, identity, old_records, links)
            if update:
                updates.append(encoded)
        if tx.before is None:
            def baseline_entries():
                for encoded in updates:
                    with self.ledger.reserve(decode_reservation(encoded)):
                        identity = decode(encoded)
                        slot = records.find_encoded(encoded).atom.value
                        yield canonical(slot["body"]), packed(Atom.own(identity))

            try:
                links = MerkleMap._from_encoded_atoms("index/$body_refs", baseline_entries())
            except ProtocolError as error:
                if error.args == ("sync_duplicate_or_colliding_key",):
                    raise ProtocolError("sync_shared_record_body") from None
                raise
        else:
            for encoded in updates:
                with self.ledger.reserve(decode_reservation(encoded)):
                    identity = decode(encoded)
                    slot = records.find_encoded(encoded).atom.value
                    check(links.find(slot["body"]) is ABSENT, "sync_shared_record_body")
                    links = links.put_atom(slot["body"], packed(Atom.own(identity)))
        tx.indexes["$body_refs"] = links
        check(len(links) == len(tx.tables["bodies"]) == len(tx.tables["records"]), "sync_orphan_body")
        check(len(tx.tables["observations"]) == len(tx.tables["records"]), "sync_orphan_observations")

    def _record_links(self, tx, identity, old_records, links):
        """One affected identity; no decoded row survives this operation."""
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
            owned = packed(Atom.own(ref))
            tx.retired_refs[owned.encoded] = owned
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
                return links, True
        return links, False

    def _member_links(self, tx):
        for retired in tx.retired_refs.values():
            identity, birth = thaw(retired.value)
            cohorts = {encoded: cohort for encoded, (cohort, _) in tx.groups.items()}
            if tx.before is not None:
                cohorts.update({encoded: cohort for encoded, (cohort, _) in tx.before.groups})
            for cohort in cohorts.values():
                for field in self.descriptor.fields:
                    check(tx.tables["memberships"].find([thaw(cohort.value), identity, birth, field]) is ABSENT,
                          "sync_retired_membership")
        checked = set()
        for operation in tx.member_operations:
            if operation.op != "put":
                continue
            key = thaw(operation.key.value)
            check(type(key) is list and len(key) == 4, "sync_membership_key")
            _record_ref(key[1:3], tx)
            ref = operation.key.value[1:3]
            if ref in checked:
                continue
            checked.add(ref)
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
        # Compact provisional overlays and the callback patch are still live
        # on the owning stage frames. Their prepaid credit survives root
        # assembly and is refunded by that stage only after those aliases drop.
        if tx.compact is None:
            tx.budget.close()
        computed = native_root_encoded(tx.binding.encoded, tx.tag.generation, tx.tables).hex()
        check(computed == tx.tag.root, "sync_result_root")
        continuing = tx.before is not None and tx.before is self.candidate
        changes = {} if not continuing else {(item.space, item.key.encoded): item for item in tx.before.changes}
        if tx.before is not None:
            changes.update({(item.space, item.key.encoded): item for item in tx.changes})
        change_base = None if tx.before is None else tx.before.change_base if continuing else tx.before.tag
        root = MaterialRoot(tx.binding, tx.tag, tx.cursor, tuple(tx.tables.items()), tuple(tx.indexes.items()),
                            tuple(tx.groups.items()), tuple(changes.values()), change_base,
                            tx.affected_scopes, tx.invalidations)
        self._arena.clear()
        self.ledger.retain(root, reservation=reservation)
        if self.candidate is not None:
            self.ledger.release(self.candidate)
        self.candidate = root
        self.last_work = {"callbackLookups": tx.visits.lookups, "callbackIterations": tx.visits.iterations,
                          "changedKeys": len(tx.changes), **self.ledger.inspect()}
        return root

    @_decoding
    def stage_compact(self, header, scope, *, reservation=None):
        from .normalization import stage
        return stage(self, header, scope, reservation=reservation)

    @_decoding
    def stage_baseline(self, binding, tag, cursor, tables, *, reservation=None):
        with self._lock:
            self._check()
            if self._transaction is not None:
                self.close()
                raise ProtocolError("sync_reentrant_admission")
            check(type(tag) is NativeTag and set(tables) == set(SPACES), "sync_baseline_shape")
            # A baseline is an explicit material replacement. Revoke public
            # authority before entering this internal engine boundary.
            self.retire_material()
            owned_binding = Atom.own(binding)
            private_binding = thaw(owned_binding.value)
            check(private_binding.get("hostScope") == self.host, "sync_host_binding")
            check(binding_digest(private_binding, native=True).hex() == tag.binding, "sync_binding_digest")
            check(type(cursor) is tuple and len(cursor) == 3 and type(cursor[1]) is int and
                  cursor == (private_binding["ownerEpoch"], tag.generation, tag.root), "sync_cursor")
            check(all(len(tables[name]) <= TABLE_LIMITS[name] for name in SPACES), "sync_table_capacity")
            built = {name: MerkleMap.baseline_atoms(name, ((key, value if type(value) is PackedAtom else
                                                          Atom.own(value) if name in {"receipts", "cohorts", "metadata"}
                                                          else packed(Atom.own(value))) for key, value in tables[name]))
                     for name in SPACES}
            check(all(len(built[name]) <= TABLE_LIMITS[name] for name in SPACES), "sync_table_capacity")
            for leaf in built["bodies"].leaves():
                check(body_digest_encoded(self.native_descriptor_digest, leaf.atom.encoded).hex() == decode(leaf.key),
                      "sync_body_digest")
            selected = getattr(self.ledger, "_packed_nodes", None)
            lazy = selected is not None and selected() is not None
            size = 4096 if lazy else 1024 + sum(map(len, built.values())) * (sys.getsizeof(object.__new__(Operation)) + 16)
            with self.ledger.reserve(size):
                operations = (_BaselineOperations(built) if lazy else
                              tuple(Operation(name, "put", InputKey.borrow(leaf.key), None, leaf.atom)
                                    for name in SPACES for leaf in built[name].leaves()))
                tx = _Transaction(self, None, owned_binding, tag, cursor, operations, built, self._groups(built["memberships"]))
                self._transaction = tx
                try:
                    self._links(tx)
                    patch = self.profile.admit_baseline(PublicStageContext(self, tx))
                    return self._finish(tx, patch, reservation)
                finally:
                    tx.budget.close()
                    self._transaction = None

    @_decoding
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
            check(type(cursor) is tuple and len(cursor) == 3 and type(cursor[1]) is int and
                  cursor == (before.cursor[0], result.generation, result.root), "sync_cursor")
            if self.previous is not None:
                # Reclamation can visit a whole older generation. Do it in
                # material staging, outside the compact nonce/proof operation.
                self.ledger.release(self.previous)
                self.previous = None
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
            check(self.previous is None, "sync_predecessor_not_retired")
            self._arena.clear()
            self.previous, self.current, self.candidate = self.current, self.candidate, None
            return self.current.tag

    def retire_material(self):
        """Explicit replacement boundary after authority/refs were revoked."""
        with self._lock:
            self._check()
            check(self._transaction is None, "sync_reentrant_admission")
            self._arena.clear()
            for name in ("previous", "current", "candidate"):
                root = getattr(self, name)
                if root is not None:
                    self.ledger.release(root)
                    setattr(self, name, None)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            self._arena.close()
            for name in ("previous", "current", "candidate"):
                root = getattr(self, name)
                if root is not None:
                    self.ledger.release(root)
                    setattr(self, name, None)
            self.ledger.release(self._metadata)
            self._metadata = self._fingerprint = ()
            self.validators.clear()
            self.index_specs.clear()
            # A supported callback can retain a retired public value/context.
            # Break profile -> reference -> store -> profile on terminal close;
            # invalid references still reject through the closed store first.
            self.profile = None
            self._codec_binding = None
