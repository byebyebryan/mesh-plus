import math
import random
import unittest

from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import canonical
from mesh_plus.sync.commitment import ABSENT
from mesh_plus.sync.ordered import OrderedMap, index_key


class OrderedIndexTests(unittest.TestCase):
    def test_sparse_order_matches_sorted_oracle_and_prior_root_is_immutable(self):
        generator = random.Random(714)
        keys = list(range(2000))
        generator.shuffle(keys)
        tree = OrderedMap.baseline(([value // 100, value], {"value": value}) for value in keys)
        original = tree
        oracle = {(value // 100, value): value for value in keys}
        for step in range(200):
            value = generator.randrange(2000)
            key = [value // 100, value]
            if tuple(key) in oracle:
                tree = tree.remove(key)
                del oracle[tuple(key)]
            else:
                tree = tree.put(key, {"value": -step})
                oracle[tuple(key)] = -step
        self.assertEqual([index_key(tree.leaf_at(i)) for i in range(len(tree))],
                         [list(key) for key in sorted(oracle)])
        self.assertEqual(len(original), 2000)
        self.assertLessEqual(tree.node.height, 2 * math.ceil(math.log2(len(tree) + 1)))
        for key, value in oracle.items():
            self.assertEqual(tree.get(list(key))["value"], value)
        self.assertIs(tree.get([99, 9999]), ABSENT)
        start = tree.lower_bound([7])
        expected = [list(key) for key in sorted(oracle) if key[0] == 7]
        self.assertEqual([index_key(tree.leaf_at(start + i)) for i in range(len(expected))], expected)

    def test_unique_allocation_reclamation_and_sparse_path_bound(self):
        tree = OrderedMap.baseline(([i], i) for i in range(2000))
        ledger = AllocationLedger()
        ledger.retain(tree)
        visited = ledger.visited
        changed = tree.put([1000], -1)
        ledger.retain(changed)
        self.assertLess(ledger.visited - visited, 100)
        ledger.release(tree)
        self.assertEqual(changed.get([1000]), -1)
        ledger.release(changed)
        self.assertEqual(ledger.used, 0)
        self.assertEqual(ledger.encoded, 0)

    def test_total_json_order_and_duplicate_key_rejection(self):
        values = [{"a": 1}, [2], [1, "x"], [1], "a", 2, 1, True, False, None]
        tree = OrderedMap.baseline((key, 0) for key in values)
        expected = [None, False, True, 1, 2, "a", [1], [1, "x"], [2], {"a": 1}]
        self.assertEqual([canonical(index_key(tree.leaf_at(i))) for i in range(len(tree))],
                         [canonical(key) for key in expected])
        with self.assertRaisesRegex(ValueError, "sync_duplicate_key"):
            OrderedMap.baseline([([1], "first"), ([1], "second")])


if __name__ == "__main__":
    unittest.main()
