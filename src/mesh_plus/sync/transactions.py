"""Strict native transactions without a second decoded operations roster."""

from hashlib import sha256

from ..protocol import check
from .canonical import Atom, PackedAtom, canonical, decode, decode_reservation
from .model import SPACES, NativeTag, hex_digest
from .reconstruction import TABLE_LIMITS, Operation
from .streaming import array_spans, object_spans
from .wire import MAX_NATIVE, cursor

_LIMITS = {"kind": 32, "descriptor": 16384, "nativeBindingDigest": 512,
           "transactionId": 512, "baseTag": 512, "resultTag": 512,
           "baseCursor": 512, "resultCursor": 512}


def _operation_parts(operation):
    yield b'["put",' if operation.op == "put" else b'["remove",'
    yield operation.key.encoded
    yield b","
    yield b"null" if operation.expected is None else b'"' + operation.expected.encode("ascii") + b'"'
    if operation.op == "put":
        yield b","
        yield operation.value.encoded
    yield b"]"


def _parts(header, grouped):
    """C(transaction excluding ID), assembled from already canonical atoms."""
    yield b"{"
    for index, name in enumerate(sorted((set(header) - {"transactionId"}) | {"operations"})):
        if index:
            yield b","
        yield canonical(name)
        yield b":"
        if name != "operations":
            yield canonical(header[name])
            continue
        yield b"{"
        for space_index, space in enumerate(sorted(SPACES)):
            if space_index:
                yield b","
            yield canonical(space)
            yield b":["
            for row_index, operation in enumerate(grouped[space]):
                if row_index:
                    yield b","
                yield from _operation_parts(operation)
            yield b"]"
        yield b"}"
    yield b"}"


def transaction_input(raw, descriptor, ledger):
    """Return owned normalized operations and a live header/scratch lease.

    The caller enters ledger.allocations() and retains the immutable raw buffer
    throughout this scope. No operation value can escape as a mutable DTO.
    """
    check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_message_capacity")
    spans = object_spans(raw, maximum=9)
    check(set(spans) == set(_LIMITS) | {"operations"}, "sync_transaction_shape")
    size = 4096
    for name, maximum in _LIMITS.items():
        start, end = spans[name]
        check(end - start <= maximum, "sync_transaction_header_capacity")
        size += end - start + decode_reservation(raw, maximum, _start=start, _end=end)
    reservation = ledger.reserve(size)
    try:
        header = {name: decode(raw[spans[name][0]:spans[name][1]], maximum, _depth=1)
                  for name, maximum in _LIMITS.items()}
        check(header["kind"] == "transaction", "sync_expected_transaction")
        check(canonical(header["descriptor"]) == descriptor.native_descriptor, "sync_native_descriptor")
        base, result = NativeTag.parse(header["baseTag"]), NativeTag.parse(header["resultTag"])
        check(header["nativeBindingDigest"] == base.binding == result.binding and
              result.generation == base.generation + 1, "sync_transaction_tag")
        before = cursor(header["baseCursor"], base)
        cursor(header["resultCursor"], result, before[0])
        hex_digest(header["transactionId"])
        spaces = object_spans(raw, *spans["operations"])
        check(set(spaces) == set(SPACES), "sync_operation_registry")
        grouped, count = {}, 0
        for space in SPACES:
            changes, seen = [], set()
            for start, end in array_spans(raw, *spaces[space]):
                check(len(changes) < TABLE_LIMITS[space] * 2, "sync_operation_capacity")
                # Covers both pointer lists/tuples and duplicate-key set slots.
                if count % 64 == 0:
                    reservation.grow(512 * 64)
                count += 1
                with ledger.reserve(end - start + 256, encoded=end - start):
                    row = raw[start:end]
                    with ledger.reserve(decode_reservation(row)):
                        change = decode(row, _depth=3)
                        check(type(change) is list and len(change) in (3, 4), "sync_operation_shape")
                        check(change[0] == "put" and len(change) == 4 or
                              change[0] == "remove" and len(change) == 3 and change[2] is not None,
                              "sync_operation_shape")
                        if change[2] is not None:
                            hex_digest(change[2])
                        key = Atom.own(change[1])
                        check(key.encoded not in seen, "sync_duplicate_operation")
                        seen.add(key.encoded)
                        value = None
                        if change[0] == "put":
                            value = (Atom.own(change[3]) if space in {"receipts", "cohorts", "metadata"}
                                     else PackedAtom._from_private_json(change[3]))
                        changes.append(Operation(space, change[0], key, change[2], value))
            grouped[space] = tuple(changes)
        # Length-prefix framing requires a first pass over canonical pieces,
        # never a concatenated full transaction or a second JSON value tree.
        length = sum(len(part) for part in _parts(header, grouped))
        digest = sha256(b"mesh-sync-transaction\0" + length.to_bytes(8, "big"))
        for part in _parts(header, grouped):
            digest.update(part)
        check(digest.hexdigest() == header["transactionId"], "sync_transaction_id")
        header["operations"] = tuple(operation for space in SPACES for operation in grouped[space])
        return header, reservation
    except BaseException:
        reservation.close()
        raise
