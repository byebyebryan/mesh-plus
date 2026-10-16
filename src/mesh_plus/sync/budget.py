"""Incremental unique-allocation accounting for retained immutable sync graphs."""

import sys
from dataclasses import dataclass

from ..protocol import check
from ._allocation import TrackedAllocation
from .canonical import Atom, FrozenObject, PackedAtom
from .commitment import Branch, Leaf, MerkleMap, Work


class OwnedUnit:
    """Internal immutable allocation-unit protocol; never accepted from JSON."""

    __slots__ = ()

    def owned_children(self):
        return ()

    def owned_intrinsic(self):
        return 0


def children(value):
    kind = type(value)
    if isinstance(value, OwnedUnit):
        return value.owned_children()
    if kind is Branch:
        return (value.left, value.right)
    if kind is Leaf:
        return (value.atom,)
    if kind in (Atom, PackedAtom):
        return ()
    if kind is FrozenObject:
        return (value._items,)
    if kind is tuple:
        return value
    if kind is MerkleMap:
        return (value.node, value.work)
    check(kind in (str, bytes, int, bool, type(None), Work), "sync_owned_graph_type")
    return ()


def _payload_size(value):
    """A newly owned atom's private tree; never walks an unchanged cache root."""
    seen = set()

    def visit(item):
        if id(item) in seen:
            return 0
        seen.add(id(item))
        if type(item) in (bool, type(None)) or (type(item) is int and -5 <= item <= 256):
            return 0  # interpreter-owned immortal scalar, no cache allocation
        size = sys.getsizeof(item)
        if type(item) is FrozenObject:
            size += visit(item._items)
        elif type(item) is tuple:
            size += sum(visit(child) for child in item)
        return size

    return visit(value)


def allocation_size(value):
    """Group private intrinsic buffers with their owning node, not per-buffer
    ledger entries. Persistent child nodes and shareable atoms remain separate
    allocation units; shared roots/atoms are consequently charged only once.
    """
    size, encoded = sys.getsizeof(value), 0
    kind = type(value)
    if kind is Branch:
        size += sys.getsizeof(value.prefix) + sys.getsizeof(value.root)
        size += sys.getsizeof(value.count) if value.count > 256 else 0
        encoded = len(value.prefix) + len(value.root)
        # example borrows a child's key digest; children keep it alive.
    elif kind is Leaf:
        buffers = (value.key, value.example, value.value_hash, value.root)
        size += sum(sys.getsizeof(buffer) for buffer in buffers)
        encoded = sum(len(buffer) for buffer in buffers)
    elif kind in (Atom, PackedAtom):
        size += sys.getsizeof(value.encoded)
        if kind is Atom:
            size += _payload_size(value.value)
        size += sys.getsizeof(value.copy_budget) if value.copy_budget > 256 else 0
        encoded = len(value.encoded)
    elif kind is MerkleMap:
        size += sum(sys.getsizeof(buffer) for buffer in (value._framed_space, value._empty))
        encoded = len(value._framed_space) + len(value._empty)
    elif kind is Work:
        size += 512  # bounded counter integers, including future increments
    elif kind is bytes:
        encoded = len(value)
    if isinstance(value, OwnedUnit):
        size += value.owned_intrinsic()
    return size, encoded


@dataclass(slots=True)
class _Tracked:
    value: object
    refs: int
    cost: int
    encoded: int


