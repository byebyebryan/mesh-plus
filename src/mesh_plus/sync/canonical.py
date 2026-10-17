"""Integer-only canonical JSON and privately owned immutable values."""

import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass

from ..protocol import ProtocolError, check
from ._allocation import TrackedAllocation, finish, prepay, prepay_json

PACKED_DECODER = ContextVar("mesh_sync_private_decoder", default=None)


@dataclass(frozen=True, slots=True)
class FrozenObject(Mapping):
    _items: tuple

    def __iter__(self):
        return (key for key, _ in self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, key):
        lo, hi = 0, len(self._items)
        while lo < hi:
            mid = (lo + hi) // 2
            name, value = self._items[mid]
            if name == key:
                return value
            if name < key:
                lo = mid + 1
            else:
                hi = mid
        raise KeyError(key)


def _validate(value, depth=0, budget=None):
    check(depth <= 64, "sync_tree_depth")
    kind = type(value)
    if kind is str:
        check(value.isascii() or not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "sync_unicode")
    elif kind is dict:
        if budget is not None:
            budget[0] += 248 + 72 * len(value)
        for key, child in value.items():
            check(type(key) is str, "sync_object_key")
            _validate(key, depth + 1)
            _validate(child, depth + 1, budget)
    elif kind is list:
        if budget is not None:
            budget[0] += 96 + 16 * len(value)
        for child in value:
            _validate(child, depth + 1, budget)
    else:
        check(kind in (int, bool, type(None)), "sync_json_type")


def canonical(value):
    """Encode a newly supplied plain JSON value; never accepts object subclasses."""
    reservation = prepay_json(value)
    try:
        output = bytearray()
        _encode(value, output)
        return bytes(output)
    except ProtocolError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, RuntimeError) as error:
        raise ProtocolError("sync_json") from error
    finally:
        if reservation is not None:
            reservation.close()


def _encode(value, output, depth=0):
    """Validate each captured node while emitting; no temporary frozen tree.

    Retained values still use Atom.own. Canonical byte results have no decoded
    graph and no alias to the supplied mutable containers.
    """
    check(depth <= 64, "sync_tree_depth")
    kind = type(value)
    if kind is str:
        _validate(value, depth)
        output.extend(json.encoder.encode_basestring(value).encode("utf-8"))
    elif kind is bool:
        output.extend(b"true" if value else b"false")
    elif value is None:
        output.extend(b"null")
    elif kind is int:
        output.extend(str(value).encode("ascii"))
    elif kind is list:
        output.extend(b"[")
        for number, child in enumerate(value):
            if number:
                output.extend(b",")
            _encode(child, output, depth + 1)
        output.extend(b"]")
    else:
        check(kind is dict, "sync_json_type")
        check(all(type(key) is str for key in value), "sync_object_key")
        output.extend(b"{")
        for number, key in enumerate(sorted(value)):
            if number:
                output.extend(b",")
            _encode(key, output, depth + 1)
            output.extend(b":")
            _encode(value[key], output, depth + 1)
        output.extend(b"}")


def decode(raw, maximum=8 * 1024 * 1024 + 80 * 1024, *, _depth=0):
    check(type(raw) is bytes and len(raw) <= maximum, "sync_message_capacity")
    check(not raw.startswith(b"\xef\xbb\xbf"), "sync_bom")

    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "sync_duplicate_key")
            result[key] = value
        return result

    def integer(text):
        check(text != "-0", "sync_negative_zero")
        return int(text)

    def invalid(_):
        raise ProtocolError("sync_json_number")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_int=integer,
                           parse_float=invalid, parse_constant=invalid)
        _validate(value, _depth)
        return value
    except ProtocolError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ProtocolError("sync_json") from error


def _freeze(value, depth=0, budget=None):
    check(depth <= 64, "sync_tree_depth")
    if type(value) is dict:
        if budget is not None:
            budget[0] += 248 + 72 * len(value)
        items = []
        for key, child in value.items():
            check(type(key) is str, "sync_object_key")
            _validate(key, depth + 1)
            items.append((key.encode("utf-8").decode("utf-8"), _freeze(child, depth + 1, budget)))
        return FrozenObject(tuple(sorted(items)))
    if type(value) is list:
        if budget is not None:
            budget[0] += 96 + 16 * len(value)
        return tuple(_freeze(child, depth + 1, budget) for child in value)
    check(type(value) in (str, int, bool, type(None)), "sync_json_type")
    _validate(value, depth)
    if type(value) is str:
        return value.encode("utf-8").decode("utf-8")
    if type(value) is int and not -5 <= value <= 256:
        return int(str(value))
    return value


