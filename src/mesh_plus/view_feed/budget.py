"""Small explicit ownership ledger for the complete-view feed.

The ledger accounts allocations owned by a feed engine or its borrowed output
handles. It does not claim to cap caller-owned input, validator internals, or
process RSS; those boundaries are owned by Delivery and the outer runtime.
"""

from dataclasses import dataclass
from threading import Lock

from ..protocol import MAX_MESSAGE, check

MAX_ENCODED_BYTES = 32 * 1024 * 1024
MAX_HEAP_BYTES = 64 * 1024 * 1024
MAX_RECORDS = 4096


@dataclass(frozen=True, slots=True)
class FeedLimits:
    """Narrow-only limits for one negotiated feed incarnation."""

    encoded_bytes: int = MAX_ENCODED_BYTES
    heap_bytes: int = MAX_HEAP_BYTES
    max_records: int = MAX_RECORDS
    max_packet_bytes: int = MAX_MESSAGE

    def __post_init__(self):
        check(type(self.encoded_bytes) is int and 0 < self.encoded_bytes <= MAX_ENCODED_BYTES,
              "view_feed_encoded_limit")
        check(type(self.heap_bytes) is int and 0 < self.heap_bytes <= MAX_HEAP_BYTES,
              "view_feed_heap_limit")
        check(type(self.max_records) is int and 0 < self.max_records <= MAX_RECORDS,
              "view_feed_record_limit")
        check(type(self.max_packet_bytes) is int and 0 < self.max_packet_bytes <= MAX_MESSAGE,
              "view_feed_packet_limit")


class FeedBudget:
    """Shared thread-safe scalar ledger for one connection/client lifetime."""

    def __init__(self, limits=None):
        limits = FeedLimits() if limits is None else limits
        check(type(limits) is FeedLimits, "view_feed_limits")
        self.limits = limits
        self._lock = Lock()
        self._heap = 0
        self._encoded = 0
        self._peak_heap = 0
        self._peak_encoded = 0

    def reserve(self, *, encoded=0, heap=0):
        """Reserve caller-owned intake/parser storage against the shared cap."""
        # Do not keep a scope on the ledger: each scope points back to its
        # budget, so a persistent scope would form a cycle under GC-disabled
        # ownership checks. A lease keeps this temporary scope alive as needed.
        return _BudgetScope(self, self.limits).reserve(heap, encoded_bytes=encoded)

    def scope(self, limits=None):
        limits = self.limits if limits is None else limits
        check(type(limits) is FeedLimits and
              limits.heap_bytes <= self.limits.heap_bytes and
              limits.encoded_bytes <= self.limits.encoded_bytes and
              limits.max_records <= self.limits.max_records and
              limits.max_packet_bytes <= self.limits.max_packet_bytes,
              "view_feed_limit_enlargement")
        return _BudgetScope(self, limits)

    def narrow(self, limits):
        """Permanently narrow shared limits without discarding live leases."""
        check(type(limits) is FeedLimits and
              limits.heap_bytes <= self.limits.heap_bytes and
              limits.encoded_bytes <= self.limits.encoded_bytes and
              limits.max_records <= self.limits.max_records and
              limits.max_packet_bytes <= self.limits.max_packet_bytes,
              "view_feed_limit_enlargement")
        with self._lock:
            check(self._heap <= limits.heap_bytes and self._encoded <= limits.encoded_bytes,
                  "view_feed_capacity")
            self.limits = limits

    def _reserve(self, scope, heap_bytes, encoded_bytes):
        check(type(heap_bytes) is int and heap_bytes >= 0 and
              type(encoded_bytes) is int and encoded_bytes >= 0, "view_feed_reservation")
        with self._lock:
            check(self._heap + heap_bytes <= self.limits.heap_bytes and
                  self._encoded + encoded_bytes <= self.limits.encoded_bytes and
                  scope._heap + heap_bytes <= scope.limits.heap_bytes and
                  scope._encoded + encoded_bytes <= scope.limits.encoded_bytes,
                  "view_feed_capacity")
            self._heap += heap_bytes
            self._encoded += encoded_bytes
            scope._heap += heap_bytes
            scope._encoded += encoded_bytes
            self._peak_heap = max(self._peak_heap, self._heap)
            self._peak_encoded = max(self._peak_encoded, self._encoded)
        return _BudgetCredit(scope, heap_bytes, encoded_bytes)

    def _resize(self, credit, heap_bytes, encoded_bytes):
        check(type(heap_bytes) is int and heap_bytes >= 0 and
              type(encoded_bytes) is int and encoded_bytes >= 0, "view_feed_reservation")
        with self._lock:
            check(not credit._released, "view_feed_reservation_closed")
            scope = credit._scope
            heap_delta = heap_bytes - credit.heap_bytes
            encoded_delta = encoded_bytes - credit.encoded_bytes
            check(self._heap + heap_delta <= self.limits.heap_bytes and
                  self._encoded + encoded_delta <= self.limits.encoded_bytes and
                  scope._heap + heap_delta <= scope.limits.heap_bytes and
                  scope._encoded + encoded_delta <= scope.limits.encoded_bytes,
                  "view_feed_capacity")
            self._heap += heap_delta
            self._encoded += encoded_delta
            scope._heap += heap_delta
            scope._encoded += encoded_delta
            credit.heap_bytes, credit.encoded_bytes = heap_bytes, encoded_bytes
            self._peak_heap = max(self._peak_heap, self._heap)
            self._peak_encoded = max(self._peak_encoded, self._encoded)

    def _release(self, credit):
        with self._lock:
            if credit._released:
                return
            scope = credit._scope
            self._heap -= credit.heap_bytes
            self._encoded -= credit.encoded_bytes
            scope._heap -= credit.heap_bytes
            scope._encoded -= credit.encoded_bytes
            credit._released = True

    def inspect(self):
        with self._lock:
            return {"heapBytes": self._heap, "encodedBytes": self._encoded,
                    "heapLimitBytes": self.limits.heap_bytes,
                    "encodedLimitBytes": self.limits.encoded_bytes,
                    "peakHeapBytes": self._peak_heap,
                    "peakEncodedBytes": self._peak_encoded}


class _BudgetScope:
    """Per-engine narrow view over a potentially shared FeedBudget."""

    __slots__ = ("_budget", "limits", "_heap", "_encoded")

    def __init__(self, budget, limits):
        self._budget, self.limits = budget, limits
        self._heap = self._encoded = 0

    def reserve(self, heap_bytes, *, encoded_bytes=0):
        return self._budget._reserve(self, heap_bytes, encoded_bytes)

    def inspect(self):
        with self._budget._lock:
            return {"heapBytes": self._heap, "encodedBytes": self._encoded,
                    "heapLimitBytes": self.limits.heap_bytes,
                    "encodedLimitBytes": self.limits.encoded_bytes}


class _BudgetCredit:
    """A single physical owner for one conservative allocation estimate."""

    __slots__ = ("_scope", "heap_bytes", "encoded_bytes", "_released")

    def __init__(self, scope, heap_bytes, encoded_bytes):
        self._scope = scope
        self.heap_bytes = heap_bytes
        self.encoded_bytes = encoded_bytes
        self._released = False

    def resize(self, heap_bytes, encoded_bytes):
        self._scope._budget._resize(self, heap_bytes, encoded_bytes)

    def release(self):
        self._scope._budget._release(self)

    close = release

    def __del__(self):
        self.release()

