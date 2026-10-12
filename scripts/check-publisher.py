"""Strict public publisher/factory acceptance; installed and optional carriers are explicit."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--ssh", action="store_true", help="owned real fixed SSH command")
    parser.add_argument("--wss", action="store_true", help="optional native TLS listener factory")
    parser.add_argument("--baseline-python", type=Path, help="explicit installed a10 reference bridge")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    import mesh_plus
    from mesh_plus.api import SDK_INTERFACE_VERSION

    package = Path(mesh_plus.__file__).resolve().parent
    if args.installed and package.is_relative_to(ROOT):
        raise RuntimeError("installed wheel required")
    sys.path.insert(0, str(ROOT / "tests"))
    names = ["test_publisher"]
    if args.ssh:
        names.append("test_publisher_ssh")
    if args.wss:
        sys.path.insert(0, str(ROOT / "tests/wss"))
        names.append("test_wss_publisher")
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    baseline = None
    if args.baseline_python:
        baseline = json.loads(subprocess.check_output([str(args.baseline_python), "-I", "-c",
            "import json,importlib.metadata;print(json.dumps({n:importlib.metadata.version(n) for n in "
            "('mesh-plus','tmux-observer','agent-observer')}))"], timeout=5))
        if baseline != {"mesh-plus": "0.1.0a10", "tmux-observer": "0.6.0a5", "agent-observer": "0.5.0a16"}:
            raise RuntimeError("reviewed installed baseline required")
        from publisher_mixed import mixed_suite
        suite.addTests(mixed_suite(args.baseline_python))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = (result.testsRun > 0 and result.wasSuccessful() and not result.skipped and
              not result.expectedFailures and not result.unexpectedSuccesses)
    report = {"status": "passed" if passed else "failed", "testsRun": result.testsRun,
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "meshVersion": importlib.metadata.version("mesh-plus"), "sdkInterface": SDK_INTERFACE_VERSION,
              "baselinePackages": baseline, "packagePath": str(package), "installed": args.installed, "ssh": args.ssh, "wss": args.wss,
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "expectedFailures": len(result.expectedFailures), "unexpectedSuccesses": len(result.unexpectedSuccesses),
              "runtimeInputs": {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(package.rglob("*")) if p.suffix in {".py", ".json"}},
              "testInputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in [*(ROOT / "tests").glob("*.py"), *(ROOT / "tests/wss").glob("*.py")]},
              "exclusions": ["owner-native acquisition", "live fleet", "resource budgets", "deployment",
                             "physical suspend", "sibling source parity"]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"runtimeInputs", "testInputs"}}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
