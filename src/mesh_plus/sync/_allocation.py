"""Private accounting slots on the dominant immutable graph allocations.

Only the ledger mutates these slots. They are never semantic state, included in
wire hashes, or returned by the public read facade.
"""

import sys
from contextvars import ContextVar

from ..protocol import check

ACTIVE_LEDGER = ContextVar("mesh_sync_stage_ledger", default=None)


class TrackedAllocation:
    __slots__ = ("_allocation_owner", "_allocation_refs", "_allocation_cost", "_allocation_encoded", "_allocation_pending")

    def __del__(self):
        owner = getattr(self, "_allocation_owner", None)
        if owner is not None and getattr(self, "_allocation_pending", False) and self._allocation_refs == 0:
            owner.discard_pending(self)


def prepay(amount, encoded=0):
    ledger = ACTIVE_LEDGER.get()
    return None if ledger is None else ledger.reserve(amount, encoded=encoded)


def finish(value, reservation):
    if reservation is not None:
        reservation.ledger.adopt_pending(value, reservation)
    return value


def _estimate(value, depth=0):
    check(depth <= 64, "sync_tree_depth")
    kind = type(value)
    if kind is str:
        return sys.getsizeof(value) + 64, 6 * len(value) + 2
    if kind is int:
        return sys.getsizeof(value) + 32, value.bit_length() // 3 + 4
    if kind in (bool, type(None)):
        return 0, 5
    check(kind in (dict, list), "sync_json_type")
    private, encoded = (80 + 64 * len(value), 2) if kind is dict else (40 + 8 * len(value), 2)
    for key, child in value.items() if kind is dict else ((None, child) for child in value):
        if kind is dict:
            check(type(key) is str, "sync_object_key")
            cost, size = _estimate(key, depth + 1)
            private += cost
            encoded += size + 1
        cost, size = _estimate(child, depth + 1)
        private += cost
        encoded += size + 1
    return private, encoded


def prepay_json(value):
    if ACTIVE_LEDGER.get() is None:
        return None
    private, encoded = _estimate(value)
    # Freeze/thaw containers plus the encoder's temporary Unicode string and
    # final bytes are prepaid. Actual retained bytes replace this allowance.
    return prepay(1024 + private * 3 + encoded * 5, encoded * 2)
