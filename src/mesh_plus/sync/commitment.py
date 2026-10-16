"""Persistent compressed Patricia maps with locally computed state commitments."""

from dataclasses import dataclass
from hashlib import sha256

from ..protocol import check
from .canonical import Atom, canonical, decode

ABSENT = object()
ANY = object()


def framed(value):
    return len(value).to_bytes(8, "big") + value


def digest(value):
    return sha256(value).digest()


@dataclass(slots=True)
class Work:
    node_reads: int = 0
    node_writes: int = 0
    key_hashes: int = 0
    value_hashes: int = 0
    branch_hashes: int = 0
    iterated_entries: int = 0

    def snapshot(self):
        return {name: getattr(self, name) for name in self.__slots__}


@dataclass(frozen=True, slots=True)
class Leaf:
    key: bytes
    example: bytes
    atom: Atom
    value_hash: bytes
    root: bytes
    count: int = 1


@dataclass(frozen=True, slots=True)
class Branch:
    split: int
    prefix: bytes
    left: object
    right: object
    example: bytes
    root: bytes
    count: int


def _common(a, b):
    return 256 - (int.from_bytes(a, "big") ^ int.from_bytes(b, "big")).bit_length()


def _bit(value, bit):
    return (value[bit // 8] >> (7 - bit % 8)) & 1


class MerkleMap:
    """Immutable roots; updates return another map sharing unchanged subtrees.

    Work is an optional shared instrumentation counter. Enumeration is explicit;
    point changes never call it. Key/value bytes are admitted/owned on insertion.
    """

    __slots__ = ("space", "node", "work", "_framed_space", "_empty")

    def __setattr__(self, name, value):
        if hasattr(self, name):
            raise AttributeError("immutable Merkle map")
        object.__setattr__(self, name, value)

    def __init__(self, space, node=None, *, work=None):
        check(type(space) is str and 0 < len(space.encode()) <= 128, "sync_space")
        self.space, self.node, self.work = space, node, work if work is not None else Work()
        self._framed_space = framed(space.encode())
        self._empty = digest(b"mesh-sync-empty\0" + self._framed_space)

    @property
    def root(self):
        return self._empty if self.node is None else self.node.root

    def __len__(self):
        return 0 if self.node is None else self.node.count

    def _key(self, value):
        encoded = canonical(value)
        self.work.key_hashes += 1
        return encoded, digest(b"mesh-sync-key\0" + self._framed_space + framed(encoded))

    def _leaf(self, key, key_hash, atom):
        self.work.value_hashes += 1
        value_hash = digest(b"mesh-sync-value\0" + self._framed_space + framed(atom.encoded))
        root = digest(b"mesh-sync-leaf\0" + self._framed_space + key_hash +
                      framed(key) + value_hash)
        self.work.node_writes += 1
        return Leaf(key, key_hash, atom, value_hash, root)

    def _branch(self, split, left, right):
        prefix = bytearray(left.example[:(split + 7) // 8])
        if split % 8:
            prefix[-1] &= (255 << (8 - split % 8)) & 255
        prefix = bytes(prefix)
        root = digest(b"mesh-sync-branch\0" + self._framed_space + split.to_bytes(2, "big") +
                      framed(prefix) + left.root + right.root)
        self.work.branch_hashes += 1
        self.work.node_writes += 1
        return Branch(split, prefix, left, right, left.example, root, left.count + right.count)

    def _copy(self, node):
        return MerkleMap(self.space, node, work=self.work)

    def find(self, key):
        encoded, hashed = self._key(key)
        node = self.node
        while node is not None:
            self.work.node_reads += 1
            if isinstance(node, Leaf):
                if node.example == hashed:
                    check(node.key == encoded, "sync_key_hash_collision")
                    return node
                return ABSENT
            if _common(node.example, hashed) < node.split:
                return ABSENT
            node = node.right if _bit(hashed, node.split) else node.left
        return ABSENT

    def get(self, key, default=ABSENT):
        leaf = self.find(key)
        return default if leaf is ABSENT else leaf.atom.value

    def put(self, key, value, *, expected=ANY):
        return self.put_atom(key, Atom.own(value), expected=expected)

    def put_atom(self, key, atom, *, expected=ANY):
        check(type(atom) is Atom, "sync_atom")
        encoded, hashed = self._key(key)

        def insert(node):
            if node is None:
                check(expected is ANY or expected is ABSENT, "sync_expected_value")
                return self._leaf(encoded, hashed, atom)
            self.work.node_reads += 1
            common = _common(node.example, hashed)
            if isinstance(node, Leaf) and common == 256:
                check(node.key == encoded, "sync_key_hash_collision")
                check(expected is ANY or expected == node.value_hash, "sync_expected_value")
                if node.atom.encoded == atom.encoded:
                    return node
                return self._leaf(encoded, hashed, atom)
            if isinstance(node, Leaf) or common < node.split:
                check(expected is ANY or expected is ABSENT, "sync_expected_value")
                leaf = self._leaf(encoded, hashed, atom)
                return self._branch(common, node, leaf) if _bit(hashed, common) else self._branch(common, leaf, node)
            if _bit(hashed, node.split):
                right = insert(node.right)
                return node if right is node.right else self._branch(node.split, node.left, right)
            left = insert(node.left)
            return node if left is node.left else self._branch(node.split, left, node.right)

        return self._copy(insert(self.node))

    def remove(self, key, *, expected=ANY):
        encoded, hashed = self._key(key)

        def delete(node):
            check(node is not None, "sync_missing_key")
            self.work.node_reads += 1
            if isinstance(node, Leaf):
                check(node.example == hashed, "sync_missing_key")
                check(node.key == encoded, "sync_key_hash_collision")
                check(expected is ANY or expected == node.value_hash, "sync_expected_value")
                return None
            check(_common(node.example, hashed) >= node.split, "sync_missing_key")
            if _bit(hashed, node.split):
                right = delete(node.right)
                return node.left if right is None else self._branch(node.split, node.left, right)
            left = delete(node.left)
            return node.right if left is None else self._branch(node.split, left, node.right)

        return self._copy(delete(self.node))

    def items(self):
        stack = [] if self.node is None else [self.node]
        while stack:
            node = stack.pop()
            self.work.node_reads += 1
            if isinstance(node, Leaf):
                self.work.iterated_entries += 1
                yield decode(node.key), node.atom.value
            else:
                stack.extend((node.right, node.left))

    @classmethod
    def baseline(cls, space, entries, *, work=None):
        return cls.baseline_atoms(space, ((key, Atom.own(value)) for key, value in entries), work=work)

    @classmethod
    def baseline_atoms(cls, space, entries, *, work=None):
        """Bulk-build from already privately owned atoms, sharing those atoms."""
        result = cls(space, work=work)
        leaves = []
        for key, atom in entries:
            check(type(atom) is Atom, "sync_atom")
            encoded, hashed = result._key(key)
            leaves.append(result._leaf(encoded, hashed, atom))
        leaves.sort(key=lambda leaf: leaf.example)
        for before, after in zip(leaves, leaves[1:]):
            check(before.example != after.example, "sync_duplicate_or_colliding_key")

        def build(lo, hi):
            if lo == hi:
                return None
            if hi - lo == 1:
                return leaves[lo]
            split = _common(leaves[lo].example, leaves[hi - 1].example)
            low, high = lo, hi
            while low < high:
                mid = (low + high) // 2
                if _bit(leaves[mid].example, split):
                    high = mid
                else:
                    low = mid + 1
            return result._branch(split, build(lo, low), build(low, hi))

        return result._copy(build(0, len(leaves)))


def native_root(binding, generation, tables):
    check(type(generation) is int and 0 <= generation < 2**64, "sync_generation")
    summary = [[name, table.root.hex(), len(table)] for name, table in sorted(tables.items())]
    return digest(b"mesh-sync-native\0" + framed(canonical(binding)) + generation.to_bytes(8, "big") +
                  framed(canonical(summary)))


def source_root(binding, native):
    check(type(native) is bytes and len(native) == 32, "sync_native_root")
    return digest(b"mesh-sync-source\0" + framed(canonical(binding)) + native)


def binding_digest(binding, *, native):
    tag = b"mesh-sync-native-binding\0" if native else b"mesh-sync-source-binding\0"
    return digest(tag + framed(canonical(binding)))


def body_digest(descriptor_digest, content):
    check(type(descriptor_digest) is bytes and len(descriptor_digest) == 32, "sync_descriptor_digest")
    return digest(b"mesh-sync-body\0" + framed(descriptor_digest) + framed(canonical(content)))


def field_digest(descriptor_digest, identity, birth, name, value):
    check(type(descriptor_digest) is bytes and len(descriptor_digest) == 32, "sync_descriptor_digest")
    check(type(name) is str, "sync_field_name")
    return digest(b"mesh-sync-field\0" + framed(descriptor_digest) + framed(canonical(identity)) +
                  framed(canonical(birth)) + framed(name.encode()) + framed(canonical(value)))
