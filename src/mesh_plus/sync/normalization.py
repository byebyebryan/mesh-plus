"""Configured compact normalization; provisional refs grant no admission.

All live handles resolve through a transaction permit. They retain no staged
tree. Values transfer once into the ordinary reconstruction/root-check path.
"""

import weakref
from dataclasses import dataclass

from ..protocol import ProtocolError, check
from ._boundary import _retire_error, admission_boundary
from .budget import OwnedUnit
from .canonical import Atom, FrozenObject, PackedAtom, canonical, decode, packed, thaw
from .commitment import ABSENT
from .context import reference
from .model import SPACES, hex_digest

PHASES = ("records", "receipts", "cohorts", "bodies", "observations", "scopes", "metadata", "memberships")
FEATURE = "provisional-memberships/1"
_MINT = object()


@dataclass(frozen=True, slots=True)
class AliasSpec(OwnedUnit):
    index: str
    alias_path: tuple
    birth_path: tuple

    def __post_init__(self):
        check(type(self.index) is str and 0 < len(self.index) <= 128, "sync_alias_spec")
        for path in (self.alias_path, self.birth_path):
            check(type(path) is tuple and 0 < len(path) <= 8 and
                  all(type(part) is str and 0 < len(part) <= 128 for part in path), "sync_alias_spec")

    def owned_children(self):
        return self.index, self.alias_path, self.birth_path


@dataclass(frozen=True, slots=True)
class CodecSpec(OwnedUnit):
    encoding_id: str
    encoding_schema_digest: str
    native_descriptor_digest: str
    fields: tuple
    alias_spec: AliasSpec
    required_profile_features: tuple

    def __post_init__(self):
        check(type(self.encoding_id) is str and 0 < len(self.encoding_id) <= 128 and
              self.encoding_id.isascii() and all(ord(char) > 32 for char in self.encoding_id), "sync_codec_spec")
        hex_digest(self.encoding_schema_digest)
        hex_digest(self.native_descriptor_digest)
        check(type(self.fields) is tuple and len(self.fields) == 9 and
              all(type(field) is str for field in self.fields) and len(set(self.fields)) == 9, "sync_codec_fields")
        check(type(self.alias_spec) is AliasSpec, "sync_alias_spec")
        check(type(self.required_profile_features) is tuple and len(self.required_profile_features) <= 32 and
              all(type(item) is str and 0 < len(item) <= 128 for item in self.required_profile_features) and
              len(set(self.required_profile_features)) == len(self.required_profile_features) and
              FEATURE in self.required_profile_features, "sync_codec_features")

    def owned_children(self):
        return tuple(getattr(self, name) for name in self.__slots__)


@dataclass(frozen=True, slots=True)
class NormalizedEntry:
    space: str
    key: object
    value: object


@dataclass(frozen=True, slots=True)
class NormalizedOperation:
    space: str
    op: str
    key: object
    expected_old_v: str | None
    value: object = None


@dataclass(frozen=True, slots=True)
class MembershipGroup:
    cohort: object
    after_ref: object
    mask: int


@dataclass(frozen=True, slots=True)
class MembershipGroupChange:
    cohort: object
    before_ref: object
    expected_old_mask: int | None
    after_ref: object
    new_mask: int


class CanonicalValueRef:
    """Opaque stage-local single-consume value, never an input admission ref."""

    __slots__ = ("_state", "_atom", "__weakref__")

    def __init__(self, state, atom, *, _mint=None):
        check(_mint is _MINT, "sync_canonical_value_owner")
        self._state, self._atom = weakref.ref(state), atom

    def _consume(self, state):
        check(self._state() is state and self._atom is not None, "sync_canonical_value_owner")
        state.check()
        atom, self._atom = self._atom, None
        state.packs.pop(id(self), None)
        return atom

    def close(self):
        self._atom = None
        state = self._state()
        if state is not None:
            state.packs.pop(id(self), None)


