"""The portable oracle detects both permissive and overconservative profiles."""

import copy
import json
import unittest

from mesh_plus.testing import network_suite, profile_cases, profile_suite, run_suite
from mesh_plus.testing.sample import Profile


class ConformanceTests(unittest.TestCase):
    def test_portable_owned_networking_for_both_profiles(self):
        for domain in ("tmux", "agent"):
            report = run_suite(network_suite(Profile, domain=domain), domain=domain)
            self.assertTrue(report["ok"], report)

    def test_independent_profiles_pass_fixed_oracles(self):
        for domain in ("tmux", "agent"):
            report = run_suite(profile_suite(Profile, domain=domain), domain=domain)
            self.assertTrue(report["ok"], report)
            self.assertEqual(report["testsRun"], 6 if domain == "tmux" else 7)
            self.assertNotIn("sessions", json.dumps(report))

    def test_broken_profiles_fail_independent_oracle(self):
        for fault in ("receipt", "eligibility", "identity", "reconstruction", "binding", "lease"):
            def factory(domain):
                p = Profile(domain)
                if fault == "receipt":
                    p.record_receipts = lambda row, state: frozenset()
                elif fault == "eligibility":
                    p.record_eligible = lambda row, state: True
                    p.record_receipts = lambda row, state: frozenset(
                        (r["sourceId"], r["component"]) for r in state.receipts if r["health"] in {"current", "partial"})
                elif fault == "identity":
                    p.record_identity = lambda row: ("same",)
                elif fault == "reconstruction":
                    original = p.restore_native
                    p.restore_native = lambda owner, rows: original(owner, [])
                else:
                    original = p.bind
                    def bind(host, source):
                        codec = original(host, source)
                        if fault == "binding":
                            codec.source = "wrong"
                        else:
                            inspect = codec.inspect_native
                            def altered(frame):
                                state = inspect(frame)
                                for receipt in state.receipts:
                                    if receipt["expiry"] is not None:
                                        receipt["expiry"] += 100
                                return state
                            codec.inspect_native = altered
                        return codec
                    p.bind = bind
                return p
            with self.subTest(fault=fault):
                report = run_suite(profile_suite(factory, domain="agent"), domain="agent")
                self.assertFalse(report["ok"], report)

    def test_unrelated_exception_is_error_not_rejection(self):
        def broken(domain):
            p = Profile(domain)
            p.validate_response = lambda response: (_ for _ in ()).throw(RuntimeError("private payload"))
            return p
        report = run_suite(profile_suite(broken, domain="tmux"), domain="tmux")
        self.assertEqual(report["errors"], 6)
        self.assertNotIn("private", json.dumps(report))

    def test_cases_are_fresh_and_empty_suite_rejected(self):
        first = profile_cases("tmux")
        original = copy.deepcopy(first[0].response)
        first[0].response.clear()
        self.assertEqual(profile_cases("tmux")[0].response, original)
        with self.assertRaises(ValueError):
            profile_suite(Profile, domain="tmux", cases=[])
