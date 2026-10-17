"""Private G1 paged-node prototype; no packaged factory enables this backend.

Numeric metadata lives in fixed arrays; canonical key/value bytes and digest
planes retain their encoded charge. Empty page capacity is never free credit.
Each occupied branch owns its two actual edges, independent of page lifetime.
"""

import sys
import weakref
import zlib
from array import array

from ..protocol import check
from ._allocation import ACTIVE_LEDGER, TrackedAllocation, finish, prepay
from .budget import OwnedUnit
from .canonical import Atom, InputKey, PackedAtom, _key_copy_budget, decode
from .commitment import ABSENT, Branch, Leaf, MerkleMap, Work, _bit, _common, digest, digest_parts, framed

_SLOTS = 256
_MAX = 2**32 - 1
_SLOT_CONTROL, _VIEW_CONTROL = 256, 1024


def _refund(credit, heap, encoded=0):
    check(not credit.closed and 0 <= heap <= credit.amount and
          0 <= encoded <= credit.encoded_amount, "sync_packed_credit")
    credit.amount -= heap
    credit.encoded_amount -= encoded
    credit.ledger.reserved -= heap
    credit.ledger.encoded_reserved -= encoded


class _Page:
    def __init__(self, arena, number, leaf):
        width = 64 if leaf else 32
        # Full fixed arrays/lists, their unused slots, array headers, page
        # object/dict, both credits and registry entry are prepaid first.
        heap = 4096 + _SLOTS * (width + (36 if leaf else 40))
        credit = arena.ledger.reserve(heap, encoded=width * _SLOTS + 1)
        payload = None
        try:
            payload = arena.ledger.reserve(0)
            self.number, self.leaf, self.width = number, leaf, width
            self.data = bytearray(width * _SLOTS)
            self.generations, self.refs = array("I", [0]) * _SLOTS, array("I", [0]) * _SLOTS
            self.keys, self.atoms = ([None] * _SLOTS, [None] * _SLOTS) if leaf else (None, None)
            self.key_sizes = array("i", [0]) * _SLOTS if leaf else None
            self.left, self.right, self.examples = ((None, None, None) if leaf else
                                                  tuple(array("Q", [0]) * _SLOTS for _ in range(3)))
            self.counts = None if leaf else array("I", [0]) * _SLOTS
            self.splits = None if leaf else array("H", [0]) * _SLOTS
            self.free, self.live = list(range(_SLOTS - 1, -1, -1)), 0
            self.credit, self.payload = credit, payload
            physical = sys.getsizeof(self) + sys.getsizeof(self.__dict__)
            physical += sum(sys.getsizeof(value) for value in (
                self.data, self.generations, self.refs, self.keys, self.atoms, self.left,
                self.right, self.examples, self.counts, self.splits, self.free, self.key_sizes))
            check(physical + 1024 <= heap, "sync_packed_page_estimate")
        except BaseException:
            # A retained exception must not keep physical page storage after
            # its reservation has been returned. Partial construction is safe
            # because these are fresh, edge-free slots.
            for name in ("data", "generations", "refs", "keys", "atoms", "key_sizes",
                         "left", "right", "examples", "counts", "splits", "free"):
                if hasattr(self, name):
                    setattr(self, name, None)
            if payload is not None:
                payload.close()
            credit.close()
            raise

    def retire(self):
        check(self.live == 0 and self.payload.amount == 0 and self.payload.encoded_amount == 0,
              "sync_packed_live_page")
        self.data = self.keys = self.atoms = self.left = self.right = self.examples = None
        self.generations = self.refs = self.counts = self.splits = self.free = None
        self.key_sizes = None
        self.payload.close()
        self.credit.close()