class CodecBinding(OwnedUnit):
    def __init__(self, codec, profile):
        self.codec, self.profile = codec, profile
        spec = codec.spec
        check(type(spec) is CodecSpec and spec.fields == profile.descriptor.fields and
              spec.native_descriptor_digest == profile.descriptor.native_descriptor_digest and
              spec.alias_spec.index in {item.name for item in profile.descriptor.indexes}, "sync_codec_spec")
        features = getattr(profile, "normalization_features", ())
        check(type(features) is tuple and all(type(item) is str for item in features) and
              set(spec.required_profile_features) <= set(features), "sync_codec_features")
        self.spec = spec
        self.captured = self.fingerprint()

    def fingerprint(self):
        codec, spec = self.codec, self.codec.spec
        check(type(spec) is CodecSpec and type(spec.alias_spec) is AliasSpec, "sync_codec_identity")
        values = [codec, spec, *(getattr(spec, name) for name in spec.__slots__),
                  *(getattr(spec.alias_spec, name) for name in spec.alias_spec.__slots__),
                  getattr(self.profile, "normalization_features", ())]
        for name in ("open", "entries", "operations", "head"):
            callback = getattr(codec, name, None)
            check(callable(callback), "sync_codec_interface")
            values.extend((getattr(callback, "__func__", callback), getattr(callback, "__self__", None)))
        return tuple(values)

    def close(self):
        self.codec = self.profile = None
        self.captured = ()

    def owned_children(self):
        return (self.spec,)

    def owned_intrinsic(self):
        return 4096  # fixed callback/feature capture and binding controls


class AliasView:
    __slots__ = ("_store", "_permit", "_side")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable alias view")
        object.__setattr__(self, name, value)

    def __init__(self, store, permit, side):
        self._store, self._permit, self._side = store, permit, side

    @admission_boundary
    def get(self, alias):
        check(type(alias) is int and 1 <= alias < 2**64, "sync_alias")
        return reference(self._store, self._permit, ("compact", "alias-" + self._side, str(alias), b""))

    @admission_boundary
    def resolve(self, alias, birth):
        ref = self.get(alias)
        check(ref is not ABSENT and type(birth) in (tuple, list) and len(birth) == 2,
              "sync_alias_birth")
        check(ref[1][0] == birth[0] and type(birth[1]) is int and ref[1][1] == birth[1], "sync_alias_birth")
        return ref


class _AliasViews:
    __slots__ = ("before", "after")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable alias views")
        object.__setattr__(self, name, value)

    def __init__(self, store, permit):
        self.before, self.after = AliasView(store, permit, "before"), AliasView(store, permit, "after")


class NormalizationContext:
    __slots__ = ("_store", "_permit", "before", "after_records", "aliases", "binding", "descriptor", "budget", "visits")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable normalization context")
        object.__setattr__(self, name, value)

    def __init__(self, store, tx, budget):
        from .reconstruction import PublicStateRef
        self._store, self._permit = store, tx.permit
        self.before, self.after_records = (PublicStateRef(store, tx.permit, side) for side in ("before", "after"))
        self.aliases = _AliasViews(store, tx.permit)
        self.binding = reference(store, tx.permit, ("after", "binding", "", b""))
        self.descriptor, self.budget, self.visits = store.descriptor, budget, tx.visits

    @admission_boundary
    def pack(self, value):
        tx = self._store.check_permit(self._permit)
        return tx.compact.pack(value)


class MembershipGroupIntent:
    __slots__ = ("_store", "_permit", "_index")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable membership intent")
        object.__setattr__(self, name, value)

    def __init__(self, store, permit, index, *, _mint=None):
        check(_mint is _MINT, "sync_membership_intent_owner")
        self._store, self._permit, self._index = store, permit, index

    @property
    def cohort(self):
        return reference(self._store, self._permit, ("compact", "cohort", str(self._index), b""))

    @property
    def record_ref(self):
        return reference(self._store, self._permit, ("compact", "record", str(self._index), b""))

    @admission_boundary
    def _mask(self, index):
        tx = self._store.check_permit(self._permit)
        tx.visits.charge()
        return tx.compact.group_at(self._index)[index]

    @property
    def old_mask(self):
        return self._mask(2)

    @property
    def new_mask(self):
        return self._mask(3)


class _IntentIterator:
    def __init__(self, store, permit):
        self._store, self._permit, self._index, self._closed = store, permit, 0, False

    def __iter__(self):
        return self

    def __next__(self):
        tx = self._store.check_permit(self._permit)
        if self._closed or tx.compact is None or self._index >= len(tx.compact.order):
            raise StopIteration
        tx.visits.charge(iteration=True)
        result = MembershipGroupIntent(self._store, self._permit, self._index, _mint=_MINT)
        self._index += 1
        return result

    def close(self):
        self._closed = True


def _slot_path(slot, path):
    for part in path:
        check(type(slot) is FrozenObject and part in slot, "sync_alias_definition")
        slot = slot[part]
    return slot


