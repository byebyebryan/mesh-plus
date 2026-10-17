"""Channel-scoped transport storage; never an admission capability.

The private allocation engine is shared with cache intake. Public relay types
remain distinct, and the cache's exact-type admission check rejects them.
"""

import weakref
from contextlib import contextmanager

from ..protocol import ProtocolError, check
from ._boundary import _retire_error, admission_boundary
from .budget import Reservation
from .inputs import (
    _BASE_HEAP,
    _LEASE_HEAP,
    _MAX_ITEMS,
    _MINT,
    InputOwner,
    InputReservation,
    OwnedInputRef,
    _Buffer,
)
from .wire import MAX_NATIVE


class RelayInputOwner(InputOwner):
    def __init__(self, channel, *, _credit=None, _mint=None):
        check(_mint is _MINT, "sync_input_mint")
        self._base = _credit
        self._channel = weakref.ref(channel)
        self._ledger = channel._relay.ledger
        self._leases, self._buffers = {}, {}
        self._closed = False

    def _check(self):
        channel = self._channel()
        check(not self._closed and channel is not None and channel._inputs is self,
              "sync_input_retired")
        channel._check()

    @admission_boundary
    def reserve(self, heap_bytes, *, encoded_bytes=0):
        self._check()
        check(type(heap_bytes) is int and heap_bytes >= 0 and
              type(encoded_bytes) is int and encoded_bytes >= 0, "sync_reservation")
        check(len(self._leases) + len(self._buffers) < _MAX_ITEMS, "sync_input_slots")
        credit = self._ledger.reserve(heap_bytes + _LEASE_HEAP, encoded=encoded_bytes)
        try:
            lease = RelayInputReservation(self, credit, _mint=_MINT)
            self._leases[lease._key] = lease
            return lease
        except BaseException:
            credit.close()
            raise

    def close(self):
        self._close()
        channel = self._channel()
        if channel is not None:
            channel._begin_close()


class RelayInputReservation(InputReservation):
    @admission_boundary
    def seal(self, raw):
        owner = self._check()
        check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_input_bytes")
        check(len(owner._leases) + len(owner._buffers) < _MAX_ITEMS, "sync_input_slots")
        cost = owner.buffer_heap(len(raw))
        check(cost <= self.heap_bytes and len(raw) <= self.encoded_bytes, "sync_input_credit")
        credit = Reservation(owner._ledger, cost, len(raw))
        try:
            handle = RelayInputRef(owner, _mint=_MINT)
            record = _Buffer(raw, credit, weakref.ref(handle))
            owner._buffers[handle._key] = record
        except BaseException:
            credit.closed = True  # original lease still owns the credit
            raise
        self._credit.amount -= cost
        self._credit.encoded_amount -= len(raw)
        return handle


class RelayInputRef(OwnedInputRef):
    """Opaque exclusive transfer to this relay channel, with no byte export."""


def mint_relay_inputs(channel):
    credit = channel._relay.ledger.reserve(_BASE_HEAP)
    try:
        return RelayInputOwner(channel, _credit=credit, _mint=_MINT)
    except BaseException:
        credit.close()
        raise


@contextmanager
def relay_bytes(channel, supplied):
    """Private single-consume pin, held through scanner and output unwind."""
    owner = record = raw = None
    code = signal = public = None
    try:
        check(type(supplied) is RelayInputRef, "sync_input_owner")
        owner, record = supplied._record()
        owner._check()
        check(owner._channel() is channel and channel._inputs is owner, "sync_input_owner")
        record.consuming = True
        raw = record.raw
        yield raw
        check(not record.revoked, "sync_input_retired")
        owner._check()
    except BaseException as error:
        code, signal, public = _retire_error(error)
    finally:
        raw = None
        if record is not None and record.consuming and not channel._io_failed:
            record.consuming = False
        # A foreign valid handle retires only itself, never sibling records.
        if type(supplied) is RelayInputRef:
            supplied.close()
        supplied = owner = record = None
    if signal is not None:
        raise signal
    if public is not None:
        raise public
    if code is not None:
        raise ProtocolError(code)
