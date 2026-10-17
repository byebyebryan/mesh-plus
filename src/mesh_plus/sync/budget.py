"""Incremental unique-allocation accounting for retained immutable sync graphs."""

import sys
from contextlib import contextmanager
from dataclasses import dataclass

from ..protocol import check
from ._allocation import ACTIVE_LEDGER, TrackedAllocation
from .canonical import Atom, FrozenObject, InputKey, PackedAtom
from .commitment import Branch, Leaf, MerkleMap, Work


class OwnedUnit:
    """Internal immutable allocation-unit protocol; never accepted from JSON."""

    __slots__ = ()

    def owned_children(self):
        return ()

    def owned_intrinsic(self):
        return 0

    def owned_encoded(self):
        return 0


def children(value):
    kind = type(value)
    if isinstance(value, OwnedUnit):
        return value.owned_children()
    if kind is Branch:
        return (value.left, value.right)
    if kind is Leaf:
        return (value.atom,)
    if kind in (Atom, PackedAtom, InputKey):
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
        elif type(item) in (tuple, list):
            size += sum(visit(child) for child in item)
        elif type(item) is dict:
            size += sum(visit(key) + visit(child) for key, child in item.items())
        return size

    try:
        return visit(value)
    finally:
        visit = None
        seen.clear()


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
    elif kind is InputKey:
        size += sys.getsizeof(value.copy_budget) if value.copy_budget > 256 else 0
        # Canonical buffer is already charged to the baseline leaf. InputKey
        # is stage-only and never owns a separate encoded-byte reservation.
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
        encoded += value.owned_encoded()
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
        self.pending_encoded = self.encoded_reserved = self.pending_units = 0
        self.visited = self.reclaimed = 0
        self._since_compaction = 0

    def reserve(self, amount, *, encoded=0):
        check(type(amount) is int and amount >= 0, "sync_reservation")
        check(type(encoded) is int and encoded >= 0, "sync_reservation")
        check(self.used + self.reserved + amount <= self.maximum, "sync_decoded_capacity")
        check(self.encoded + self.pending_encoded + self.encoded_reserved + encoded <= self.encoded_maximum,
              "sync_encoded_capacity")
        self.reserved += amount
        self.encoded_reserved += encoded
        self.peak = max(self.peak, self.used + self.reserved)
        return Reservation(self, amount, encoded)

    @contextmanager
    def allocations(self):
        current = ACTIVE_LEDGER.get()
        check(current is None or current is self, "sync_allocation_owner")
        working = None if current is self else self.reserve(min(65536, self.maximum // 32))
        token = ACTIVE_LEDGER.set(self)
        try:
            yield
        finally:
            ACTIVE_LEDGER.reset(token)
            if working is not None:
                working.close()

    def adopt_pending(self, value, reservation):
        check(isinstance(value, TrackedAllocation) and self._state(value) is None and
              reservation.ledger is self and not reservation.closed, "sync_allocation_state")
        intrinsic, encoded = allocation_size(value)
        cost = intrinsic + 96
        check(cost <= reservation.amount and encoded <= reservation.encoded_amount, "sync_allocation_estimate")
        reservation.close()
        self.reserved += cost
        self.pending_encoded += encoded
        self.pending_units += 1
        self.visited += 1
        for name, item in (("owner", self), ("refs", 0), ("cost", cost), ("encoded", encoded), ("pending", True)):
            object.__setattr__(value, "_allocation_" + name, item)

    def discard_pending(self, value):
        self.reserved -= value._allocation_cost
        self.pending_encoded -= value._allocation_encoded
        self.pending_units -= 1
        self.reclaimed += 1
        object.__setattr__(value, "_allocation_owner", None)
        object.__setattr__(value, "_allocation_pending", False)

    def _retain_atom_edge(self, value):
        """Private paged-node edge; atoms have no separately tracked children."""
        check(type(value) in (Atom, PackedAtom), "sync_atom")
        state = self._state(value)
        if state is None:
            intrinsic, encoded = allocation_size(value)
            cost = intrinsic + 96
            check(self.used + self.reserved + cost <= self.maximum, "sync_decoded_capacity")
            check(self.encoded + self.pending_encoded + self.encoded_reserved + encoded <= self.encoded_maximum,
                  "sync_encoded_capacity")
            self._create(value, cost, encoded)
            self.visited += 1
        else:
            self._set_refs(value, state, self._refs(value, state) + 1)
            if value._allocation_pending:
                self._convert_pending(value, commit=True)
        self.peak = max(self.peak, self.used + self.reserved)

    def _release_atom_edge(self, value):
        state = self._state(value)
        check(state is not None and self._refs(value, state) > 0, "sync_owned_release")
        refs = self._refs(value, state) - 1
        self._set_refs(value, state, refs)
        if refs == 0:
            self._forget(value, state)
            self.reclaimed += 1

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
            object.__setattr__(value, "_allocation_pending", False)
        else:
            self.entries[id(value)] = _Tracked(value, 1, cost, encoded)
        self.units += 1
        self.used += cost
        self.encoded += encoded

    def _forget(self, value, state):
        if isinstance(value, TrackedAllocation):
            cost, encoded = state._allocation_cost, state._allocation_encoded
            object.__setattr__(state, "_allocation_owner", None)
            object.__setattr__(state, "_allocation_pending", False)
            for name in ("refs", "cost", "encoded"):
                object.__setattr__(state, "_allocation_" + name, 0)
        else:
            cost, encoded = state.cost, state.encoded
            del self.entries[id(value)]
            self._since_compaction += 1
        self.units -= 1
        self.used -= cost
        self.encoded -= encoded

    def _convert_pending(self, value, *, commit):
        sign = 1 if commit else -1
        self.used += sign * value._allocation_cost
        self.reserved -= sign * value._allocation_cost
        self.encoded += sign * value._allocation_encoded
        self.pending_encoded -= sign * value._allocation_encoded
        self.units += sign
        self.pending_units -= sign
        object.__setattr__(value, "_allocation_pending", not commit)

    def retain(self, root, *, reservation=None, finalize=True):
        # A small rollback log replaces a second per-node planning graph. Every
        # increment is undone on failure, including aliases to existing roots.
        touched, actions, active = [], bytearray(), set()
        # The log is a flat list of borrowed object pointers, not one Python
        # bookkeeping object per node. A fixed DFS allowance covers the bounded
        # Patricia depth; the list's capacity is bounded before each append.
        scratch_base = min(65536, self.maximum // 32)
        scratch = scratch_base
        credit = 0 if reservation is None else reservation.amount
        encoded_credit = 0 if reservation is None else reservation.encoded_amount
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
            is_pending = state is not None and isinstance(value, TrackedAllocation) and value._allocation_pending
            intrinsic, encoded = (0, 0) if state is not None else allocation_size(value)
            # Slots include their four pointer slots. 96 further bytes cover
            # their mutable size/ref integers. Root registrations are separate.
            cost = 0 if state is not None else intrinsic + (96 if isinstance(value, TrackedAllocation) else 256)
            check(self.used + self.reserved - credit + cost + 16 <= self.maximum, "sync_decoded_capacity")
            check(self.encoded + self.pending_encoded + self.encoded_reserved - encoded_credit + encoded <= self.encoded_maximum,
                  "sync_encoded_capacity")
            self.reserved += 16  # flat rollback log capacity, before append
            scratch += 16
            touched.append(value)
            actions.append(3 if is_pending and finalize else 4 if is_pending else 1 if state is not None else 2)
            if state is not None:
                self._set_refs(value, state, self._refs(value, state) + 1)
                if is_pending and finalize:
                    self._convert_pending(value, commit=True)
                elif is_pending:
                    check(not children(value), "sync_provisional_graph")
            else:
                self._create(value, cost, encoded)
                self.visited += 1
            if state is None or is_pending and finalize:
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
            for value, action in zip(reversed(touched), reversed(actions)):
                state = self._state(value)
                refs = self._refs(value, state) - 1
                if action == 3:
                    self._set_refs(value, state, refs)
                    self._convert_pending(value, commit=False)
                elif action in (1, 4):
                    self._set_refs(value, state, refs)
                else:
                    self._forget(value, state)
            raise
        finally:
            self.reserved -= scratch + root_cost
            visit = None
            touched.clear()
            actions.clear()
            active.clear()

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
                if isinstance(value, TrackedAllocation) and value._allocation_pending:
                    # A provisional decoder borrow ended; a pending parent may
                    # still hold this atom. Its destructor releases the charge
                    # once the actual uncommitted allocation is unreachable.
                    continue
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
                "pendingAllocations": self.pending_units, "pendingEncodedBytes": self.pending_encoded,
                "reservedEncodedBytes": self.encoded_reserved,
                "newAllocationVisits": self.visited, "reclaimedAllocations": self.reclaimed}


class Reservation:
    def __init__(self, ledger, amount, encoded=0):
        self.ledger, self.amount, self.encoded_amount, self.closed = ledger, amount, encoded, False

    def close(self):
        if not self.closed:
            self.closed = True
            self.ledger.reserved -= self.amount
            self.ledger.encoded_reserved -= self.encoded_amount

    def grow(self, amount, *, encoded=0):
        """Prepay additional scratch capacity before growing its container."""
        check(not self.closed, "sync_reservation")
        extra = self.ledger.reserve(amount, encoded=encoded)
        self.amount += extra.amount
        self.encoded_amount += extra.encoded_amount
        extra.closed = True  # its charge now belongs to this reservation

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