class AllocationLedger:
    """Only new paths are visited; shared held children terminate traversal.

    Dominant immutable nodes/atoms carry private accounting slots, avoiding a
    second dictionary/object graph per node. Other bounded composite allocations
    use a small side table. Node-intrinsic buffers are grouped with their owner.
    Owned atoms have private payloads; aliases share the atom, not its tree.
    Private byte buffers count toward the independent encoded retention cap too.
    This is a hard owned-cache budget, not a substitute for aggregate RSS gates.
    """

    def __init__(self, maximum=64 * 1024 * 1024, *, encoded_maximum=32 * 1024 * 1024):
        check(type(maximum) is int and maximum > 0, "sync_decoded_budget")
        check(type(encoded_maximum) is int and encoded_maximum > 0, "sync_encoded_budget")
        self.maximum, self.encoded_maximum = maximum, encoded_maximum
        self.entries = {}
        self._roots = {}
        self.units = 0
        self.used = self.encoded = self.reserved = self.peak = 0
        self.visited = self.reclaimed = 0
        self._since_compaction = 0

    def reserve(self, amount):
        check(type(amount) is int and amount >= 0, "sync_reservation")
        check(self.used + self.reserved + amount <= self.maximum, "sync_decoded_capacity")
        self.reserved += amount
        self.peak = max(self.peak, self.used + self.reserved)
        return Reservation(self, amount)

    def _state(self, value):
        if isinstance(value, TrackedAllocation):
            owner = getattr(value, "_allocation_owner", None)
            check(owner is None or owner is self, "sync_allocation_owner")
            return None if owner is None else value
        return self.entries.get(id(value))

    def _refs(self, value, state):
        return state._allocation_refs if isinstance(value, TrackedAllocation) else state.refs

    def _set_refs(self, value, state, refs):
        if isinstance(value, TrackedAllocation):
            object.__setattr__(state, "_allocation_refs", refs)
        else:
            state.refs = refs

    def _create(self, value, cost, encoded):
        if isinstance(value, TrackedAllocation):
            for name, item in (("owner", self), ("refs", 1), ("cost", cost), ("encoded", encoded)):
                object.__setattr__(value, "_allocation_" + name, item)
        else:
            self.entries[id(value)] = _Tracked(value, 1, cost, encoded)
        self.units += 1
        self.used += cost
        self.encoded += encoded

    def _forget(self, value, state):
        if isinstance(value, TrackedAllocation):
            cost, encoded = state._allocation_cost, state._allocation_encoded
            object.__setattr__(state, "_allocation_owner", None)
            for name in ("refs", "cost", "encoded"):
                object.__setattr__(state, "_allocation_" + name, 0)
        else:
            cost, encoded = state.cost, state.encoded
            del self.entries[id(value)]
            self._since_compaction += 1
        self.units -= 1
        self.used -= cost
        self.encoded -= encoded

    def retain(self, root, *, reservation=None):
        # A small rollback log replaces a second per-node planning graph. Every
        # increment is undone on failure, including aliases to existing roots.
        touched, active = [], set()
        # The log is a flat list of borrowed object pointers, not one Python
        # bookkeeping object per node. A fixed DFS allowance covers the bounded
        # Patricia depth; the list's capacity is bounded before each append.
        scratch_base = min(65536, self.maximum // 32)
        scratch = scratch_base
        credit = 0 if reservation is None else reservation.amount
        if reservation is not None:
            check(reservation.ledger is self and not reservation.closed, "sync_reservation")
        root_cost = 224 if id(root) not in self._roots else 0
        check(self.used + self.reserved - credit + root_cost + scratch_base <= self.maximum,
              "sync_decoded_capacity")
        self.reserved += root_cost + scratch_base

        def visit(value):
            nonlocal scratch
            check(id(value) not in active, "sync_owned_graph_cycle")
            state = self._state(value)
            intrinsic, encoded = (0, 0) if state is not None else allocation_size(value)
            # Slots include their four pointer slots. 96 further bytes cover
            # their mutable size/ref integers. Root registrations are separate.
            cost = 0 if state is not None else intrinsic + (96 if isinstance(value, TrackedAllocation) else 256)
            check(self.used + self.reserved - credit + cost + 16 <= self.maximum, "sync_decoded_capacity")
            check(self.encoded + encoded <= self.encoded_maximum, "sync_encoded_capacity")
            self.reserved += 16  # flat rollback log capacity, before append
            scratch += 16
            touched.append(value)
            if state is not None:
                self._set_refs(value, state, self._refs(value, state) + 1)
            else:
                self._create(value, cost, encoded)
                self.visited += 1
                active.add(id(value))
                for child in children(value):
                    visit(child)
                active.remove(id(value))
            self.peak = max(self.peak, self.used + self.reserved - credit)

        try:
            visit(root)
            key = id(root)
            previous = self._roots.get(key)
            self._roots[key] = (root, 1 if previous is None else previous[1] + 1)
            self.used += root_cost
            if reservation is not None:
                reservation.close()
            return root
        except BaseException:
            for value in reversed(touched):
                state = self._state(value)
                refs = self._refs(value, state) - 1
                if refs:
                    self._set_refs(value, state, refs)
                else:
                    self._forget(value, state)
            raise
        finally:
            self.reserved -= scratch + root_cost

    def release(self, root):
        registration = self._roots.get(id(root))
        check(registration is not None, "sync_owned_release")
        if registration[1] == 1:
            del self._roots[id(root)]
            self.used -= 224
            if not self._roots:
                self._roots = {}
        else:
            self._roots[id(root)] = (root, registration[1] - 1)
        pending = [root]
        while pending:
            value = pending.pop()
            state = self._state(value)
            check(state is not None and self._refs(value, state) > 0, "sync_owned_release")
            refs = self._refs(value, state) - 1
            self._set_refs(value, state, refs)
            if refs == 0:
                self._forget(value, state)
                self.reclaimed += 1
                pending.extend(children(value))
        if not self.entries:
            self.entries = {}  # retire the peak-sized dictionary capacity too
            self._since_compaction = 0
        elif self._since_compaction > len(self.entries) // 2:
            # Rebuild only after proportional reclamation, never per sparse
            # transaction. Work is charged to the entries actually retired.
            self.entries = dict(self.entries.items())
            self._since_compaction = 0

    def inspect(self):
        return {"decodedBytes": self.used, "encodedBytes": self.encoded, "reservedBytes": self.reserved,
                "peakBytes": self.peak, "uniqueAllocations": self.units,
                "newAllocationVisits": self.visited, "reclaimedAllocations": self.reclaimed}


class Reservation:
    def __init__(self, ledger, amount):
        self.ledger, self.amount, self.closed = ledger, amount, False

    def close(self):
        if not self.closed:
            self.closed = True
            self.ledger.reserved -= self.amount

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