class CompactState:
    def __init__(self, store, tx, binding):
        self.store, self.tx, self.spec = store, tx, binding.spec
        self.aliases, self.groups, self.order, self.packs = {}, {}, [], {}
        self.phase, self.complete = None, False
        tx.budget.charge(32768)  # bounded live value controls and iterator state

    def check(self):
        check(self.tx is not None and self.store.check_permit(self.tx.permit) is self.tx, "sync_reference_retired")
        return self.tx

    def pack(self, value):
        self.check()
        check(self.phase in PHASES and self.phase != "memberships", "sync_codec_phase")
        check(len(self.packs) < 64, "sync_canonical_value_capacity")
        # Keep only bounded header values decoded; body/record/facet containers
        # use the generic private canonical representation immediately.
        atom = (Atom.own(value) if self.phase in ("receipts", "cohorts", "metadata") else
                PackedAtom._from_private_json(value))
        result = CanonicalValueRef(self, atom, _mint=_MINT)
        self.packs[id(result)] = result
        return result

    @admission_boundary
    def adopt(self, item, space, seen, *, baseline):
        from .reconstruction import Operation
        tx = self.tx
        if space == "memberships":
            self.group(item, baseline=baseline)
            return
        check(type(item) is (NormalizedEntry if baseline else NormalizedOperation) and type(item.space) is str and
              item.space == space, "sync_normalized_operation")
        op, expected = ("put", None) if baseline else (item.op, item.expected_old_v)
        check(type(op) is str and op in ("put", "remove") and
              (expected is None or type(expected) is str) and
              (op != "remove" or expected is not None and item.value is None), "sync_operation")
        if expected is not None:
            hex_digest(expected)
        key = Atom.own(item.key)
        check(key.encoded not in seen, "sync_duplicate_operation")
        tx.budget.charge(512 + len(key.encoded))
        seen.add(key.encoded)
        value = None
        if op == "put":
            check(type(item.value) is CanonicalValueRef, "sync_canonical_value_owner")
            value = item.value._consume(self)
        operation = Operation(space, op, key, expected, value)
        self.store._apply(tx, operation)
        if not baseline or space == "records":
            tx.operations.append(operation)
        if baseline:
            tx.changes.clear()

    def alias_atom(self, alias, side):
        self.check()
        if side == "after" and alias in self.aliases:
            return self.aliases[alias]
        if self.tx.before is None:
            return ABSENT
        table = dict(self.tx.before.indexes)[self.spec.alias_spec.index]
        leaf = table.find(alias)
        return ABSENT if leaf is ABSENT else leaf.atom

    def definitions(self):
        tx, spec = self.tx, self.spec.alias_spec
        additions = {}
        for operation in tx.operations:
            if operation.space != "records":
                continue
            identity = thaw(operation.key.value)
            old = ABSENT if tx.before is None else dict(tx.before.tables)["records"].get(identity)
            new = tx.tables["records"].get(identity)
            old_alias = None
            if old is not ABSENT:
                old_alias = _slot_path(old, spec.alias_path)
            if new is ABSENT:
                tx.budget.charge(256)
                self.aliases[old_alias] = ABSENT
                continue
            alias, birth = _slot_path(new, spec.alias_path), _slot_path(new, spec.birth_path)
            check(type(alias) is int and 1 <= alias < 2**64 and type(birth) is tuple and len(birth) == 2 and
                  birth[0] == tx.cursor[0] and type(birth[1]) is int and 1 <= birth[1] <= tx.tag.generation,
                  "sync_alias_definition")
            if old is not ABSENT:
                check(alias == old_alias and birth == _slot_path(old, spec.birth_path), "sync_alias_rebirth")
            check(alias not in additions, "sync_alias_conflict")
            tx.budget.charge(512)
            additions[alias] = packed(Atom.own([identity, thaw(birth)]))
        for alias, ref in additions.items():
            old = self.alias_atom(alias, "after")
            check(old is ABSENT or old.encoded == ref.encoded, "sync_alias_conflict")
            self.aliases[alias] = ref

    def _ref(self, value, side):
        from .reconstruction import _record_ref
        _record_ref(value, self.tx)
        check(value[1][1] > 0, "sync_record_ref")
        tables = ({} if self.tx.before is None else dict(self.tx.before.tables)) if side == "before" else self.tx.tables
        table = tables.get("records")
        slot = ABSENT if table is None else table.get(value[0])
        check(slot is not ABSENT and thaw(_slot_path(slot, self.spec.alias_spec.birth_path)) == value[1],
              "sync_alias_birth")

    def mask(self, cohort, record, side):
        check(side in ("before", "after"), "sync_reference_side")
        key = canonical([cohort, *record])
        if side == "after" and key in self.groups:
            return self.groups[key][3]
        before = self.tx.before
        if before is None:
            return 0
        table = dict(before.tables)["memberships"]
        return sum(1 << i for i, field in enumerate(self.spec.fields)
                   if table.find([cohort, *record, field]) is not ABSENT)

    def group(self, item, *, baseline):
        tx = self.tx
        if baseline:
            check(type(item) is MembershipGroup and type(item.mask) is int and 1 <= item.mask <= 511,
                  "sync_membership_group")
            before, old, after, new = None, None, item.after_ref, item.mask
        else:
            check(type(item) is MembershipGroupChange, "sync_membership_group")
            before, old, after, new = item.before_ref, item.expected_old_mask, item.after_ref, item.new_mask
            check((before is None) == (old is None) and (old is None or type(old) is int and 1 <= old <= 511) and
                  type(new) is int and 0 <= new <= 511 and (after is None) == (new == 0) and
                  not (before is None and after is None), "sync_membership_mask")
        if before is not None:
            self._ref(before, "before")
        if after is not None:
            self._ref(after, "after")
        check(before is None or after is None or canonical(before) == canonical(after), "sync_membership_group_identity")
        record = after if after is not None else before
        cohort = Atom.own(item.cohort)
        ref = packed(Atom.own(record))
        marker = canonical([item.cohort, *record])
        check(marker not in self.groups, "sync_duplicate_membership_group")
        check(len(self.groups) < (36864 if baseline else 73728), "sync_membership_group_capacity")
        actual = self.mask(item.cohort, record, "before")
        check(actual == (old or 0), "sync_membership_old_mask")
        tx.budget.charge(1024 + len(marker))
        self.groups[marker] = cohort, ref, actual, new
        self.order.append(marker)

    def group_at(self, index):
        self.check()
        return self.groups[self.order[index]]

    def atom_at(self, kind, key):
        if kind.startswith("alias-"):
            return self.alias_atom(int(key), kind[6:])
        group = self.group_at(int(key))
        return group[0 if kind == "cohort" else 1]

    def verify_alias_patch(self, patch):
        index = self.spec.alias_spec.index
        for item in (*patch.writes, *patch.removes):
            if item.index == index:
                check(type(item.key) is int and item.key in self.aliases, "sync_alias_patch")
        table = self.tx.indexes[index]
        if self.tx.before is None:
            check(len(table) == len(self.aliases), "sync_alias_patch")
        for alias, expected in self.aliases.items():
            leaf = table.find(alias)
            actual = ABSENT if leaf is ABSENT else leaf.atom
            check(actual is expected is ABSENT or actual is not ABSENT and expected is not ABSENT and
                  actual.encoded == expected.encoded, "sync_alias_patch")

    def expand(self, fields):
        tx = self.tx
        for cohort, ref, _old, new in self.groups.values():
            self._expand_group(thaw(cohort.value), thaw(ref.value), new)
        cohorts = {encoded: cohort for encoded, (cohort, _) in tx.groups.items()}
        for leaf in tx.tables["cohorts"].leaves():
            cohorts.setdefault(leaf.key, Atom.own(decode(leaf.key)))
        if tx.before is not None:
            cohorts.update({encoded: cohort for encoded, (cohort, _) in tx.before.groups})
        check(len(cohorts) <= 32, "sync_cohort_capacity")
        for ref_atom, _changes, _tokens, changed, _offsets in fields.values():
            if not changed:
                continue
            ref = thaw(ref_atom.value)
            for cohort_atom in cohorts.values():
                cohort = thaw(cohort_atom.value)
                marker = canonical([cohort, *ref])
                if marker not in self.groups:
                    self._expand_group(cohort, ref, self.mask(cohort, ref, "after"))
        self.complete = True

    def _expand_group(self, cohort, ref, mask):
        from .reconstruction import Operation
        tx = self.tx
        if mask:
            self._ref(ref, "after")
        tokens = tx.indexes["$fields"].get(ref)
        for i, field in enumerate(self.spec.fields):
            key = [cohort, *ref, field]
            leaf = tx.tables["memberships"].find(key)
            value = ABSENT
            if mask & (1 << i):
                check(tokens is not ABSENT and field in tokens, "sync_member_content_token")
                value = hex_digest(tokens[field])
            if value is ABSENT:
                if leaf is ABSENT:
                    continue
                operation = Operation("memberships", "remove", Atom.own(key), leaf.value_hash.hex(), None)
            else:
                if leaf is not ABSENT and leaf.atom.encoded == canonical(value):
                    continue
                operation = Operation("memberships", "put", Atom.own(key),
                                      None if leaf is ABSENT else leaf.value_hash.hex(), Atom.own(value))
            self.store._apply(tx, operation)
            if tx.before is None:
                tx.changes.pop()  # baseline has no predecessor change roster

    def close(self):
        for ref in tuple(self.packs.values()):
            ref.close()
        self.aliases.clear()
        self.groups.clear()
        self.order.clear()
        self.packs.clear()
        self.tx = None


