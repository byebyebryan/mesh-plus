"""Retired prerelease profiles are rejected before they select a codec/endpoint."""

import unittest

from mesh_plus.api import descriptor
from mesh_plus.protocol import ProtocolError
from mesh_plus.state import ProfileDescriptor, resolve_profile


class RetiredProfileTest(unittest.TestCase):
    def test_active_profile_is_not_currently_registered(self):
        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            descriptor("agent", profile_id="agent-observer.mesh-active.v1")

    def test_supplied_retired_descriptor_cannot_reintroduce_admission(self):
        class Retired:
            descriptor = ProfileDescriptor(1, "agent-observer.mesh-active.v1", "agent-observer.active-feed", 1, "sha256:" + "0" * 64, 8404992)

            def bind(self, *_):
                raise AssertionError("retired profile reached codec dispatch")

        with self.assertRaisesRegex(ProtocolError, "profile_descriptor"):
            resolve_profile("agent", Retired())

    def test_full_working_set_and_tmux_stay_registered(self):
        for domain, profile in (("agent", "agent-observer.mesh-candidate.v3"),
                                ("agent", "agent-observer.mesh-working-set.v1"),
                                ("tmux", "tmux-observer.mesh-candidate.v1")):
            with self.subTest(profile=profile):
                self.assertEqual(descriptor(domain, profile_id=profile).profile_id, profile)
