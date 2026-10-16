"""Incremental unique-allocation accounting for retained immutable sync graphs."""

import sys
from dataclasses import dataclass

from ..protocol import check
from .canonical import Atom, FrozenObject
from .commitment import Branch, Leaf, MerkleMap, Work


def children(value):
    kind = type(value)
    if kind is Branch:
        return (value.left, value.right)
    if kind is Leaf:
        return (value.atom,)
    if kind is Atom:
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
    elif kind is Atom:
        size += sys.getsizeof(value.encoded) + _payload_size(value.value)
        encoded = len(value.encoded)
    elif kind is MerkleMap:
        size += sum(sys.getsizeof(buffer) for buffer in (value._framed_space, value._empty))
        encoded = len(value._framed_space) + len(value._empty)
    elif kind is Work:
        size += 512  # bounded counter integers, including future increments
    elif kind is bytes:
        encoded = len(value)
    return size, encoded


@dataclass(slots=True)
class _Tracked:
    value: object
    refs: int
    cost: int
    encoded: int


class AllocationLedger:
    """Only new paths are visited; shared held children terminate traversal.

    Charges actual private object/container sizes plus a conservative per-unit allowance
    for the ledger's dictionary, reference integer and bookkeeping allocations.
    Grouping node-intrinsic bytes avoids a ledger object per hash/string. Owned
    atoms have private payloads; aliases share the atom, not its borrowed tree.
    Private byte buffers count toward the independent encoded retention cap too.
    This is a hard owned-cache budget, not a substitute for aggregate RSS gates.
    """

    def __init__(self, maximum=64 * 1024 * 1024, *, encoded_maximum=32 * 1024 * 1024):
        check(type(maximum) is int and maximum > 0, "sync_decoded_budget")
        check(type(encoded_maximum) is int and encoded_maximum > 0, "sync_encoded_budget")
        self.maximum, self.encoded_maximum = maximum, encoded_maximum
        self.entries = {}
        self.used = self.encoded = self.reserved = self.peak = 0
        self.visited = self.reclaimed = 0

    def reserve(self, amount):
        check(type(amount) is int and amount >= 0, "sync_reservation")
        check(self.used + self.reserved + amount <= self.maximum, "sync_decoded_capacity")
        self.reserved += amount
        self.peak = max(self.peak, self.used + self.reserved)
        return Reservation(self, amount)

    def retain(self, root, *, reservation=None):
        plan = {}
        visiting = set()

        def visit(value):
            key = id(value)
            if key in self.entries or key in plan:
                return
            check(key not in visiting, "sync_owned_graph_cycle")
            visiting.add(key)
            edges = children(value)
            # Edges are read directly from immutable units, not duplicated into
            # a second retained graph of Python id integers/tuples.
            intrinsic, encoded = allocation_size(value)
            cost = intrinsic + 256
            self.visited += 1
            for child in edges:
                visit(child)
            visiting.remove(key)
            plan[key] = _Tracked(value, 0, cost, encoded)

        visit(root)
        credit = 0
        if reservation is not None:
            check(reservation.ledger is self and not reservation.closed, "sync_reservation")
            credit = reservation.amount
        added = sum(entry.cost for entry in plan.values())
        encoded = sum(entry.encoded for entry in plan.values())
        check(self.used + self.reserved - credit + added <= self.maximum, "sync_decoded_capacity")
        check(self.encoded + encoded <= self.encoded_maximum, "sync_encoded_capacity")
        # Validation/planning above has no retained-ledger mutation on failure.
        for key, entry in plan.items():
            self.entries[key] = entry
        for entry in plan.values():
            for child in children(entry.value):
                self.entries[id(child)].refs += 1
        self.entries[id(root)].refs += 1
        self.used += added
        self.encoded += encoded
        if reservation is not None:
            reservation.close()
        self.peak = max(self.peak, self.used + self.reserved)
        return root

    def release(self, root):
        pending = [id(root)]
        while pending:
            key = pending.pop()
            entry = self.entries.get(key)
            check(entry is not None and entry.refs > 0, "sync_owned_release")
            entry.refs -= 1
            if entry.refs == 0:
                del self.entries[key]
                self.used -= entry.cost
                self.encoded -= entry.encoded
                self.reclaimed += 1
                pending.extend(id(child) for child in children(entry.value))

    def inspect(self):
        return {"decodedBytes": self.used, "encodedBytes": self.encoded, "reservedBytes": self.reserved,
                "peakBytes": self.peak, "uniqueAllocations": len(self.entries),
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
