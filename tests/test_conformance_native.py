"""Portable scenarios also preserve the reviewed native facade semantics."""

import unittest

from mesh_plus.api import ReferenceProfile
from mesh_plus.testing import network_suite, run_suite


class NativeConformanceTests(unittest.TestCase):
    def test_network_scenarios_with_native_validators(self):
        for domain in ("tmux", "agent"):
            report = run_suite(network_suite(ReferenceProfile, domain=domain), domain=domain)
            self.assertTrue(report["ok"], report)
