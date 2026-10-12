"""Adversarial checks for the trial's PID and CPU attribution (not runtime conformance)."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from coordinator import resources  # noqa: E402
from measure import process  # noqa: E402


class AccountingTests(unittest.TestCase):
    def test_birth_mismatch_rejects_live_process(self):
        current = process(os.getpid())
        self.assertEqual(process(os.getpid(), current["birth"])["birth"], current["birth"])
        self.assertEqual(process(os.getpid(), "0")["error"], "incarnation_changed")

    def test_no_child_cpu_aggregation_or_privileged_memory_invention(self):
        samples = []
        for at, ticks in ((0, 100), (10, 150)):
            samples.append({"time": at, "sampler": {"ticks": ticks}, "roles": [
                {"role": "reader", "pid": 1, "birth": "7", "ticks": ticks, "rssKiB": 12, "pssKiB": 9, "fds": 4,
                 "childTicks": 99999},
                {"role": "ssh-server", "pid": 2, "birth": "8", "ticks": 3, "rssKiB": 4, "pssKiB": None, "fds": None},
            ]})
        result = resources(samples)
        self.assertEqual(result["roles"][0]["cpuPercent"], 500 / os.sysconf("SC_CLK_TCK"))
        self.assertIsNone(result["roles"][1]["pssMeanKiB"])
        self.assertEqual(result["roles"][1]["cpuPercent"], 0)

    def test_missing_or_reused_role_never_silently_becomes_zero(self):
        samples = [{"time": at, "sampler": {"ticks": 0}, "roles": [{"role": "publisher", "pid": 1,
                    "error": "incarnation_changed"}]} for at in (0, 1)]
        result = resources(samples)
        self.assertEqual(len(result["errors"]), 2)
        self.assertEqual(result["roles"], [])


if __name__ == "__main__":
    unittest.main()