def thaw(value):
    """Explicit detached output; its O(output) cost belongs to the caller."""
    if type(value) is FrozenObject:
        return {key: thaw(child) for key, child in value._items}
    if type(value) is tuple:
        return [thaw(child) for child in value]
    check(type(value) in (str, int, bool, type(None)), "sync_frozen_type")
    return value


@dataclass(frozen=True, slots=True)
class Atom(TrackedAllocation):
    encoded: bytes
    value: object
    copy_budget: int = 0

    @classmethod
    def own(cls, value):
        reservation = prepay_json(value)
        try:
            budget = [0]
            frozen = _freeze(value, budget=budget)
            encoded = json.dumps(thaw(frozen), sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            return finish(cls(encoded, frozen, budget[0]), reservation)
        except ProtocolError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError, RuntimeError) as error:
            raise ProtocolError("sync_json") from error
        finally:
            if reservation is not None:
                reservation.close()


@dataclass(frozen=True, slots=True)
class PackedAtom(TrackedAllocation):
    """Private canonical value storage; decoding is a bounded owner operation.

    It commits the exact same bytes as Atom. A public callback never receives
    this object; its read refs resolve through the owning decoder arena.
    """

    encoded: bytes
    copy_budget: int

    @property
    def value(self):
        decoder = PACKED_DECODER.get()
        return _freeze(decode(self.encoded)) if decoder is None or self.copy_budget == 0 else decoder.load(self)

    @classmethod
    def from_owned(cls, atom):
        check(type(atom) is Atom, "sync_owned_atom")
        reservation = prepay(len(atom.encoded) + 1024, len(atom.encoded))
        try:
            return finish(cls(atom.encoded, atom.copy_budget), reservation)
        finally:
            if reservation is not None:
                reservation.close()

    @classmethod
    def _from_private_json(cls, value):
        """Only for receiver-owned decoder output, never mutable user input.

        No external reference sees the decoded table entry. Retain its strict
        canonical bytes without first building another complete frozen tree.
        """
        reservation = prepay_json(value)
        try:
            budget = [0]
            _validate(value, budget=budget)
            encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            return finish(cls(encoded, budget[0]), reservation)
        finally:
            if reservation is not None:
                reservation.close()


@dataclass(frozen=True, slots=True)
class InputKey(PackedAtom):
    """Baseline-only key bytes borrowed from its staged table leaf.

    Never retained in a material root or returned as a public capability. The
    enclosing baseline owns the leaf throughout the operation callback.
    """

    @classmethod
    def borrow(cls, encoded):
        reservation = prepay(1024, 0)
        try:
            budget = _key_copy_budget(encoded)
            return finish(cls(encoded, budget), reservation)
        finally:
            if reservation is not None:
                reservation.close()


def _key_copy_budget(encoded):
    """Container-copy bound from an already owned canonical key, no decode.

    Commas plus nonempty containers count all members. Colons then separate
    dictionary entries from array elements. Quoted punctuation is ignored.
    The result matches Atom's existing detached-container allowance exactly.
    """
    if encoded[:1] not in (b"[", b"{"):
        return 0
    arrays = objects = nonempty = commas = colons = 0
    quoted = escaped = False
    for index, byte in enumerate(encoded):
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            arrays += int(byte == 91)
            objects += int(byte == 123)
            nonempty += int(encoded[index + 1] != (93 if byte == 91 else 125))
        elif byte == 44:
            commas += 1
        elif byte == 58:
            colons += 1
    return 96 * arrays + 16 * (commas + nonempty - colons) + 248 * objects + 72 * colons


def packed(atom):
    check(type(atom) in (Atom, PackedAtom), "sync_owned_atom")
    if type(atom) is PackedAtom:
        return atom
    # Keep small scalar tokens directly available. Container trees and long
    # strings retain only their canonical bytes in the material graph.
    if type(atom.value) in (FrozenObject, tuple) or type(atom.value) is str and len(atom.value) >= 64:
        return PackedAtom.from_owned(atom)
    return atom


def decode_reservation(raw, maximum=8_404_992, *, _start=0, _end=None):
    """Conservative lexical preflight; scans received bytes, not old roots."""
    check(type(raw) is bytes, "sync_message_capacity")
    end = len(raw) if _end is None else _end
    check(type(_start) is int and type(end) is int and 0 <= _start <= end <= len(raw) and
          end - _start <= maximum, "sync_message_capacity")
    strings = containers = scalars = 0
    quoted = escaped = False
    for byte in memoryview(raw)[_start:end]:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
            strings += 1
        elif byte in (91, 123):
            containers += 1
        elif byte in (44, 58):
            scalars += 1
    return 4096 + (end - _start) * 4 + strings * 96 + containers * 256 + scalars * 32
