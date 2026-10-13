"""Independent golden comparisons and incompatible legacy behavior witnesses."""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from test_simplification import fleet  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepared import Prepared, PreparedGuard  # noqa: E402

from mesh_plus.api import ReadGuard, current_sessions  # noqa: E402
from mesh_plus.protocol import ProtocolError  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402


class OwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_golden_current_and_expiry_for_all_accepted_fixture_profiles(self):
        for domain, timing in (("tmux", False), ("agent", False), ("agent", True)):
            profile, _, response = await fleet(domain, hosts=4, rows=4, timing=timing)
            prepared = Prepared(response, profile)
            clock = response["mesh"]["reader"]["clock"]
            times = [boottime_ms()] + sorted({r["expiresAtMs"] for h in response["mesh"]["hosts"] for r in h["receipts"]})
            for now in times:
                self.assertEqual(prepared.current(now, clock), current_sessions(response, now, clock, profile=profile))
            self.assertEqual(prepared.snapshot(), response)
            prepared.invalidate()
            self.assertEqual(prepared.current(times[0], clock), [])

    async def test_input_export_and_row_mutation_cannot_change_sealed_rows(self):
        profile, _, response = await fleet()
        owned = copy.deepcopy(response)
        prepared = Prepared(response, profile)
        now, clock = boottime_ms(), owned["mesh"]["reader"]["clock"]
        expected = current_sessions(owned, now, clock, profile=profile)
        response["sessions"].clear()
        exported = prepared.snapshot()
        exported["sessions"][0]["name"] = "changed export"
        result = prepared.current(now, clock)
        result[0]["name"] = "changed result"
        self.assertEqual(prepared.current(now, clock), expected)
        self.assertEqual(prepared.snapshot(), owned)
        with self.assertRaises((AttributeError, TypeError)):
            prepared.rows = ()
        with self.assertRaises((AttributeError, TypeError)):
            prepared.rows[0].expiry += 100000

    async def test_clock_and_no_receipt_extension(self):
        profile, _, response = await fleet()
        prepared = Prepared(response, profile)
        clock = response["mesh"]["reader"]["clock"]
        with self.assertRaises(ProtocolError):
            prepared.current(boottime_ms(), {**clock, "bootId": "wrong"})
        with self.assertRaises(ProtocolError):
            prepared.current(prepared.encoded_at - 1, clock)
        expiry = max(row.expiry for row in prepared.rows)
        self.assertFalse(prepared.current(expiry, clock))
        self.assertFalse(prepared.current(expiry + 100000, clock))

    async def test_failed_admission_never_yields_a_prepared_value(self):
        profile, _, response = await fleet()
        for kind in ("proof", "receipt", "scope"):
            bad = copy.deepcopy(response)
            if kind == "proof":
                bad["mesh"]["hosts"][1]["delivery"]["proof"]["payloadDigest"] = "sha256:" + "0" * 64
            elif kind == "receipt":
                bad["mesh"]["hosts"][0]["receipts"][0]["accepted"] += 1
            else:
                bad["sessions"][0]["hostId"] = "foreign"
            with self.subTest(kind=kind), self.assertRaises(Exception):
                Prepared(bad, profile)

    async def test_legacy_mutable_guard_is_not_replaced_by_sealed_export(self):
        profile, _, response = await fleet()
        guard = ReadGuard("tmux", "a" * 32, profile=profile)
        guard.accept(response)
        prepared = Prepared(response, profile)
        guard.view["sessions"][0]["sessionId"] = "$forged"
        with self.assertRaises(Exception):
            guard.current(boottime_ms(), response["mesh"]["reader"]["clock"])
        self.assertEqual(len(prepared.current(boottime_ms(), response["mesh"]["reader"]["clock"])), 32)

    async def test_later_callback_rejection_witness_requires_explicit_opt_in(self):
        profile, _, response = await fleet()
        prepared = Prepared(response, profile)
        with patch.object(profile, "validate_response", side_effect=ProtocolError("later_owner_rejection")):
            with self.assertRaisesRegex(ProtocolError, "later_owner_rejection"):
                current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"], profile=profile)
            # Expected incompatibility, not successful runtime acceptance.
            self.assertEqual(len(prepared.current(boottime_ms(), response["mesh"]["reader"]["clock"])), 32)

    async def test_gap_resync_heartbeat_and_disconnect_keep_original_leases(self):
        profile, _, response = await fleet()
        candidate = PreparedGuard("tmux", "a" * 32, profile)
        candidate.accept(response)
        clock = response["mesh"]["reader"]["clock"]
        control = {"protocol": response["protocol"], "schemaVersion": 1,
                   "mesh": {k: response["mesh"][k] for k in ("meshProtocol", "requestId", "operation", "access")}}
        control["mesh"].update(reader={**response["mesh"]["reader"], "sequence": 2}, kind="gap")
        candidate.accept(control)
        self.assertFalse(candidate.current(boottime_ms(), clock))
        resync = copy.deepcopy(response)
        resync["mesh"].update(kind="resync")
        resync["mesh"]["reader"].update(sequence=3, revision=2)
        candidate.accept(resync)
        control["mesh"].update(reader={**resync["mesh"]["reader"], "sequence": 4}, kind="heartbeat")
        candidate.accept(control)
        self.assertEqual(len(candidate.current(boottime_ms(), clock)), 32)
        expiry = max(r["expiresAtMs"] for h in response["mesh"]["hosts"] for r in h["receipts"])
        self.assertFalse(candidate.current(expiry, clock))
        candidate.disconnect()
        self.assertFalse(candidate.current(boottime_ms(), clock))

    async def test_invalid_replacement_retires_prior_prepared_state(self):
        profile, _, response = await fleet()
        candidate = PreparedGuard("tmux", "a" * 32, profile)
        candidate.accept(response)
        bad = copy.deepcopy(response)
        bad["mesh"]["reader"].update(sequence=2)
        bad["mesh"]["hosts"][0]["receipts"][0]["accepted"] += 1
        with self.assertRaises(Exception):
            candidate.accept(bad)
        self.assertFalse(candidate.current(boottime_ms(), response["mesh"]["reader"]["clock"]))

    async def test_dynamic_eligibility_witness_is_not_sdk1_equivalence(self):
        profile, _, response = await fleet()
        prepared = Prepared(response, profile)
        with patch.object(profile, "record_eligible", return_value=False):
            self.assertFalse(current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"], profile=profile))
            self.assertTrue(prepared.current(boottime_ms(), response["mesh"]["reader"]["clock"]))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OwnershipTests))
    if not result.wasSuccessful() or result.skipped:
        raise SystemExit(1)
