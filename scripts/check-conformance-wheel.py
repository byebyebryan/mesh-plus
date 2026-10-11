"""External installed-kit caller; requires no Mesh checkout test imports."""

import argparse
import importlib.util
import json
import os
import tempfile

import mesh_plus
from mesh_plus.testing import network_suite, profile_suite, run_suite
from mesh_plus.testing.sample import Profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh", action="store_true", help="separate owned actual-SSH acceptance")
    args = parser.parse_args()
    reports = []
    with tempfile.TemporaryDirectory(prefix="mesh-external-caller-") as directory:
        os.chdir(directory)
        for domain in ("tmux", "agent"):
            for suite in (profile_suite(Profile, domain=domain), network_suite(Profile, domain=domain)):
                report = run_suite(suite, domain=domain)
                if not report["ok"]:
                    raise AssertionError(report)
                reports.append(report)
            def broken(domain):
                p = Profile(domain)
                p.record_receipts = lambda row, state: frozenset()
                return p
            negative = run_suite(profile_suite(broken, domain=domain), domain=domain)
            if negative["ok"] or not negative["failures"]:
                raise AssertionError("broken external profile was certified")
            if args.ssh:
                from mesh_plus.testing.ssh import ssh_suite
                report = run_suite(ssh_suite(Profile, domain=domain), domain=domain)
                if not report["ok"]:
                    raise AssertionError(report)
                reports.append(report)
    print(json.dumps({"status": "passed", "meshVersion": mesh_plus.__version__,
                      "observerPackagesPresent": {name: importlib.util.find_spec(name) is not None
                                                  for name in ("tmux_observer", "agent_observer")},
                      "reports": reports, "negativeProfilesDetected": 2,
                      "limits": "Installed independent fixture profiles, not owner deployment or provider acceptance"}, indent=2))


if __name__ == "__main__":
    main()
