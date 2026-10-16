"""Private accounting slots on the dominant immutable graph allocations.

Only the ledger mutates these slots. They are never semantic state, included in
wire hashes, or returned by the public read facade.
"""


class TrackedAllocation:
    __slots__ = ("_allocation_owner", "_allocation_refs", "_allocation_cost", "_allocation_encoded")
