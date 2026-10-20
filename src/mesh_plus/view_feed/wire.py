"""Prepaid strict JSON framing for the explicit feed's owned LineChannel.

Delivery schemas and actual frame bytes are unchanged. The lexical preflight
counts an upper bound on JSON nodes before allocating the decoded tree. Leases
follow decoded frames, queued payloads, serialized writes and retained errors.
"""

import copy

from ..protocol import MAX_MESSAGE, check, decode, encode, validate
from .protocol import json_size


class CreditOwner:
    __slots__ = ("lease",)

    def __init__(self, lease):
        self.lease = lease

    def __del__(self):
        self.lease.close()


class _DecodedFrame(dict):
    def __init__(self, value, credit):
        super().__init__(value)
        self._feed_credit = credit

    def __deepcopy__(self, memo):
        return copy.deepcopy(dict(self), memo)


class _EncodedFrame(bytes):
    def __new__(cls, raw, credit):
        result = super().__new__(cls, raw)
        result._feed_credit = credit
        return result


def _nodes(raw):
    """Upper-bound containers, values and keys without constructing strings."""
    count = 1
    quoted = escaped = False
    depth = 0
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (123, 91):
            depth += 1
            check(depth <= 65, "tree_depth")
            count += 1
        elif byte in (125, 93):
            depth -= 1
        elif byte in (44, 58):
            count += 1
    return count


class FeedWireCodec:
    """Same Delivery v1 encoding with a shared feed ownership ledger."""

    def __init__(self, budget):
        self.budget = budget
        self.closed = False
        # Existing StreamReader buffers can reach twice their configured limit.
        # Reserve raw/partial/returned-line overlap before starting owned IO.
        # This is conservative reserved capacity, not allocated RAM or RSS.
        self._carrier_credit = budget.reserve(encoded=3 * MAX_MESSAGE + 65536,
                                              heap=3 * MAX_MESSAGE + 131072)

    def decode(self, raw, direction, maximum=MAX_MESSAGE):
        check(not self.closed, "view_feed_wire_closed")
        size = len(raw)
        check(size <= maximum, "message_capacity")
        count = _nodes(raw)
        # Plain JSON dict/list/scalar allocations, Unicode expansion, parser
        # scratch and bounded schema traversal. Large trees refuse before parse.
        lease = self.budget.reserve(encoded=size, heap=256 * count + 8 * size + 16384)
        credit = CreditOwner(lease)
        value = None
        try:
            value = decode(raw, direction, maximum)
            check(not self.closed, "view_feed_wire_closed")
            result = _DecodedFrame(value, credit)
            return result
        except BaseException as error:
            # Do not refund a decoded graph/raw value held by a real traceback.
            error._view_feed_credit = credit
            raise
        finally:
            raw = value = credit = lease = None

    def encode(self, value):
        check(not self.closed, "view_feed_wire_closed")
        size = json_size(value, maximum=MAX_MESSAGE)
        credit = CreditOwner(self.budget.reserve(encoded=2 * size,
                                                 heap=2 * size + 16384))
        raw = None
        try:
            raw = encode(value)
            check(not self.closed, "view_feed_wire_closed")
            return _EncodedFrame(raw, credit)
        except BaseException as error:
            error._view_feed_credit = credit
            raise
        finally:
            value = raw = credit = None

    def validate(self, value, direction, size=None, maximum=MAX_MESSAGE):
        return validate(value, direction, size, maximum)

    def close(self):
        if not self.closed:
            self.closed = True
            self._carrier_credit.close()
            self._carrier_credit = None
