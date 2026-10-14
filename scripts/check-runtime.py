"""Runtime acceptance report; core-only mode includes independent SDK profiles and excludes native adapters."""

import argparse
import hashlib
import importlib.metadata
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

import mesh_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-only", action="store_true", help="no Observer dependencies or native acceptance")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    loader = unittest.TestLoader()
    if args.core_only:
        suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in
                                  ("test_publisher", "test_protocol", "test_transport", "test_delivery", "test_diagnostics", "test_assessment", "test_configured_read", "test_sdk", "test_agent_timing_profile", "test_agent_system_profile", "test_simplification", "test_prepared", "test_conformance",
                                   "test_authority", "test_library_authority", "test_remote.QuotingTests"))
    else:
        suite = loader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    versions = {}
    for name in ("mesh-plus", "tmux-observer", "agent-observer", "jsonschema"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    report = {"status": "passed" if result.wasSuccessful() else "failed",
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "python": sys.version.split()[0],
              "scope": "standalone IPC/lifecycle/SDK profiles/authority/quoting" if args.core_only else "runtime and owned native/SSH acceptance",
              "testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
              "versions": versions,
              "runtimeDigests": {str(path.relative_to(Path(mesh_plus.__file__).parent)): hashlib.sha256(path.read_bytes()).hexdigest()
                                 for path in sorted(Path(mesh_plus.__file__).parent.rglob("*"))
                                 if path.is_file() and path.suffix in {".py", ".json"}},
              "testDigests": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted((ROOT / "tests").glob("*.py"))},
              "limits": ["No operational fleet, installed artifact selection, GUI or physical suspend acceptance",
                         "Agent integration uses validated native fixture publishers, not native provider collection"]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"limits", "runtimeDigests", "testDigests"}}, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
