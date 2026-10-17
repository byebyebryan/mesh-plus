"""Private index/rule scratch with an explicit phase ownership boundary.

The returned DomainIndexPatch and its DTOs remain caller-prepaid through the
transaction. This owner pays only new duplicate markers and bulk-entry storage;
key/value Atoms and constructed index nodes retain their intrinsic charges.
"""

from ..protocol import ProtocolError, check
from ._boundary import _retire_error
from .canonical import Atom, PackedAtom, packed, thaw
from .commitment import ABSENT, MerkleMap
from .model import IndexRemove, IndexWrite, RuleWrite
from .ordered import OrderedMap


class _IndexRows:
    """One baseline bucket owns its keys through construction and unwind."""

    __slots__ = ("credit", "rows", "__weakref__")

    def __init__(self, ledger):
        self.credit = ledger.reserve(256)
        self.rows = None
        try:
            self.rows = []
        except BaseException:
            self.close()
            raise

    def append(self, key, value):
        check(type(key) in (Atom, PackedAtom) and type(value) in (Atom, PackedAtom) and
              getattr(key, "_allocation_owner", None) is self.credit.ledger and
              getattr(value, "_allocation_owner", None) is self.credit.ledger, "sync_index_row_owner")
        self.credit.grow(128)  # tuple, pointer list and resize overlap
        self.rows.append((key, value))
        return len(self.rows)

    def __len__(self):
        return len(self.rows)

    def close(self):
        self.rows = None
        if self.credit is not None:
            self.credit.close()
            self.credit = None


class _IndexWorkspace:
    __slots__ = ("credit", "seen", "entries", "entries_credit", "__weakref__")

    def __init__(self, ledger, *, baseline=False, prepaid=False):
        # Expanded admission keeps its existing whole-patch prepayment. The
        # compact opt-in path owns these phases independently instead.
        self.credit = None if prepaid else ledger.reserve(4096)
        self.seen = self.entries = self.entries_credit = None
        try:
            self.seen = {}
            self.entries = {} if baseline else None
            # At most 32 descriptor indexes. Registry resize overlap and bucket
            # control objects stay charged after the duplicate registry drops.
            self.entries_credit = ledger.reserve(8192) if baseline and not prepaid else None
        except BaseException:
            self.close()
            raise

    def remember(self, index, key, code, *, decoded=False):
        check((index, key.encoded) not in self.seen, code)
        if self.credit is not None:
            self.credit.grow(256)  # marker tuple, hash table and resize overlap
        owned = key if decoded else packed(key)
        self.seen[index, owned.encoded] = owned
        return owned

    def append(self, index, key, value):
        if self.entries_credit is not None:
            check(self.seen is not None, "sync_index_workspace_retired")
            if index not in self.entries:
                bucket = _IndexRows(self.entries_credit.ledger)
                try:
                    self.entries[index] = bucket
                except BaseException:
                    bucket.close()
                    raise
            return self.entries[index].append(key, value)
        if index not in self.entries:
            if self.credit is not None:
                self.credit.grow(256)  # index bucket and empty list
            self.entries[index] = []
        if self.credit is not None:
            self.credit.grow(128)  # row tuple and list growth/resize overlap
        self.entries[index].append((key, value))
        return len(self.entries[index])

    def finish_seen(self):
        self.seen = None
        if self.credit is not None:
            self.credit.close()
            self.credit = None

    def take(self):
        # Preserve insertion/build order, with no roster-sized key snapshot.
        name = next(iter(self.entries))
        return name, self.entries.pop(name)

    def close(self):
        if getattr(self, "entries_credit", None) is not None:
            for bucket in self.entries.values():
                bucket.close()
        self.entries = None
        if getattr(self, "entries_credit", None) is not None:
            self.entries_credit.close()
            self.entries_credit = None
        self.finish_seen()


def _raise_failure(failure):
    code, signal, public = failure
    if signal is not None:
        raise signal
    raise public if public is not None else ProtocolError(code)


