"""Integer-only canonical JSON and privately owned immutable values."""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from ..protocol import ProtocolError, check


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


def decode(raw, maximum=8 * 1024 * 1024 + 80 * 1024):
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
        _validate(value)
        return value
    except ProtocolError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise ProtocolError("sync_json") from error


def _freeze(value, depth=0):
    check(depth <= 64, "sync_tree_depth")
    if type(value) is dict:
        items = []
        for key, child in value.items():
            check(type(key) is str, "sync_object_key")
            _validate(key, depth + 1)
            items.append((key.encode("utf-8").decode("utf-8"), _freeze(child, depth + 1)))
        return FrozenObject(tuple(sorted(items)))
    if type(value) is list:
        return tuple(_freeze(child, depth + 1) for child in value)
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
class Atom:
    encoded: bytes
    value: object

    @classmethod
    def own(cls, value):
        try:
            frozen = _freeze(value)
            encoded = json.dumps(thaw(frozen), sort_keys=True, ensure_ascii=False,
                                 separators=(",", ":"), allow_nan=False).encode("utf-8")
            return cls(encoded, frozen)
        except ProtocolError:
            raise
        except (ValueError, TypeError, UnicodeError, RecursionError, RuntimeError) as error:
            raise ProtocolError("sync_json") from error
