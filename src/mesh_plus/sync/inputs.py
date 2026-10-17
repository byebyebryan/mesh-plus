"""Opt-in byte ownership; reserving or sealing never admits material.

Receive code owns unsealed reservations until its physical buffers retire.
Disconnect revokes their use but deliberately does not refund active I/O.
"""

import sys
import weakref
from contextlib import contextmanager

from ..protocol import ProtocolError, check
from ._boundary import _retire_error, admission_boundary
from .budget import Reservation
from .wire import MAX_NATIVE

_MINT = object()
_BASE_HEAP, _LEASE_HEAP, _BUFFER_HEAP = 2048, 1024, 1536
_MAX_ITEMS = 64


class InputOwner:
    """Cache-minted, epoch-bound intake credit, separate from admission."""

    def __init__(self, cache, *, _credit=None, _mint=None):
        check(_mint is _MINT, "sync_input_mint")
        self._base = _credit
        self._cache = weakref.ref(cache)
        self._ledger = cache.ledger
        self._leases, self._buffers = {}, {}
        self._closed = False

    def _check(self):
        cache = self._cache()
        check(not self._closed and cache is not None and cache._inputs is self, "sync_input_retired")
        cache._check()

    @staticmethod
    def buffer_heap(nbytes):
        """Credit transferred by seal, including bytes and handle bookkeeping."""
        check(type(nbytes) is int and 0 <= nbytes <= MAX_NATIVE, "sync_input_capacity")
        return sys.getsizeof(b"") + nbytes + _BUFFER_HEAP

    @admission_boundary
    def reserve(self, heap_bytes, *, encoded_bytes=0):
        self._check()
        check(type(heap_bytes) is int and heap_bytes >= 0 and
              type(encoded_bytes) is int and encoded_bytes >= 0, "sync_reservation")
        check(len(self._leases) + len(self._buffers) < _MAX_ITEMS, "sync_input_slots")
        credit = self._ledger.reserve(heap_bytes + _LEASE_HEAP, encoded=encoded_bytes)
        try:
            lease = InputReservation(self, credit, _mint=_MINT)
            self._leases[lease._key] = lease
            return lease
        except BaseException:
            credit.close()
            raise

    def close(self):
        cache = self._cache()
        if cache is not None:
            with cache._lock:
                self._close()
                if cache._inputs is self:
                    # Closing the current intake epoch has disconnect's
                    # publication barrier too. A stale owner's repeated close
                    # must never revoke its replacement or a sibling cache.
                    cache._inputs = None
                    cache.revoke("input_retired")
                    cache._discard_candidate()
        else:
            self._close()

    def _close(self):
        if not getattr(self, "_closed", True):
            self._closed = True
            for key in tuple(self._buffers):
                self._retire(key)
            # Active receive/parser buffers still belong to these leases.
            # Their source/session must cancel, await and finally close them.
        self._finish_base()

    def _finish_base(self):
        if self._closed and not self._leases and not self._buffers:
            self._base.close()

    def _retire(self, key):
        record = self._buffers.get(key)
        if record is not None:
            record.revoked = True
            if not record.consuming:
                del self._buffers[key]
                record.close()
        self._finish_base()

    def __del__(self):
        if hasattr(self, "_base"):
            if hasattr(self, "_closed"):
                self.close()
            self._base.close()