def apply_indexes(store, tx, patch):
    if not patch.writes and not patch.removes:
        return
    work = key = value = owned_key = entries = spec = remove = write = bucket = None
    failure = None
    try:
        work = _IndexWorkspace(store.ledger, baseline=tx.before is None, prepaid=tx.compact is None)
        # Removes still precede inserts, with one duplicate registry across
        # both. A key replacement needs only its final declared entry capacity.
        for remove in patch.removes:
            check(type(remove) is IndexRemove and remove.index in store.index_specs, "sync_index_remove")
            key = Atom.own(remove.key)
            work.remember(remove.index, key, "sync_duplicate_index_operation")
            tx.indexes[remove.index] = tx.indexes[remove.index].remove(thaw(key.value))
        for write in patch.writes:
            check(type(write) is IndexWrite and write.index in store.index_specs, "sync_index_write")
            key, value = Atom.own(write.key), Atom.own(write.value)
            spec = store.index_specs[write.index]
            owned_key = work.remember(write.index, key, "sync_duplicate_index_operation", decoded=spec.ordered)
            check(len(value.encoded) <= spec.max_value_bytes, "sync_index_value_capacity")
            store.validators[write.index][0].validate(key, store.ledger)
            store.validators[write.index][1].validate(value, store.ledger)
            if work.entries is None:
                tx.indexes[write.index] = tx.indexes[write.index].put_atom(thaw(key.value), packed(value))
                size = len(tx.indexes[write.index])
            else:
                size = work.append(write.index, owned_key if spec.ordered or work.entries_credit is not None else
                                   owned_key.encoded, packed(value))
            check(size <= spec.max_entries, "sync_index_entry_capacity")
        if work.entries_credit is not None:
            # All duplicates and schemas have been checked. Rows own the
            # canonical key buffers before their duplicate markers retire.
            work.finish_seen()
            while work.entries:
                name, bucket = work.take()
                entries = bucket.rows
                tx.indexes[name] = (OrderedMap.baseline_atoms(entries) if store.index_specs[name].ordered else
                                    MerkleMap._from_encoded_atoms("index/" + name,
                                        ((key.encoded, value) for key, value in entries)))
                entries = None
                bucket.close()
                bucket = None
        elif work.entries is not None:
            for name, entries in work.entries.items():
                tx.indexes[name] = (OrderedMap.baseline_atoms(entries) if store.index_specs[name].ordered else
                                    MerkleMap._from_encoded_atoms("index/" + name, entries))
    except BaseException as error:
        failure = _retire_error(error)
    finally:
        key = value = owned_key = entries = spec = remove = write = None
        if bucket is not None:
            bucket.close()
            bucket = None
        if work is not None:
            work.close()
        work = None
    if failure is not None:
        store = tx = patch = None
        _raise_failure(failure)


def apply_rules(store, tx, patch):
    if not patch.changed_rules and not patch.removed_rules:
        return
    from .reconstruction import _record_ref

    work = key = value = owned = ref = slot = item = None
    failure = None
    try:
        # "$rules" is reserved: declared index names cannot share this key
        # space. Both rule operations still share one duplicate registry.
        work = _IndexWorkspace(store.ledger, prepaid=tx.compact is None)
        for item in patch.changed_rules:
            check(type(item) is RuleWrite, "sync_rule_write")
            key, value = Atom.own(item.key), Atom.own(item.value)
            work.remember("$rules", key, "sync_duplicate_rule")
            ref = thaw(key.value)
            _record_ref(ref, tx)
            slot = tx.tables["records"].get(ref[0])
            check(slot is not ABSENT and thaw(slot["birth"]) == ref[1], "sync_rule_record_birth")
            check(len(value.encoded) <= 16384, "sync_rule_capacity")
            tx.indexes["$rules"] = tx.indexes["$rules"].put_atom(ref, packed(value))
        for key in patch.removed_rules:
            owned = Atom.own(key)
            work.remember("$rules", owned, "sync_duplicate_rule")
            if tx.indexes["$rules"].get(thaw(owned.value)) is not ABSENT:
                tx.indexes["$rules"] = tx.indexes["$rules"].remove(thaw(owned.value))
    except BaseException as error:
        failure = _retire_error(error)
    finally:
        key = value = owned = ref = slot = item = None
        if work is not None:
            work.close()
        work = None
    if failure is not None:
        store = tx = patch = None
        _raise_failure(failure)
