import unittest
from unittest.mock import patch

from mesh_plus.protocol import ProtocolError
from mesh_plus.sync._schema import OwnedSchema
from mesh_plus.sync.budget import AllocationLedger
from mesh_plus.sync.canonical import Atom, canonical, packed, thaw
from mesh_plus.sync.commitment import MerkleMap
from mesh_plus.sync.decoder import DecoderArena


class PackedValueTests(unittest.TestCase):
    def test_index_schema_owns_its_tree_and_prepays_validation_before_compilation(self):
        ledger = AllocationLedger(4 * 1024 * 1024)
        schema = OwnedSchema.retain(canonical({"$defs": {"value": {"type": "integer"}},
                                               "$ref": "#/$defs/value"}), ledger)
        try:
            schema.validate(Atom.own(1), ledger)
            with self.assertRaisesRegex(Exception, "not of type"):
                schema.validate(Atom.own("wrong"), ledger)
            self.assertEqual(ledger.reserved, 0)
            with ledger.reserve(ledger.maximum - ledger.used - 4096):
                with patch("mesh_plus.sync._schema.Draft202012Validator", side_effect=AssertionError("unfunded compiler")):
                    with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                        schema.validate(Atom.own(1), ledger)
        finally:
            ledger.release(schema)
        self.assertEqual((ledger.used, ledger.reserved), (0, 0))

    def test_unfunded_staging_is_rejected_before_copy_or_encoding(self):
        ledger = AllocationLedger(4096)
        from mesh_plus.sync.canonical import PackedAtom
        with ledger.allocations():
            with patch("mesh_plus.sync.canonical._freeze", side_effect=AssertionError("unfunded copy")):
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                    Atom.own({"body": "x" * 16384})
            with patch("mesh_plus.sync.canonical.json.dumps", side_effect=AssertionError("unfunded encoding")):
                with self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                    PackedAtom._from_private_json({"body": "x" * 16384})
        self.assertEqual((ledger.used, ledger.reserved, ledger.pending_units), (0, 0, 0))

    def test_provisional_decoder_borrow_does_not_uncharge_a_live_staged_atom(self):
        ledger = AllocationLedger()
        arena = DecoderArena(ledger)
        try:
            with ledger.allocations():
                value = packed(Atom.own({"body": "x" * 2048}))
                amount = ledger.reserved
                self.assertEqual(ledger.pending_units, 1)
                with arena.active():
                    self.assertEqual(value.value["body"], "x" * 2048)
                arena.clear()
                self.assertEqual(ledger.reserved, amount)
                self.assertEqual(ledger.pending_units, 1)
                value = None
                self.assertEqual(ledger.pending_units, 0)
        finally:
            arena.close()
        self.assertEqual((ledger.used, ledger.reserved), (0, 0))

    def test_packing_preserves_every_commitment_and_detaches_input(self):
        values = [["id", {"value": [1, 2, {"text": "snow 雪"}], "health": "current"}],
                  ["other", "ab" * 32]]
        plain = MerkleMap.baseline("bodies", values)
        compact = MerkleMap.baseline_atoms("bodies", ((key, packed(Atom.own(value))) for key, value in values))
        self.assertEqual(plain.root, compact.root)
        values[0][1]["value"][2]["text"] = "mutated"
        ledger = AllocationLedger()
        arena = DecoderArena(ledger)
        ledger.retain(compact)
        try:
            with arena.active():
                first = compact.get("id")
                second = compact.get("id")
                self.assertIs(first, second)
                self.assertEqual(first["value"][2]["text"], "snow 雪")
                self.assertEqual(canonical(thaw(first)), plain.find("id").atom.encoded)
            self.assertEqual(arena.decodes, 1)
        finally:
            arena.close()
            ledger.release(compact)
        self.assertEqual(ledger.used, 0)

    def test_arena_is_bounded_and_releases_old_values(self):
        values = [(str(i), {"body": str(i) * 1024}) for i in range(100)]
        tree = MerkleMap.baseline_atoms("bodies", ((key, packed(Atom.own(value))) for key, value in values))
        ledger = AllocationLedger()
        arena = DecoderArena(ledger, maximum=4)
        ledger.retain(tree)
        baseline = ledger.used
        try:
            with arena.active():
                for i in range(100):
                    self.assertEqual(tree.get(str(i))["body"], str(i) * 1024)
                    self.assertLessEqual(len(arena.entries), 4)
            self.assertLess(ledger.used, baseline + 64 * 1024)
            arena.clear()
            self.assertEqual(ledger.used, baseline)
        finally:
            arena.close()
            ledger.release(tree)
        self.assertEqual(ledger.used, 0)

    def test_failed_decode_quota_does_not_retain_a_partial_entry(self):
        value = packed(Atom.own({"body": "x" * 16384}))
        ledger = AllocationLedger(32 * 1024)
        arena = DecoderArena(ledger, maximum=1)
        baseline = ledger.used
        try:
            with arena.active(), self.assertRaisesRegex(ProtocolError, "sync_decoded_capacity"):
                value.value
            self.assertEqual(ledger.used, baseline)
            self.assertEqual(ledger.reserved, 0)
            self.assertEqual(len(arena.entries), 0)
        finally:
            arena.close()
        self.assertEqual(ledger.used, 0)


if __name__ == "__main__":
    unittest.main()
