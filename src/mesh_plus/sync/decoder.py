"""Small quota-accounted decoded-value arena for privately packed JSON atoms."""

import contextlib
from collections import OrderedDict
from dataclasses import dataclass

from ..protocol import ProtocolError, check
from .budget import OwnedUnit, _payload_size
from .canonical import PACKED_DECODER, _freeze, decode, decode_reservation


@dataclass(frozen=True, slots=True)
class _Decoded(OwnedUnit):
    source: object
    value: object
    intrinsic: int

    def owned_children(self):
        return (self.source,)

    def owned_intrinsic(self):
        return self.intrinsic


@dataclass(frozen=True, slots=True)
class _ArenaLayout(OwnedUnit):
    maximum: int

    def owned_intrinsic(self):
        # Fixed capacity allowance for the private OrderedDict and its integer
        # keys/links. Decoded entries and their root registrations are separate.
        return 512 + 256 * self.maximum


class DecoderArena:
    def __init__(self, ledger, *, maximum=16):
        check(type(maximum) is int and 0 < maximum <= 32, "sync_decoder_capacity")
        self.ledger, self.maximum = ledger, maximum
        self.entries = OrderedDict()
        self.decodes = 0
        self._closed = False
        self._layout = _ArenaLayout(maximum)
        self.ledger.retain(self._layout)

    @contextlib.contextmanager
    def active(self):
        check(not self._closed, "sync_decoder_closed")
        token = PACKED_DECODER.set(self)
        try:
            yield
        finally:
            PACKED_DECODER.reset(token)

    def load(self, atom):
        check(not self._closed, "sync_decoder_closed")
        key = id(atom)
        if key in self.entries:
            self.entries.move_to_end(key)
            return self.entries[key].value
        while len(self.entries) >= self.maximum:
            self.evict()
        amount = decode_reservation(atom.encoded)
        while True:
            try:
                reservation = self.ledger.reserve(amount)
                break
            except ProtocolError:
                if not self.entries:
                    raise
                self.evict()
        try:
            document = decode(atom.encoded)
            value = _freeze(document)
            owned = _Decoded(atom, value, _payload_size(value))
            self.ledger.retain(owned)
            try:
                self.entries[key] = owned
            except BaseException:
                self.ledger.release(owned)
                raise
            self.decodes += 1
            return value
        finally:
            reservation.close()

    def evict(self):
        _, entry = self.entries.popitem(last=False)
        self.ledger.release(entry)

    def clear(self):
        while self.entries:
            self.evict()

    def close(self):
        if self._closed:
            return
        self.clear()
        self.ledger.release(self._layout)
        self._layout = None
        self._closed = True
