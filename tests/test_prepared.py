"""Opt-in ownership, exact rule admission and conservative stream lifetimes."""

import asyncio
import copy
import inspect
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from prepared_fixture import StaticPreparation
from test_simplification import fleet

from mesh_plus.api import PreparationDescriptor, PreparedReadGuard, ReadGuard, current_sessions
from mesh_plus.protocol import ProtocolError
from mesh_plus.transport import boottime_ms


class PreparedTests(unittest.IsolatedAsyncioTestCase):
    def test_additive_interface_signature_baseline(self):
        from mesh_plus import api
        baseline = json.loads((Path(__file__).parent / "fixtures/prepared-interface-v1.json").read_text())
        self.assertEqual(api.PREPARATION_INTERFACE_VERSION, baseline["interfaceVersion"])
        for name, signature in baseline["signatures"].items():
            actual = api
            for part in name.split("."):
                actual = getattr(actual, part)
            self.assertEqual(str(inspect.signature(actual)), signature)

    def guard(self, profile, *, preparation=None, **kwargs):
        return PreparedReadGuard("tmux" if profile.descriptor.profile_id.startswith("tmux") else "agent",
                                 "a" * 32, profile=profile,
                                 preparation=preparation or StaticPreparation(profile), **kwargs)

    async def test_all_profiles_golden_partial_missing_and_expiry(self):
        for domain, timing in (("tmux", False), ("agent", False), ("agent", True)):
            profile, _, response = await fleet(domain, hosts=4, rows=4, timing=timing)
            for unavailable in (False, True):
                frame = copy.deepcopy(response)
                if unavailable:
                    host = frame["mesh"]["hosts"][-1]
                    host["viewState"] = "historical"
                    for receipt in host["receipts"]:
                        receipt.update(health="stale", expiresAtMs=None, remainingMs=0)
                candidate = self.guard(profile)
                candidate.accept(frame)
                clock = frame["mesh"]["reader"]["clock"]
                times = [frame["mesh"]["reader"]["encodedAtMs"]] + sorted({r["expiresAtMs"]
                         for h in frame["mesh"]["hosts"] for r in h["receipts"] if r["expiresAtMs"] is not None})
                for now in times:
                    self.assertEqual(candidate.current(now, clock), current_sessions(frame, now, clock, profile=profile))
                self.assertEqual(candidate.snapshot(), frame)

    async def test_single_admission_no_query_callbacks_and_no_raw_retention(self):
        profile, _, response = await fleet()
        guard = self.guard(profile)
        with patch.object(profile, "validate_response", wraps=profile.validate_response) as validate:
            guard.accept(response)
            for _ in range(4):
                self.assertEqual(len(guard.current(boottime_ms(), response["mesh"]["reader"]["clock"])), 32)
            self.assertEqual(validate.call_count, 1)
        self.assertIsNone(guard._guard.view)
        self.assertIsNone(guard._guard.admitted)

    async def test_input_and_export_mutation(self):
        profile, _, response = await fleet()
        expected = copy.deepcopy(response)
        guard = self.guard(profile)
        guard.accept(response)
        response["sessions"].clear()
        guard.snapshot()["sessions"].clear()
        guard.current(boottime_ms(), expected["mesh"]["reader"]["clock"])[0]["name"] = "changed"
        self.assertEqual(guard.snapshot(), expected)
        self.assertEqual(guard.current(boottime_ms(), expected["mesh"]["reader"]["clock"]), expected["sessions"])

    async def test_preparation_input_is_deeply_immutable(self):
        profile, _, response = await fleet()
        preparation = StaticPreparation(profile)
        original = preparation.prepare_rules

        def inspect(state):
            with self.assertRaises(TypeError):
                state.records[0]["name"] = "changed"
            with self.assertRaises(TypeError):
                state.owner["service"]["clock"]["bootId"] = "changed"
            with self.assertRaises(AttributeError):
                state.receipts.clear()
            return original(state)

        preparation.prepare_rules = inspect
        self.guard(profile, preparation=preparation).accept(response)

    async def test_bad_rules_close_without_retaining_previous_generation(self):
        profile, _, response = await fleet()
        for kind in ("count", "identity", "boolean", "foreign", "mutable_keys", "list", "exception", "cancel"):
            preparation = StaticPreparation(profile)
            original = preparation.prepare_rules
            calls = 0

            def compile(state):
                nonlocal calls
                calls += 1
                rules = original(state)
                if calls <= 4:
                    return rules
                if kind == "count":
                    return rules[:-1]
                if kind == "list":
                    return list(rules)
                if kind == "exception":
                    raise ValueError("owner_failure")
                if kind == "cancel":
                    raise asyncio.CancelledError()
                rule = rules[0]
                if kind == "identity":
                    rule = replace(rule, identity=("foreign",))
                elif kind == "boolean":
                    rule = replace(rule, eligible=1)
                elif kind == "foreign":
                    rule = replace(rule, required=frozenset({("foreign", "native")}))
                else:
                    rule = replace(rule, required=set(rule.required))
                return (rule, *rules[1:])

            preparation.prepare_rules = compile
            guard = self.guard(profile, preparation=preparation)
            guard.accept(response)
            replacement = copy.deepcopy(response)
            replacement["mesh"]["reader"].update(sequence=2, revision=2)
            with self.subTest(kind=kind), self.assertRaises(BaseException):
                guard.accept(replacement)
            self.assertIsNone(guard.snapshot())
            self.assertFalse(guard.current(boottime_ms(), response["mesh"]["reader"]["clock"]))
            self.assertIsNone(guard._guard.admitted)

    async def test_none_empty_or_ineligible_grant_nothing(self):
        profile, _, response = await fleet()
        for required, eligible in ((None, True), (frozenset(), True), (frozenset({("default", "native")}), False)):
            preparation = StaticPreparation(profile)
            original = preparation.prepare_rules
            preparation.prepare_rules = lambda state: tuple(replace(rule, required=required, eligible=eligible)
                                                           for rule in original(state))
            guard = self.guard(profile, preparation=preparation)
            guard.accept(response)
            self.assertFalse(guard.current(boottime_ms(), response["mesh"]["reader"]["clock"]))

    async def test_gap_resync_heartbeat_and_terminal(self):
        profile, _, response = await fleet()
        guard = self.guard(profile)
        self.assertIsNone(guard.snapshot())
        guard.accept(response)
        control = {"protocol": response["protocol"], "schemaVersion": 1,
                   "mesh": {k: response["mesh"][k] for k in ("meshProtocol", "requestId", "operation", "access")}}
        control["mesh"].update(reader={**response["mesh"]["reader"], "sequence": 2}, kind="heartbeat")
        guard.accept(control)
        self.assertEqual(guard.snapshot(), response)
        control["mesh"].update(reader={**control["mesh"]["reader"], "sequence": 3}, kind="gap")
        guard.accept(control)
        self.assertIsNone(guard.snapshot())
        resync = copy.deepcopy(response)
        resync["mesh"].update(kind="resync")
        resync["mesh"]["reader"].update(sequence=4, revision=2)
        guard.accept(resync)
        expiry = max(r["expiresAtMs"] for h in response["mesh"]["hosts"] for r in h["receipts"])
        self.assertFalse(guard.current(expiry, response["mesh"]["reader"]["clock"]))
        guard.disconnect()
        self.assertIsNone(guard.snapshot())
        with self.assertRaisesRegex(ProtocolError, "read_terminal_barrier"):
            guard.accept(resync)

    async def test_clock_failure_retires_positives(self):
        profile, _, response = await fleet()
        for now, clock in ((True, response["mesh"]["reader"]["clock"]),
                           (response["mesh"]["reader"]["encodedAtMs"] - 1, response["mesh"]["reader"]["clock"]),
                           (boottime_ms(), {})):
            guard = self.guard(profile)
            guard.accept(response)
            with self.assertRaisesRegex(ProtocolError, "reader_clock_scope"):
                guard.current(now, clock)
            self.assertIsNone(guard.snapshot())

    async def test_invalid_proof_scope_receipt_and_order_fail_closed(self):
        profile, _, response = await fleet()
        for kind in ("proof", "scope", "receipt", "order"):
            guard = self.guard(profile)
            guard.accept(response)
            bad = copy.deepcopy(response)
            bad["mesh"]["reader"].update(sequence=2, revision=2)
            if kind == "proof":
                bad["mesh"]["hosts"][1]["delivery"]["proof"]["payloadDigest"] = "sha256:" + "0" * 64
            elif kind == "scope":
                bad["sessions"][0]["hostId"] = "foreign"
            elif kind == "receipt":
                bad["mesh"]["hosts"][0]["receipts"][0]["accepted"] += 1
            else:
                bad["mesh"]["reader"]["sequence"] = 5
            with self.subTest(kind=kind), self.assertRaises(Exception):
                guard.accept(bad)
            self.assertIsNone(guard.snapshot())

    async def test_descriptor_and_callable_changes_invalidate(self):
        profile, _, response = await fleet()
        for kind in ("descriptor", "callable", "profile"):
            preparation = StaticPreparation(profile)
            guard = self.guard(profile, preparation=preparation)
            guard.accept(response)
            previous = profile.descriptor
            if kind == "descriptor":
                preparation.descriptor = replace(preparation.descriptor, implementation_id="new")
            elif kind == "callable":
                preparation.prepare_rules = lambda state: ()
            else:
                profile.descriptor = replace(previous, native_version=999)
            with self.assertRaisesRegex(ProtocolError, "preparation_binding"):
                guard.current(boottime_ms(), response["mesh"]["reader"]["clock"])
            self.assertIsNone(guard._generation)
            profile.descriptor = previous

    async def test_reentrant_retirement_cannot_publish_late_rules(self):
        profile, _, response = await fleet()
        preparation = StaticPreparation(profile)
        original = preparation.prepare_rules

        def compile(state):
            guard.disconnect()
            return original(state)

        preparation.prepare_rules = compile
        guard = self.guard(profile, preparation=preparation)
        with self.assertRaisesRegex(ProtocolError, "prepared_retired"):
            guard.accept(response)
        self.assertIsNone(guard.snapshot())

    async def test_unsupported_preparation_rejected_at_construction(self):
        profile, _, _ = await fleet()
        for version in (True, 2):
            preparation = StaticPreparation(profile)
            preparation.descriptor = PreparationDescriptor(version, profile.descriptor, "test")
            with self.assertRaisesRegex(ProtocolError, "preparation_descriptor"):
                self.guard(profile, preparation=preparation)
        with self.assertRaisesRegex(ProtocolError, "preparation_descriptor"):
            self.guard(profile, preparation=object())
        preparation = StaticPreparation(profile)
        preparation.descriptor = replace(preparation.descriptor,
                                         profile=replace(profile.descriptor, native_version=True))
        with self.assertRaisesRegex(ProtocolError, "preparation_descriptor"):
            self.guard(profile, preparation=preparation)

    async def test_equal_boolean_descriptor_replacement_invalidates(self):
        profile, _, response = await fleet()
        preparation = StaticPreparation(profile)
        guard = self.guard(profile, preparation=preparation)
        guard.accept(response)
        preparation.descriptor = replace(preparation.descriptor, interface_version=True)
        with self.assertRaisesRegex(ProtocolError, "preparation_binding"):
            guard.current(boottime_ms(), response["mesh"]["reader"]["clock"])
        self.assertIsNone(guard._generation)

    async def test_reentrant_acceptance_cannot_publish_outer_result(self):
        profile, _, response = await fleet()
        preparation = StaticPreparation(profile)
        original = preparation.prepare_rules

        def compile(state):
            with self.assertRaisesRegex(ProtocolError, "prepared_reentrant"):
                guard.accept(response)
            return original(state)

        preparation.prepare_rules = compile
        guard = self.guard(profile, preparation=preparation)
        with self.assertRaisesRegex(ProtocolError, "prepared_retired"):
            guard.accept(response)
        self.assertIsNone(guard.snapshot())

    async def test_legacy_mutable_revalidation_and_later_rejection_unchanged(self):
        profile, _, response = await fleet()
        legacy = ReadGuard("tmux", "a" * 32, profile=profile)
        legacy.accept(response)
        prepared = self.guard(profile)
        prepared.accept(response)
        legacy.view["sessions"][0]["sessionId"] = "$forged"
        with self.assertRaises(Exception):
            legacy.current(boottime_ms(), response["mesh"]["reader"]["clock"])
        with patch.object(profile, "validate_response", side_effect=ValueError("later_rejection")):
            with self.assertRaises(ValueError):
                current_sessions(response, boottime_ms(), response["mesh"]["reader"]["clock"], profile=profile)
            self.assertEqual(len(prepared.current(boottime_ms(), response["mesh"]["reader"]["clock"])), 32)

    async def test_serialized_capacity_failure_closes(self):
        profile, _, response = await fleet()
        guard = self.guard(profile)
        with patch("mesh_plus.prepared._CAPACITY", 256):
            with self.assertRaisesRegex(ProtocolError, "prepared_capacity"):
                guard.accept(response)
        self.assertIsNone(guard.snapshot())

    async def test_expected_scope_rejects_before_compilation(self):
        profile, _, response = await fleet()
        preparation = StaticPreparation(profile)
        with patch.object(preparation, "prepare_rules", wraps=preparation.prepare_rules) as compile:
            guard = self.guard(profile, preparation=preparation, host_ids=["foreign"])
            with self.assertRaisesRegex(ProtocolError, "read_scope_binding"):
                guard.accept(response)
            compile.assert_not_called()
            self.assertIsNone(guard.snapshot())