class PackedNodeArena:
    """Explicit private opt-in on one ledger, with exact epoch/generation handles."""

    def __init__(self, ledger):
        prior = getattr(ledger, "_packed_nodes", None)
        check(prior is None or prior() is None, "sync_packed_arena_exists")
        self._closed = True
        base = ledger.reserve(262144, encoded=65536)
        registry = loans = codecs = None
        try:
            registry, loans = ledger.reserve(4096), ledger.reserve(0)
            codecs = ledger.reserve(0)
            self.ledger, self._base, self._registry, self._loans = ledger, base, registry, loans
            self._epoch, self._pages = object(), {}
            self._key_codecs, self._codec_credit = {}, codecs
            self._available = {True: set(), False: set()}
            self._next_page, self._high_pages = 1, 0
            self._maps = self._controls = self.live_nodes = 0
            self.allocated_nodes = self.released_nodes = 0
            self.record_reads = 0
            self._closed = False
            ledger._packed_nodes = weakref.ref(self)
        except BaseException:
            if codecs is not None:
                codecs.close()
            if loans is not None:
                loans.close()
            if registry is not None:
                registry.close()
            base.close()
            raise

    @property
    def map_type(self):
        self._check()
        return _PackedMap

    def _check(self):
        check(not self._closed, "sync_packed_retired")

    def _record(self, handle, epoch=None):
        self._check()
        self.record_reads += 1
        check(epoch is None or epoch is self._epoch, "sync_packed_epoch")
        check(type(handle) is int and 0 < handle < 2**64, "sync_packed_handle")
        slot, generation = handle & _MAX, handle >> 32
        page = self._pages.get(slot // _SLOTS)
        index = slot % _SLOTS
        check(page is not None and page.refs[index] > 0 and page.generations[index] == generation,
              "sync_packed_handle")
        return page, index

    def _increment(self, handle):
        page, index = self._record(handle)
        check(page.refs[index] < _MAX, "sync_packed_references")
        page.refs[index] += 1

    def _allocate(self, leaf):
        self._check()
        if not self._available[leaf]:
            check(self._next_page * _SLOTS <= _MAX - _SLOTS, "sync_packed_handle_exhausted")
            if len(self._pages) >= self._high_pages:
                self._registry.grow(2048)
                self._high_pages = len(self._pages) + 1
            number = self._next_page
            page = _Page(self, number, leaf)
            try:
                self._pages[number] = page
                self._available[leaf].add(number)
            except BaseException:
                self._pages.pop(number, None)
                self._available[leaf].discard(number)
                page.retire()
                raise
            self._next_page += 1
        number = next(iter(self._available[leaf]))
        page = self._pages[number]
        index = page.free[-1]
        check(page.generations[index] < _MAX, "sync_packed_handle_exhausted")
        page.free.pop()
        page.generations[index] += 1
        page.refs[index] = 1
        page.live += 1
        if not page.free:
            self._available[leaf].discard(number)
        self.live_nodes += 1
        self.allocated_nodes += 1
        return (int(page.generations[index]) << 32) | (number * _SLOTS + index)

    def _drop(self, handle):
        # At most one sibling per Patricia level. The arena base prepays this
        # bounded stack and cleanup cannot need fresh capacity at a full cap.
        pending = [handle]
        while pending:
            current = pending.pop()
            page, index = self._record(current)
            page.refs[index] -= 1
            if page.refs[index]:
                continue
            if page.leaf:
                key, atom = page.keys[index], page.atoms[index]
                page.keys[index] = page.atoms[index] = None
                page.key_sizes[index] = 0
                self.ledger._release_atom_edge(atom)
                amount, encoded = sys.getsizeof(key), len(key)
                key = atom = None
                _refund(page.payload, amount, encoded)
            else:
                pending.extend((int(page.left[index]), int(page.right[index])))
                page.left[index] = page.right[index] = page.examples[index] = 0
                page.counts[index] = page.splits[index] = 0
            page.live -= 1
            page.free.append(index)
            self._available[page.leaf].add(page.number)
            self.live_nodes -= 1
            self.released_nodes += 1
            if page.live == 0:
                self._available[page.leaf].discard(page.number)
                del self._pages[page.number]
                page.retire()

    def _example_handle(self, handle):
        page, index = self._record(handle)
        return handle if page.leaf else int(page.examples[index])

    def _example(self, handle):
        page, index = self._record(self._example_handle(handle))
        return bytes(page.data[index * 64:index * 64 + 32])

    def _root(self, handle):
        page, index = self._record(handle)
        start = index * page.width + (32 if page.leaf else 0)
        return bytes(page.data[start:start + 32])

    def _count(self, handle):
        page, index = self._record(handle)
        return 1 if page.leaf else int(page.counts[index])

    def _key_storage(self, space, key):
        check(len(key) <= 16384, "sync_packed_key_capacity")
        if len(key) < 96 or space == framed(b"records"):
            return key, len(key)
        dictionary = self._key_codecs.get(space)
        if dictionary is None:
            check(len(self._key_codecs) < 64, "sync_packed_spaces")
            size = min(1024, len(key))
            self._codec_credit.grow(512 + sys.getsizeof(space) + sys.getsizeof(b"") + size,
                                    encoded=len(space) + size)
            dictionary = memoryview(key)[-size:].tobytes()
            self._key_codecs[space] = dictionary
        # A 1 KiB window and minimum memLevel bound C working storage, prepaid
        # with the arena's simultaneous input/output and codec scratch.
        encoder = zlib.compressobj(1, zlib.DEFLATED, -10, 1, zdict=dictionary)
        stored = encoder.compress(key) + encoder.flush()
        return (stored, -len(key)) if len(stored) < len(key) else (key, len(key))

    def _leaf(self, key, raw_size, hashed, atom, root):
        handle = self._allocate(True)
        page, index = self._record(handle)
        credit = held = False
        try:
            page.payload.grow(sys.getsizeof(key), encoded=len(key))
            credit = True
            self.ledger._retain_atom_edge(atom)
            held = True
            start = index * 64
            page.data[start:start + 32] = hashed
            page.data[start + 32:start + 64] = root
            page.keys[index], page.atoms[index] = key, atom
            page.key_sizes[index] = raw_size
            return handle
        except BaseException:
            if held:
                self.ledger._release_atom_edge(atom)
            if credit:
                _refund(page.payload, sys.getsizeof(key), len(key))
            self._abandon(handle)
            raise

    def _abandon(self, handle):
        """An allocated slot whose edges/payload have not committed."""
        page, index = self._record(handle)
        page.refs[index] = 0
        page.live -= 1
        page.free.append(index)
        self._available[page.leaf].add(page.number)
        self.live_nodes -= 1
        self.released_nodes += 1
        if page.live == 0:
            self._available[page.leaf].discard(page.number)
            del self._pages[page.number]
            page.retire()

    def _branch(self, split, left, right, root):
        check(left != right, "sync_packed_edges")
        self._record(left)
        self._record(right)
        count = self._count(left) + self._count(right)
        check(count <= _MAX, "sync_packed_count")
        handle, held = self._allocate(False), []
        try:
            for child in (left, right):
                self._increment(child)
                held.append(child)
            page, index = self._record(handle)
            page.left[index], page.right[index] = left, right
            page.examples[index] = self._example_handle(left)
            page.counts[index], page.splits[index] = count, split
            page.data[index * 32:index * 32 + 32] = root
            return handle
        except BaseException:
            for child in held:
                self._drop(child)
            self._abandon(handle)
            raise

    def _control(self, amount):
        self._check()
        self._loans.grow(amount)
        self._controls += 1

    def _uncontrol(self, amount):
        self._controls -= 1
        _refund(self._loans, amount)

    def _slot(self, handle):
        controlled = False
        try:
            self._control(_SLOT_CONTROL)
            controlled = True
            return _Slot(self, handle)
        except BaseException:
            if controlled:
                self._uncontrol(_SLOT_CONTROL)
            self._drop(handle)
            raise

    def _view(self, handle, space, work):
        page, _ = self._record(handle)
        self._control(_VIEW_CONTROL)
        incremented = False
        try:
            self._increment(handle)
            incremented = True
            result = object.__new__(_LeafView if page.leaf else _BranchView)
            for name, value in (("_arena", self), ("_handle", handle), ("_epoch", self._epoch),
                                ("_space", space), ("_work", work), ("_control_owner", self),
                                ("_decoded_key", None), ("_key_heap", 0), ("_key_encoded", 0)):
                object.__setattr__(result, name, value)
            return result
        except BaseException:
            if incremented:
                self._drop(handle)
            self._uncontrol(_VIEW_CONTROL)
            raise

    def inspect(self):
        return {"pages": len(self._pages), "nodes": self.live_nodes, "maps": self._maps,
                "controls": self._controls, "allocatedNodes": self.allocated_nodes,
                "releasedNodes": self.released_nodes,
                "fixedHeapCredit": sum(page.credit.amount for page in self._pages.values()),
                "digestPlaneCredit": sum(page.credit.encoded_amount for page in self._pages.values()),
                "keyHeapCredit": sum(page.payload.amount for page in self._pages.values()),
                "keyEncodedCredit": sum(page.payload.encoded_amount for page in self._pages.values()),
                "registryCredit": self._registry.amount, "loanCredit": self._loans.amount,
                "keyDictionaryCredit": self._codec_credit.amount,
                "keyDictionaryEncodedCredit": self._codec_credit.encoded_amount,
                "recordReads": self.record_reads}

    def close(self):
        if self._closed:
            return
        check(self.live_nodes == self._maps == self._controls == 0, "sync_packed_in_use")
        check(not self._pages, "sync_packed_live_page")
        self._closed = True
        selected = getattr(self.ledger, "_packed_nodes", None)
        if selected is not None and selected() is self:
            del self.ledger._packed_nodes
        self._available.clear()
        self._pages.clear()
        self._key_codecs.clear()
        self._codec_credit.close()
        self._loans.close()
        self._registry.close()
        self._base.close()


class _Slot:
    __slots__ = ("_arena", "_handle", "_epoch", "_control_owner")

    def __init__(self, arena, handle):
        self._arena, self._handle, self._epoch, self._control_owner = arena, handle, arena._epoch, arena

    def _check(self):
        check(self._arena is not None, "sync_packed_retired")
        return self._arena._record(self._handle, self._epoch)

    @property
    def example(self):
        self._check()
        return self._arena._example(self._handle)

    @property
    def root(self):
        self._check()
        return self._arena._root(self._handle)

    @property
    def count(self):
        self._check()
        return self._arena._count(self._handle)

    def close(self):
        arena, self._arena = self._arena, None
        if arena is not None:
            arena._drop(self._handle)

    def __del__(self):
        if hasattr(self, "_arena"):
            self.close()
            self._control_owner._uncontrol(_SLOT_CONTROL)


class _View:
    __slots__ = ()

    def _record(self):
        check(self._arena is not None, "sync_packed_retired")
        return self._arena._record(self._handle, self._epoch)

    @property
    def example(self):
        self._record()
        return self._arena._example(self._handle)

    @property
    def root(self):
        self._record()
        return self._arena._root(self._handle)

    @property
    def count(self):
        self._record()
        return self._arena._count(self._handle)

    def close(self):
        arena = getattr(self, "_arena", None)
        if arena is not None:
            heap, encoded = self._key_heap, self._key_encoded
            object.__setattr__(self, "_decoded_key", None)
            object.__setattr__(self, "_key_heap", 0)
            object.__setattr__(self, "_key_encoded", 0)
            if heap:
                _refund(arena._loans, heap, encoded)
            object.__setattr__(self, "_arena", None)
            arena._drop(self._handle)

    def __del__(self):
        if hasattr(self, "_control_owner"):
            self.close()
            self._control_owner._uncontrol(_VIEW_CONTROL)


_VIEW_SLOTS = ("_arena", "_handle", "_epoch", "_space", "_work", "_control_owner",
               "_decoded_key", "_key_heap", "_key_encoded")


class _LeafView(_View, Leaf):
    __slots__ = _VIEW_SLOTS

    @property
    def key(self):
        page, index = self._record()
        size = int(page.key_sizes[index])
        if size >= 0:
            return page.keys[index]
        if self._decoded_key is None:
            size = -size
            heap = sys.getsizeof(b"") + size
            self._arena._loans.grow(heap, encoded=size)
            try:
                decoder = zlib.decompressobj(-10, zdict=self._arena._key_codecs[self._space])
                raw = decoder.decompress(page.keys[index], size + 1)
                check(len(raw) == size and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail,
                      "sync_packed_key")
                object.__setattr__(self, "_decoded_key", raw)
                object.__setattr__(self, "_key_heap", heap)
                object.__setattr__(self, "_key_encoded", size)
            except BaseException:
                _refund(self._arena._loans, heap, size)
                raise
        return self._decoded_key

    def input_key(self):
        page, index = self._record()
        if page.key_sizes[index] >= 0:
            return InputKey.borrow(self.key)
        # Decompressed bytes are not page-backed. Prepay a separate immutable
        # copy so a normalized key outliving this loan retains its own credit.
        raw = self.key
        credit = prepay(4096 + sys.getsizeof(raw), len(raw))
        try:
            owned = memoryview(raw).tobytes()
            return finish(PackedAtom(owned, _key_copy_budget(owned)), credit)
        finally:
            if credit is not None:
                credit.close()

    @property
    def atom(self):
        page, index = self._record()
        return page.atoms[index]

    @property
    def value_hash(self):
        self._work.value_hashes += 1
        encoded = self.atom.encoded
        return digest_parts(b"mesh-sync-value\0", self._space, len(encoded).to_bytes(8, "big"), encoded)


class _BranchView(_View, Branch):
    __slots__ = _VIEW_SLOTS

    @property
    def split(self):
        page, index = self._record()
        return int(page.splits[index])

    @property
    def prefix(self):
        split = self.split
        prefix = bytearray(self.example[:(split + 7) // 8])
        if split % 8:
            prefix[-1] &= (255 << (8 - split % 8)) & 255
        return bytes(prefix)

    @property
    def left(self):
        page, index = self._record()
        return self._arena._view(int(page.left[index]), self._space, self._work)

    @property
    def right(self):
        page, index = self._record()
        return self._arena._view(int(page.right[index]), self._space, self._work)


class _PackedMap(MerkleMap, OwnedUnit):
    __slots__ = ("_arena",)

    def __init__(self, space, node=None, *, work=None, _arena=None):
        arena = _arena
        if arena is None:
            selected = getattr(ACTIVE_LEDGER.get(), "_packed_nodes", None)
            arena = None if selected is None else selected()
        check(arena is not None, "sync_packed_arena")
        arena._check()
        check(ACTIVE_LEDGER.get() is arena.ledger, "sync_packed_allocation_scope")
        check(type(space) is str and 0 < len(space.encode()) <= 128, "sync_space")
        credit = prepay(4096, 256)
        self._arena = arena
        try:
            self.space, self.work = space, Work() if work is None else work
            self._framed_space = framed(space.encode())
            self._empty = digest(b"mesh-sync-empty\0" + self._framed_space)
            if isinstance(node, _Slot):
                node._check()
                check(node._arena is arena, "sync_packed_epoch")
                self.node = arena._view(node._handle, self._framed_space, self.work)
                node.close()
            else:
                check(node is None or isinstance(node, (_LeafView, _BranchView)) and node._arena is arena,
                      "sync_packed_epoch")
                self.node = node
            arena._maps += 1
            finish(self, credit)
        finally:
            if credit is not None:
                credit.close()

    def owned_children(self):
        # Pages own actual node/value edges. Traversing logical child wrappers
        # here would double-charge and pin entire pages through dead siblings.
        return self.space, self.work

    def owned_intrinsic(self):
        return sys.getsizeof(self._framed_space) + sys.getsizeof(self._empty)

    def owned_encoded(self):
        return len(self._framed_space) + len(self._empty)

    def _copy(self, node):
        return _PackedMap(self.space, node, work=self.work, _arena=self._arena)

    def _find(self, encoded, hashed):
        handle = 0 if self.node is None else self.node._handle
        while handle:
            page, index = self._arena._record(handle)
            self.work.node_reads += 1
            if page.leaf:
                if self._arena._example(handle) != hashed:
                    return ABSENT
                leaf = self._arena._view(handle, self._framed_space, self.work)
                check(leaf.key == encoded, "sync_key_hash_collision")
                return leaf
            split = int(page.splits[index])
            if _common(self._arena._example(handle), hashed) < split:
                return ABSENT
            handle = int(page.right[index] if _bit(hashed, split) else page.left[index])
        return ABSENT

    def leaf_at(self, rank):
        check(type(rank) is int and 0 <= rank < len(self), "sync_entry_rank")
        handle = self.node._handle
        while True:
            page, index = self._arena._record(handle)
            self.work.node_reads += 1
            if page.leaf:
                self.work.iterated_entries += 1
                return self._arena._view(handle, self._framed_space, self.work)
            left = int(page.left[index])
            count = self._arena._count(left)
            if rank < count:
                handle = left
            else:
                rank -= count
                handle = int(page.right[index])

    def leaves(self):
        pending = [] if self.node is None else [self.node._handle]
        while pending:
            handle = pending.pop()
            page, index = self._arena._record(handle)
            self.work.node_reads += 1
            if page.leaf:
                self.work.iterated_entries += 1
                yield self._arena._view(handle, self._framed_space, self.work)
            else:
                pending.extend((int(page.right[index]), int(page.left[index])))

    def items(self):
        for leaf in self.leaves():
            yield decode(leaf.key), leaf.atom.value

    def _leaf(self, key, key_hash, atom):
        check(type(atom) in (Atom, PackedAtom), "sync_atom")
        self.work.value_hashes += 1
        value_hash = digest_parts(b"mesh-sync-value\0", self._framed_space,
                                  len(atom.encoded).to_bytes(8, "big"), atom.encoded)
        root = digest_parts(b"mesh-sync-leaf\0", self._framed_space, key_hash,
                            len(key).to_bytes(8, "big"), key, value_hash)
        self.work.node_writes += 1
        stored, size = self._arena._key_storage(self._framed_space, key)
        return self._arena._slot(self._arena._leaf(stored, size, key_hash, atom, root))

    def _branch(self, split, left, right):
        for child in (left, right):
            check(isinstance(child, (_Slot, _LeafView, _BranchView)) and child._arena is self._arena,
                  "sync_packed_epoch")
        prefix = bytearray(left.example[:(split + 7) // 8])
        if split % 8:
            prefix[-1] &= (255 << (8 - split % 8)) & 255
        prefix = bytes(prefix)
        root = digest_parts(b"mesh-sync-branch\0", self._framed_space, split.to_bytes(2, "big"),
                            len(prefix).to_bytes(8, "big"), prefix, left.root, right.root)
        self.work.branch_hashes += 1
        self.work.node_writes += 1
        return self._arena._slot(self._arena._branch(split, left._handle, right._handle, root))

    @classmethod
    def _baseline_owned(cls, space, entries, *, work=None, encoded_keys=False):
        # Keep the established bulk algorithm. _Slot controls are small,
        # separately prepaid loans, never one retained Python object per node.
        result = cls(space, work=work)
        leaves = []
        credit = result._arena.ledger.reserve(1024)
        try:
            for key, atom in entries:
                check(type(atom) in (Atom, PackedAtom), "sync_atom")
                if encoded_keys:
                    check(type(key) is bytes, "sync_owned_key")
                    encoded = key
                    result.work.key_hashes += 1
                    hashed = digest_parts(b"mesh-sync-key\0", result._framed_space,
                                          len(encoded).to_bytes(8, "big"), encoded)
                else:
                    encoded, hashed = result._key(key)
                if len(leaves) % 64 == 0:
                    credit.grow(24 * 64)
                leaves.append(result._leaf(encoded, hashed, atom))
            return result._baseline_leaves(leaves)
        finally:
            leaves.clear()
            credit.close()

    def __del__(self):
        if hasattr(self, "node"):
            object.__setattr__(self, "node", None)
            self._arena._maps -= 1
        TrackedAllocation.__del__(self)