def stage(store, header, scope, *, reservation=None):
    """Normalize into one private transaction, then use ordinary admission.

    The source before root stays physically pinned across every foreign call,
    including reentrant close. Revocation still takes effect synchronously.
    """
    from .commitment import MerkleMap, binding_digest
    from .model import NativeTag
    from .reconstruction import TABLE_LIMITS, PublicStageContext, _BaselineOperations, _Transaction
    baseline = header["kind"] == "baseline"
    tx = before = state = item = None
    failure = None
    pinned = False
    with store._lock:
        store._check()
        if store._transaction is not None:
            store.close()
            raise ProtocolError("sync_reentrant_admission")
        try:
            if baseline:
                store.retire_material()
                binding = Atom.own(header["nativeBinding"])
                tag, cursor = NativeTag.parse(header["tag"]), tuple(header["cursor"])
                check(binding.value.get("hostScope") == store.host and
                      binding_digest(thaw(binding.value), native=True).hex() == tag.binding, "sync_binding_digest")
                check(cursor == (binding.value["ownerEpoch"], tag.generation, tag.root), "sync_cursor")
                tables, groups = {name: MerkleMap(name) for name in SPACES}, {}
            else:
                before = store.candidate if store.candidate is not None else store.current
                base, tag = NativeTag.parse(header["baseTag"]), NativeTag.parse(header["resultTag"])
                check(before is not None and before.tag == base and
                      tuple(header["baseCursor"]) == before.cursor, "sync_wrong_base")
                check(tag.binding == base.binding and tag.generation == base.generation + 1, "sync_result_tag")
                binding, cursor = before.binding, tuple(header["resultCursor"])
                check(cursor == (before.cursor[0], tag.generation, tag.root), "sync_cursor")
                store.ledger.retain(before)
                pinned = True
                if store.previous is not None:
                    store.ledger.release(store.previous)
                    store.previous = None
                tables, groups = dict(before.tables), dict(before.groups)
            tx = _Transaction(store, before, binding, tag, cursor, [], tables, groups)
            store._transaction = tx
            state = tx.compact = CompactState(store, tx, scope.binding)
            ctx = NormalizationContext(store, tx, scope.budget)
            for space in PHASES:
                state.phase = space
                count, seen = 0, set()
                with scope.space(space, ctx, baseline=baseline):
                    try:
                        for item in scope:
                            store.check_permit(tx.permit)
                            check(count < TABLE_LIMITS[space] * (1 if baseline else 2), "sync_operation_capacity")
                            count += 1
                            tx.visits._limit += 128 if not baseline else 0
                            state.adopt(item, space, seen, baseline=baseline)
                            item = None
                    finally:
                        item = None
                if space == "records":
                    state.definitions()
                    if baseline:
                        tx.operations.clear()
                seen.clear()
            state.phase = None
            check(not state.packs, "sync_canonical_value_unconsumed")
            tx.operations = _BaselineOperations(tx.tables) if baseline else tuple(tx.operations)
            tx.budget.charge(1024 + len(tx.operations) * 128)
            tx.member_operations = []
            store._links(tx)
            context = PublicStageContext(store, tx)
            patch = store.profile.admit_baseline(context) if baseline else store.profile.stage_delta(context)
            store.check_permit(tx.permit)
            return store._finish(tx, patch, reservation)
        except BaseException as error:
            failure = _retire_error(error)
        finally:
            item = ctx = context = patch = seen = tables = groups = binding = None
            if state is not None:
                state.close()
            if tx is not None:
                tx.compact = None
                tx.budget.close()
            store._transaction = None
            tx = state = None
            if pinned:
                store.ledger.release(before)
            before = None
        code, signal, public = failure
        if signal is not None:
            raise signal
        raise public if public is not None else ProtocolError(code)
