import itertools
import json
import random
import unittest
from dataclasses import FrozenInstanceError
from hashlib import sha256

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import Atom, canonical, decode, thaw
from mesh_plus.sync.commitment import ABSENT, MerkleMap, Work, native_root, source_root


def oracle(space, pairs):
    """Independent full-tree arithmetic oracle, never the incremental path."""
    def h(value):
        return sha256(value).digest()

    def f(value):
        return len(value).to_bytes(8, "big") + value

    def c(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()

    s = f(space.encode())
    entries = [(h(b"mesh-sync-key\0" + s + f(c(key))), key, value) for key, value in pairs]

    def build(rows):
        if not rows:
            return h(b"mesh-sync-empty\0" + s)
        if len(rows) == 1:
            kh, key, value = rows[0]
            vh = h(b"mesh-sync-value\0" + s + f(c(value)))
            return h(b"mesh-sync-leaf\0" + s + kh + f(c(key)) + vh)
        bits = [format(int.from_bytes(row[0], "big"), "0256b") for row in rows]
        p = next(i for i in range(256) if len({b[i] for b in bits}) > 1)
        prefix = bytearray(rows[0][0][:(p + 7) // 8])
        if p % 8:
            prefix[-1] &= 255 << (8 - p % 8) & 255
        left = [row for row, bits in zip(rows, bits) if bits[p] == "0"]
        right = [row for row, bits in zip(rows, bits) if bits[p] == "1"]
        return h(b"mesh-sync-branch\0" + s + p.to_bytes(2, "big") + f(bytes(prefix)) + build(left) + build(right))

    return build(entries)


class CanonicalTests(unittest.TestCase):
    def test_exact_unicode_and_optional_null_fixture(self):
        self.assertEqual(canonical({"z": None, "é": "é\n", "a": True}).hex(),
                         "7b2261223a747275652c227a223a6e756c6c2c22c3a9223a22c3a95c6e227d")
        self.assertNotEqual(canonical({}), canonical({"x": None}))
        self.assertNotEqual(canonical(True), canonical(1))

    def test_noncanonical_types_and_ambiguous_input_rejected(self):
        for value in (1.0, float("nan"), {1: "x"}, b"x", "\ud800", (1, 2)):
            with self.subTest(value=repr(value)), self.assertRaises(ProtocolError):
                canonical(value)
        for raw in (b'{"a":1,"a":2}', b"-0", b"1.0", b"NaN", b'"\\ud800"', b"\xef\xbb\xbf{}"):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                decode(raw)

    def test_mutable_inputs_and_detached_output_cannot_change_owned_atom(self):
        original = {"nested": [{"value": "old"}], "null": None}
        atom = Atom.own(original)
        original["nested"][0]["value"] = "corrupt"
        output = thaw(atom.value)
        output["nested"].append("caller")
        self.assertEqual(atom.encoded, b'{"nested":[{"value":"old"}],"null":null}')
        self.assertEqual(thaw(atom.value), {"nested": [{"value": "old"}], "null": None})
        with self.assertRaises((AttributeError, FrozenInstanceError)):
            atom.encoded = b"forged"


class CommitmentTests(unittest.TestCase):
    def test_accepted_arithmetic_vectors_and_wrapper(self):
        empty = MerkleMap("records")
        a = empty.put("a", {"body": "A"})
        b = empty.put("b", {"body": "B"})
        ab = a.put("b", {"body": "B"})
        expected = {
            empty.root: "eeb50b54d1d8075c3a13e3c3d8fbe7c51995bad9129f80e4de7e1b6ce3d6c587",
            a.root: "e6656cee7d68057ea405fe79d91dfca8d73242361a402ce86c7ec8df3fb895ac",
            b.root: "ba716d28870d9878937cb24f5b2f1bf6a946c1f01018b87eb7fcfad4b70588b3",
            ab.root: "d9d6043d34003e0962032d529fd5ee197a02fe7818b7e91f01563826c914034f",
            ab.put("a", {"body": "A2"}).root: "60c4c18888def3635a595751bf82e9160a019f4a7ce19a620a5c2b5f60f40419",
        }
        for actual, wanted in expected.items():
            self.assertEqual(actual.hex(), wanted)
        self.assertEqual(ab.remove("b").root, a.root)
        self.assertEqual(b.put("a", {"body": "A"}).root, ab.root)
        ac = a.put("c", {"body": "C"})
        self.assertEqual(ac.node.split, 2)
        self.assertEqual(ac.node.prefix, b"\xc0")
        self.assertEqual(ac.root.hex(), "28143b1ae65c68223f645cb7d988eb6b1e79fba5d9e9705055a3908e190ff560")
        binding = {"contract": "fixture", "host": "h", "owner": "o", "view": "full"}
        nr = native_root(binding, 2, {"records": ab})
        self.assertEqual(nr.hex(), "5b7ca726bb1e93e425752f9d2c742c80131b1fab11fb57f8940c815b84f3eb0f")
        self.assertEqual(source_root({"host": "h", "profile": "proposal", "source": "s"}, nr).hex(),
                         "8ad9669a41a79d9df2d397a1233418ac739bd5d8d8a3b83ae1393e68b863882a")
        self.assertNotEqual(source_root({"source": "s2"}, nr), source_root({"source": "s"}, nr))
        self.assertNotEqual(nr, native_root({**binding, "owner": "o2"}, 2, {"records": ab}))

    def test_all_insertion_permutations_and_full_bulk_oracle_match(self):
        pairs = [(key, {"value": key}) for key in "abcdef"]
        expected = oracle("records", pairs)
        for permutation in itertools.permutations(pairs):
            tree = MerkleMap("records")
            for key, value in permutation:
                tree = tree.put(key, value)
            self.assertEqual(tree.root, expected)
        self.assertEqual(MerkleMap.baseline("records", pairs).root, expected)

    def test_random_replace_remove_and_retained_roots_match_independent_oracle(self):
        rng = random.Random(284)
        model = {str(i): [i, None] for i in range(80)}
        tree = MerkleMap.baseline("records", model.items())
        retained = []
        for step in range(150):
            retained.append((tree, tree.root))
            key = str(rng.randrange(100))
            if key in model and rng.randrange(3) == 0:
                tree = tree.remove(key)
                del model[key]
            else:
                model[key] = [step, True]
                tree = tree.put(key, model[key])
            self.assertEqual(tree.root, oracle("records", list(model.items())))
            self.assertEqual(len(tree), len(model))
        for root, expected in retained:
            self.assertEqual(root.root, expected)

    def test_wrong_old_token_duplicate_and_rebirth_are_rejected_or_isolated(self):
        tree = MerkleMap("memberships").put(["c0", "id", ["owner", 1], "runtime"], "11" * 32)
        root = tree.root
        with self.assertRaises(ProtocolError):
            tree.put(["c0", "id", ["owner", 1], "runtime"], "22" * 32, expected=ABSENT)
        with self.assertRaises(ProtocolError):
            tree.remove(["c0", "id", ["owner", 2], "runtime"])
        self.assertEqual(tree.root, root)
        with self.assertRaises(ProtocolError):
            MerkleMap.baseline("memberships", [("same", 1), ("same", 2)])

    def test_one_binding_edit_has_no_unchanged_member_enumeration(self):
        for count in (100, 500, 2000):
            work = Work()
            entries = [(["c0", str(i), ["owner", 1], "runtime"], "11" * 32) for i in range(count)]
            tree = MerkleMap.baseline("memberships", entries, work=work)
            before = work.snapshot()
            changed = tree.put(entries[count // 2][0], "22" * 32)
            self.assertNotEqual(changed.root, tree.root)
            self.assertEqual(work.iterated_entries - before["iterated_entries"], 0)
            self.assertEqual(work.value_hashes - before["value_hashes"], 1)
            self.assertLessEqual(work.node_reads - before["node_reads"], 257)
            self.assertLessEqual(work.branch_hashes - before["branch_hashes"], 256)
            self.assertEqual(changed.node.count, count)


class AllocationTests(unittest.TestCase):
    def test_dense_nine_field_memberships_share_atoms_within_default_cap(self):
        fields = ("runtime", "phase", "kind", "savedIdentity", "activity", "outcome",
                  "workspace", "lastUpdated", "latestTurn")
        entries = [(["c0", ["h", "codex", "ns", "thread", str(i)], ["owner", 1], field],
                    Atom.own("11" * 32)) for i in range(2000) for field in fields]
        members = MerkleMap.baseline_atoms("memberships", entries)
        grouped = MerkleMap.baseline_atoms("cohort-members", [(key[1:], atom) for key, atom in entries])
        ledger = AllocationLedger()
        roots = (members, grouped)
        ledger.retain(roots)
        self.assertLess(ledger.used, 64 * 1024 * 1024)
        self.assertEqual(len(members), 18000)
        ledger.release(roots)
        self.assertEqual(ledger.used, 0)

    def test_sparse_paths_are_shared_accounted_and_reclaimed_without_full_walk(self):
        tree = MerkleMap.baseline("records", [(str(i), {"value": i}) for i in range(2000)])
        ledger = AllocationLedger()
        ledger.retain(tree)
        visited = ledger.visited
        updated = tree.put("1000", {"value": "new"})
        ledger.retain(updated)
        self.assertLess(ledger.visited - visited, 600)
        ledger.release(tree)
        self.assertGreater(ledger.used, 0)
        ledger.release(updated)
        self.assertEqual(ledger.inspect()["decodedBytes"], 0)
        self.assertEqual(len(ledger.entries), 0)

    def test_failed_capacity_admission_and_reservations_publish_nothing(self):
        ledger = AllocationLedger(1024)
        with ledger.reserve(100) as reservation:
            with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                ledger.retain(MerkleMap("records").put("id", {"body": "large" * 100}),
                              reservation=reservation)
            self.assertEqual(ledger.used, 0)
            self.assertEqual(len(ledger.entries), 0)
        self.assertEqual(ledger.reserved, 0)
        encoded = AllocationLedger(encoded_maximum=8)
        with self.assertRaisesRegex(ProtocolError, "sync_encoded_capacity"):
            encoded.retain(MerkleMap("records").put("id", "body"))
        self.assertEqual(len(encoded.entries), 0)

    def test_current_predecessor_reclamation_plateaus(self):
        ledger = AllocationLedger()
        current = MerkleMap.baseline("records", [(str(i), i) for i in range(500)])
        ledger.retain(current)
        baseline = ledger.used
        previous = None
        for i in range(100):
            new = current.put(str(i), {"changed": i})
            ledger.retain(new)
            if previous is not None:
                ledger.release(previous)
            previous, current = current, new
            self.assertLess(ledger.used, baseline * 2)
        ledger.release(previous)
        ledger.release(current)
        self.assertEqual(ledger.used, 0)
        self.assertEqual(ledger.encoded, 0)


if __name__ == "__main__":
    unittest.main()
