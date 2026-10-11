"""Explicit strict study gate; skipped cases and any input drift fail closed."""

import argparse
import hashlib
import importlib.metadata
import json
import platform
import ssl
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("carrier", "state", "all"), default="all")
    args = parser.parse_args()
    baseline = json.loads((STUDY / "baseline.json").read_text())
    drift = [name for name, expected in baseline["runtimeInputs"].items()
             if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected]
    pattern = "test_*.py" if args.phase == "all" else "test_" + args.phase + ".py"
    suite = unittest.defaultTestLoader.discover(str(STUDY), pattern=pattern)
    result = unittest.TestResult()
    suite.run(result)
    passed = (result.testsRun > 0 and result.wasSuccessful() and not result.skipped and
              not result.expectedFailures and not result.unexpectedSuccesses and not drift)
    report = {"format": "mesh-plus.wss-study.validation.v1", "phase": args.phase,
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
              "status": "passed" if passed else "failed", "testsRun": result.testsRun,
              "failures": [str(case) for case, _ in result.failures],
              "errors": [str(case) for case, _ in result.errors],
              "skipped": [str(case) for case, _ in result.skipped],
              "expectedFailures": len(result.expectedFailures), "unexpectedSuccesses": len(result.unexpectedSuccesses),
              "runtimeDrift": drift, "python": platform.python_version(), "tls": ssl.OPENSSL_VERSION,
              "packages": {name: importlib.metadata.version(name) for name in baseline["packages"]},
              "studyInputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(STUDY.glob("*.py"))
                              if args.phase == "all" or p.name in {"baseline.py", "carrier.py", "check.py",
                                 "configuration.py", "fixtures.py", "test_carrier.py"} or
                              (args.phase == "state" and p.name == "test_state.py")},
              "scope": "owned loopback mTLS, released SDK and reviewed pure native wheels; no runtime promotion",
              "excluded": baseline["excluded"]}
    print(json.dumps(report, indent=2))
    if not passed:
        # Errors are local console diagnostics, not committed/public evidence.
        import sys
        for _, trace in result.errors + result.failures:
            print(trace, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
