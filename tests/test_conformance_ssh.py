import unittest

from mesh_plus.testing import run_suite
from mesh_plus.testing.sample import Profile
from mesh_plus.testing.ssh import ssh_suite


class SSHConformanceTests(unittest.TestCase):
    def test_independent_actual_ssh(self):
        for domain in ("tmux", "agent"):
            report = run_suite(ssh_suite(Profile, domain=domain), domain=domain)
            self.assertTrue(report["ok"], report)
