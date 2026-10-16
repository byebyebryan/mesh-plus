"""Strict bounded baseline admission one table entry at a time.

The scanner keeps byte spans into an immutable input. Each actual JSON value
still crosses the strict decoder; it never parses a second full roster DTO.
"""

import re

from ..protocol import check
from .canonical import PackedAtom, decode, decode_reservation
from .model import SPACES, NativeTag
from .reconstruction import TABLE_LIMITS
from .wire import MAX_NATIVE, closed, cursor

_STRUCTURE = re.compile(rb'[\[\]{}"]')
_WHITESPACE = b" \t\r\n"


def _skip(data, position, end):
    while position < end and data[position] in _WHITESPACE:
        position += 1
    return position


def _string_end(data, position, end):
    position += 1
    while True:
        quote = data.find(b'"', position, end)
        check(quote >= 0, "sync_json")
        previous, escapes = quote - 1, 0
        while previous >= position and data[previous] == 92:
            escapes += 1
            previous -= 1
        if not escapes % 2:
            return quote + 1
        position = quote + 1


def _value_end(data, position, end):
    check(position < end, "sync_json")
    first = data[position]
    if first == 34:
        return _string_end(data, position, end)
    if first not in (91, 123):
        stop = position
        while stop < end and data[stop] not in b",]} \t\r\n":
            stop += 1
        check(stop > position, "sync_json")
        return stop
    stack = [93 if first == 91 else 125]
    position += 1
    while stack:
        found = _STRUCTURE.search(data, position, end)
        check(found is not None, "sync_json")
        position = found.start()
        token = data[position]
        if token == 34:
            position = _string_end(data, position, end)
            continue
        if token in (91, 123):
            stack.append(93 if token == 91 else 125)
            check(len(stack) <= 64, "sync_tree_depth")
        else:
            check(token == stack.pop(), "sync_json")
        position += 1
    return position


def object_spans(data, start=0, end=None, *, maximum=8):
    end = len(data) if end is None else end
    start = _skip(data, start, end)
    check(start < end and data[start] == 123, "sync_json_object")
    position, result = _skip(data, start + 1, end), {}
    if position < end and data[position] == 125:
        check(_skip(data, position + 1, end) == end, "sync_json")
        return result
    while True:
        check(position < end and data[position] == 34, "sync_json_object_key")
        key_end = _string_end(data, position, end)
        key = decode(data[position:key_end], 256)
        check(type(key) is str and key not in result, "sync_duplicate_key")
        check(len(result) < maximum, "sync_object_capacity")
        position = _skip(data, key_end, end)
        check(position < end and data[position] == 58, "sync_json")
        value_start = _skip(data, position + 1, end)
        value_end = _value_end(data, value_start, end)
        result[key] = value_start, value_end
        position = _skip(data, value_end, end)
        check(position < end, "sync_json")
        if data[position] == 125:
            check(_skip(data, position + 1, end) == end, "sync_json")
            return result
        check(data[position] == 44, "sync_json")
        position = _skip(data, position + 1, end)


def array_spans(data, start, end):
    position = _skip(data, start, end)
    check(position < end and data[position] == 91, "sync_json_array")
    position = _skip(data, position + 1, end)
    if position < end and data[position] == 93:
        check(_skip(data, position + 1, end) == end, "sync_json")
        return
    while True:
        value_end = _value_end(data, position, end)
        yield position, value_end
        position = _skip(data, value_end, end)
        check(position < end, "sync_json")
        if data[position] == 93:
            check(_skip(data, position + 1, end) == end, "sync_json")
            return
        check(data[position] == 44, "sync_json")
        position = _skip(data, position + 1, end)


class _Table:
    __slots__ = ("_data", "_span", "_ledger", "_count", "_packed")

    def __init__(self, data, span, ledger, maximum, *, packed_values=False):
        self._data, self._span, self._ledger = data, span, ledger
        self._count = 0
        self._packed = packed_values
        for _ in array_spans(data, *span):
            self._count += 1
            check(self._count <= maximum, "sync_table_capacity")

    def __len__(self):
        return self._count

    def __iter__(self):
        for start, end in array_spans(self._data, *self._span):
            with self._ledger.reserve(end - start + 256, encoded=end - start):
                raw = self._data[start:end]
                with self._ledger.reserve(decode_reservation(raw)):
                    row = decode(raw, _depth=3)
                    check(type(row) is list and len(row) == 2, "sync_table_entry")
                    yield (row[0], PackedAtom._from_private_json(row[1])) if self._packed else row


def baseline_header(raw, descriptor, ledger):
    """Return a bounded private header and lazy tables; owns no read authority."""
    check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_message_capacity")
    spans = object_spans(raw)
    check(set(spans) == {"kind", "descriptor", "nativeBinding", "tag", "cursor", "tables"}, "sync_baseline_shape")
    limits = {"kind": 32, "descriptor": 16384, "nativeBinding": 256 * 1024, "tag": 512, "cursor": 512}
    size = 0
    for name, maximum in limits.items():
        start, end = spans[name]
        check(end - start <= maximum, "sync_baseline_header_capacity")
        size += end - start + decode_reservation(raw, maximum, _start=start, _end=end)
    reservation = ledger.reserve(size)
    try:
        document = {name: decode(raw[spans[name][0]:spans[name][1]], maximum, _depth=1)
                    for name, maximum in limits.items()}
        check(document["kind"] == "baseline", "sync_expected_baseline")
    # Closed native descriptor is profile-owned, but its exact configured bytes
    # are checked before any table values are admitted.
        from .canonical import canonical
        check(canonical(document["descriptor"]) == descriptor.native_descriptor, "sync_native_descriptor")
        check(type(document["nativeBinding"]) is dict, "sync_native_binding")
        tag = NativeTag.parse(document["tag"])
        cursor(document["cursor"], tag, document["nativeBinding"].get("ownerEpoch"))
        tables = object_spans(raw, *spans["tables"])
        check(set(tables) == set(SPACES), "sync_table_registry")
        document["tables"] = {name: _Table(raw, tables[name], ledger, TABLE_LIMITS[name],
                                          packed_values=name not in {"receipts", "cohorts", "metadata"}) for name in SPACES}
        closed(document, "kind descriptor nativeBinding tag cursor tables", "sync_baseline_shape")
        return document, reservation
    except BaseException:
        reservation.close()
        raise
