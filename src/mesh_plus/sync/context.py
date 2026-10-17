"""Revocable indexed value references; keeping one never pins an old tree."""

from collections.abc import Mapping, Sequence

from .canonical import FrozenObject, InputKey, PackedAtom, decode_reservation, thaw
from .commitment import ABSENT


def _detach_scalar(value):
    # Immutable scalar leaves have no backlink to a cache/root. Keeping the
    # requested scalar cannot pin a generation, just as with materialize().
    return value


def reference(owner, permit, location, path=()):
    if not path:
        with owner.peek(permit, location) as atom:
            if atom is ABSENT or atom is None:
                return atom
            first = atom.encoded[0]
            if first == 123:
                return ObjectRef(owner, permit, location, path)
            if first == 91:
                return ArrayRef(owner, permit, location, path)
            if type(atom) in (PackedAtom, InputKey):
                with owner.ledger.reserve(decode_reservation(atom.encoded)):
                    return _detach_scalar(atom.value)
            return _detach_scalar(atom.value)
    with owner.borrow(permit, location, path) as value:
        if type(value) is FrozenObject:
            return ObjectRef(owner, permit, location, path)
        if type(value) is tuple:
            return ArrayRef(owner, permit, location, path)
        return _detach_scalar(value)


class _ValueRef:
    __slots__ = ("_owner", "_permit", "_location", "_path")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable sync value reference")
        object.__setattr__(self, name, value)

    def __init__(self, owner, permit, location, path):
        self._owner, self._permit, self._location, self._path = owner, permit, location, path

    def materialize(self):
        """Explicit O(value) detached output; never an implicit header operation."""
        with self._owner.borrow(self._permit, self._location, self._path) as value:
            return thaw(value)

    @property
    def materialization_bytes(self):
        """Pre-copy bound for detached containers, without walking the value.

        Subvalue refs conservatively use their containing atom's bound.
        Immutable scalar leaves are shared, as in deepcopy; no root is shared.
        """
        return self._owner.materialization_budget(self._permit, self._location)

    def __len__(self):
        with self._owner.borrow(self._permit, self._location, self._path) as value:
            return len(value)


class ObjectRef(_ValueRef, Mapping):
    __slots__ = ()

    def __getitem__(self, key):
        if type(key) is not str:
            raise KeyError(key)
        return reference(self._owner, self._permit, self._location, (*self._path, key))

    def __iter__(self):
        for i in range(len(self)):
            with self._owner.borrow(self._permit, self._location, self._path) as value:
                key = _detach_scalar(value._items[i][0])
            yield key


class ArrayRef(_ValueRef, Sequence):
    __slots__ = ()

    def __getitem__(self, index):
        if type(index) is slice:
            return [self[i] for i in range(*index.indices(len(self)))]
        if type(index) is not int:
            raise TypeError("array index must be an integer")
        count = len(self)
        index = index + count if index < 0 else index
        if not 0 <= index < count:
            raise IndexError(index)
        return reference(self._owner, self._permit, self._location, (*self._path, index))
