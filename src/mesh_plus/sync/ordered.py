"""Persistent ordered profile indexes, independent of wire commitments.

Only a declared ordered index uses this tree. JSON values have a total order:
null, bool, integer, string, array, object; composite values compare
lexicographically. A facade chooses keys that encode its reviewed native order.
"""

from dataclasses import dataclass
from functools import cmp_to_key

from ..protocol import check
from .budget import OwnedUnit
from .canonical import Atom, FrozenObject, thaw
from .commitment import ABSENT


def compare(left, right):
    types = {type(None): 0, bool: 1, int: 2, str: 3, tuple: 4, FrozenObject: 5}
    a, b = types[type(left)], types[type(right)]
    if a != b:
        return (a > b) - (a < b)
    if a == 0:
        return 0
    if a <= 3:
        return (left > right) - (left < right)
    if a == 5:
        left, right = left._items, right._items
    for first, second in zip(left, right):
        result = compare(first, second)
        if result:
            return result
    return (len(left) > len(right)) - (len(left) < len(right))


@dataclass(frozen=True, slots=True)
class OrderedNode(OwnedUnit):
    key: Atom
    atom: Atom
    left: object
    right: object
    height: int
    count: int

    def owned_children(self):
        return self.key, self.atom, self.left, self.right, self.height, self.count


def _height(node):
    return 0 if node is None else node.height


def _count(node):
    return 0 if node is None else node.count


def _node(key, value, left=None, right=None):
    return OrderedNode(key, value, left, right, 1 + max(_height(left), _height(right)),
                       1 + _count(left) + _count(right))


def _balance(key, value, left, right):
    delta = _height(left) - _height(right)
    if delta > 1:
        if _height(left.left) < _height(left.right):
            pivot = left.right
            left = _node(pivot.key, pivot.atom, _node(left.key, left.atom, left.left, pivot.left), pivot.right)
        return _node(left.key, left.atom, left.left, _node(key, value, left.right, right))
    if delta < -1:
        if _height(right.right) < _height(right.left):
            pivot = right.left
            right = _node(pivot.key, pivot.atom, pivot.left, _node(right.key, right.atom, pivot.right, right.right))
        return _node(right.key, right.atom, _node(key, value, left, right.left), right.right)
    return _node(key, value, left, right)


@dataclass(frozen=True, slots=True)
class OrderedMap(OwnedUnit):
    node: OrderedNode | None = None

    def owned_children(self):
        return (self.node,)

    def __len__(self):
        return _count(self.node)

    def find(self, key):
        value, node = Atom.own(key).value, self.node
        while node is not None:
            result = compare(value, node.key.value)
            if result == 0:
                return node
            node = node.left if result < 0 else node.right
        return ABSENT

    def get(self, key):
        leaf = self.find(key)
        return ABSENT if leaf is ABSENT else leaf.atom.value

    def put(self, key, value):
        return self.put_atom(key, Atom.own(value))

    def put_atom(self, key, atom):
        check(type(atom) is Atom, "sync_owned_atom")
        owned = Atom.own(key)

        def insert(node):
            if node is None:
                return _node(owned, atom)
            result = compare(owned.value, node.key.value)
            if result == 0:
                return node if node.atom.encoded == atom.encoded else _node(node.key, atom, node.left, node.right)
            if result < 0:
                return _balance(node.key, node.atom, insert(node.left), node.right)
            return _balance(node.key, node.atom, node.left, insert(node.right))

        return OrderedMap(insert(self.node))

    def remove(self, key):
        owned = Atom.own(key)

        def delete(node, value):
            check(node is not None, "sync_missing_key")
            result = compare(value, node.key.value)
            if result < 0:
                return _balance(node.key, node.atom, delete(node.left, value), node.right)
            if result > 0:
                return _balance(node.key, node.atom, node.left, delete(node.right, value))
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            successor = node.right
            while successor.left is not None:
                successor = successor.left
            return _balance(successor.key, successor.atom, node.left, delete(node.right, successor.key.value))

        return OrderedMap(delete(self.node, owned.value))

    def leaf_at(self, rank):
        check(type(rank) is int and 0 <= rank < len(self), "sync_index_rank")
        node = self.node
        while True:
            count = _count(node.left)
            if count == rank:
                return node
            if rank < count:
                node = node.left
            else:
                rank -= count + 1
                node = node.right

    def lower_bound(self, key):
        value, node, skipped = Atom.own(key).value, self.node, 0
        while node is not None:
            if compare(node.key.value, value) < 0:
                skipped += 1 + _count(node.left)
                node = node.right
            else:
                node = node.left
        return skipped

    @classmethod
    def baseline(cls, entries):
        values = [(Atom.own(key), Atom.own(value)) for key, value in entries]
        values.sort(key=cmp_to_key(lambda a, b: compare(a[0].value, b[0].value)))
        check(all(compare(values[i - 1][0].value, values[i][0].value) != 0
                  for i in range(1, len(values))), "sync_duplicate_key")

        def build(start, stop):
            if start == stop:
                return None
            middle = (start + stop) // 2
            key, value = values[middle]
            return _node(key, value, build(start, middle), build(middle + 1, stop))

        return cls(build(0, len(values)))


def index_key(node):
    """Detached key for explicit lazy enumeration, without exposing an atom."""
    return thaw(node.key.value)