class InputReservation:
    """Receive/parser credit; seal leaves all non-buffer credit on this lease."""

    def __init__(self, owner, credit, *, _mint=None):
        check(_mint is _MINT, "sync_input_mint")
        self._owner, self._credit, self._key = weakref.ref(owner), credit, object()

    @property
    def heap_bytes(self):
        return max(0, self._credit.amount - _LEASE_HEAP) if not self._credit.closed else 0

    @property
    def encoded_bytes(self):
        return self._credit.encoded_amount if not self._credit.closed else 0

    def _check(self):
        owner = self._owner()
        check(not self._credit.closed and owner is not None, "sync_input_retired")
        owner._check()
        return owner

    @admission_boundary
    def resize(self, heap_bytes, *, encoded_bytes=0):
        owner = self._check()
        check(type(heap_bytes) is int and heap_bytes >= 0 and
              type(encoded_bytes) is int and encoded_bytes >= 0, "sync_reservation")
        old_heap, old_encoded = self.heap_bytes, self.encoded_bytes
        extra = owner._ledger.reserve(max(0, heap_bytes - old_heap), encoded=max(0, encoded_bytes - old_encoded))
        self._credit.amount += extra.amount
        self._credit.encoded_amount += extra.encoded_amount
        extra.closed = True
        owner._ledger.reserved -= max(0, old_heap - heap_bytes)
        owner._ledger.encoded_reserved -= max(0, old_encoded - encoded_bytes)
        self._credit.amount -= max(0, old_heap - heap_bytes)
        self._credit.encoded_amount -= max(0, old_encoded - encoded_bytes)

    @admission_boundary
    def seal(self, raw):
        owner = self._check()
        check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_input_bytes")
        check(len(owner._leases) + len(owner._buffers) < _MAX_ITEMS, "sync_input_slots")
        cost = owner.buffer_heap(len(raw))
        check(cost <= self.heap_bytes and len(raw) <= self.encoded_bytes, "sync_input_credit")
        # Both old and new controls are covered before they are allocated.
        # Only after construction succeeds does credit change ownership.
        credit = Reservation(owner._ledger, cost, len(raw))
        try:
            handle = OwnedInputRef(owner, _mint=_MINT)
            record = _Buffer(raw, credit, weakref.ref(handle))
            owner._buffers[handle._key] = record
        except BaseException:
            credit.closed = True  # original lease still owns every byte
            raise
        self._credit.amount -= cost
        self._credit.encoded_amount -= len(raw)
        return handle

    def close(self):
        if not self._credit.closed:
            self._credit.close()
            owner = self._owner()
            if owner is not None:
                owner._leases.pop(self._key, None)
                owner._finish_base()

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        if hasattr(self, "_credit"):
            self.close()


class _Buffer:
    __slots__ = ("raw", "credit", "handle", "consuming", "revoked")

    def __init__(self, raw, credit, handle):
        self.raw, self.credit, self.handle = raw, credit, handle
        self.consuming = self.revoked = False

    def close(self):
        self.raw = None
        self.credit.close()


class OwnedInputRef:
    """Opaque, single-consume byte storage. It has no semantic capability."""

    __slots__ = ("_owner", "_key", "__weakref__")

    def __init__(self, owner, *, _mint=None):
        check(_mint is _MINT, "sync_input_mint")
        self._owner, self._key = weakref.ref(owner), object()

    def _record(self):
        check(hasattr(self, "_owner") and hasattr(self, "_key"), "sync_input_retired")
        owner = self._owner()
        record = None if owner is None else owner._buffers.get(self._key)
        check(record is not None and record.handle() is self and not record.revoked and
              not record.consuming, "sync_input_retired")
        return owner, record

    @property
    @admission_boundary
    def nbytes(self):
        _, record = self._record()
        return len(record.raw)

    def close(self):
        if not hasattr(self, "_owner"):
            return
        owner = self._owner()
        if owner is not None:
            record = owner._buffers.get(self._key)
            if record is not None and record.handle() is self:
                owner._retire(self._key)

    def __del__(self):
        if hasattr(self, "_owner"):
            self.close()


def mint_input_owner(cache):
    # The owner object, weakref and registries are themselves prepaid before
    # construction, including a first intake attempted at an exhausted cap.
    credit = cache.ledger.reserve(_BASE_HEAP)
    try:
        return InputOwner(cache, _credit=credit, _mint=_MINT)
    except BaseException:
        credit.close()
        raise


@contextmanager
def input_bytes(cache, supplied):
    """Internal synchronous pin; opaque refs never cross a process boundary."""
    if type(supplied) is not OwnedInputRef:
        yield supplied, False
        return
    owner = record = raw = None
    code = signal = public = None
    try:
        owner, record = supplied._record()
        owner._check()
        check(owner._cache() is cache and cache._inputs is owner, "sync_input_owner")
        record.consuming = True
        raw = record.raw
        yield raw, True
        # The cache lock remains held: retire publication before another query
        # can observe a view if a callback disconnected/revoked its intake.
        if record.revoked or owner._closed:
            cache.disconnect()
            check(False, "sync_input_retired")
        owner._check()
    except BaseException as error:
        # Retire unwound parser/callback frames before refunding their input
        # pin, rather than leaving a raw alias in a saved failure traceback.
        code, signal, public = _retire_error(error)
    finally:
        raw = None
        if record is not None and record.consuming:
            record.consuming = False
        supplied.close()
    if signal is not None:
        raise signal
    if public is not None:
        raise public
    if code is not None:
        raise ProtocolError(code)
