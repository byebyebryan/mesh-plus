"""Integer-only canonical JSON and privately owned immutable values."""

import json
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass

from ..protocol import ProtocolError, check
from ._allocation import TrackedAllocation

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


def _validate(value, depth=0):
    check(depth <= 64, "sync_tree_depth")
    kind = type(value)
    if kind is str:
        check(value.isascii() or not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "sync_unicode")
    elif kind is dict:
        for key, child in value.items():
            check(type(key) is str, "sync_object_key")
            _validate(key, depth + 1)
            _validate(child, depth + 1)
    elif kind is list:
        for child in value:
            _validate(child, depth + 1)
    else:
        check(kind in (int, bool, type(None)), "sync_json_type")


def canonical(value):
    """Encode a newly supplied plain JSON value; never accepts object subclasses."""
    return Atom.own(value).encoded


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
        try:
            budget = [0]
            frozen = _freeze(value, budget=budget)
            encoded = json.dumps(thaw(frozen), sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            return cls(encoded, frozen, budget[0])
        except ProtocolError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError, RuntimeError) as error:
            raise ProtocolError("sync_json") from error


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
        return cls(atom.encoded, atom.copy_budget)


def packed(atom):
    check(type(atom) in (Atom, PackedAtom), "sync_owned_atom")
    if type(atom) is PackedAtom:
        return atom
    # Keep small scalar tokens directly available. Container trees and long
    # strings retain only their canonical bytes in the material graph.
    if type(atom.value) in (FrozenObject, tuple) or type(atom.value) is str and len(atom.value) >= 64:
        return PackedAtom.from_owned(atom)
    return atom


def decode_reservation(raw, maximum=8_404_992):
    """Conservative lexical preflight; scans received bytes, not old roots."""
    check(type(raw) is bytes and len(raw) <= maximum, "sync_message_capacity")
    strings = containers = scalars = 0
    quoted = escaped = False
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
            strings += 1
        elif byte in (91, 123):
            containers += 1
        elif byte in (44, 58):
            scalars += 1
    return 4096 + len(raw) * 4 + strings * 96 + containers * 256 + scalars * 32
