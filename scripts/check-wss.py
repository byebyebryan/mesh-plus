"""Strict optional WSS acceptance, standalone by default; no live selection."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", action="store_true", help="both reviewed pure Observer profiles")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--installed", action="store_true", help="reject editable/source imports")
    args = parser.parse_args()
    import mesh_plus
    package = Path(mesh_plus.__file__).resolve().parent
    if args.installed and package.is_relative_to(ROOT):
        raise RuntimeError("installed wheel required")
    if args.native:
        for name, expected in (("tmux-observer", "0.6.0a5"), ("agent-observer", "0.5.0a16")):
            if importlib.metadata.version(name) != expected:
                raise RuntimeError("reviewed native package required: " + name)
    os.environ["MESH_WSS_NATIVE"] = "1" if args.native else "0"
    sys.path.insert(0, str(ROOT / "tests/wss"))
    names = ["test_wss_carrier", "test_wss_integration"] + (["test_wss_state", "test_wss_cli"] if args.native else [])
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    passed = (result.testsRun > 0 and result.wasSuccessful() and not result.skipped and
              not result.expectedFailures and not result.unexpectedSuccesses)
    report = {"status": "passed" if passed else "failed", "testsRun": result.testsRun,
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
              "scope": "native WSS" if args.native else "standalone WSS independent profile",
              "packages": {name: importlib.metadata.version(name) for name in ("mesh-plus", "websockets")},
              "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped),
              "installed": args.installed, "expectedFailures": len(result.expectedFailures),
              "unexpectedSuccesses": len(result.unexpectedSuccesses),
              "runtimeInputs": {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(package.rglob("*")) if p.suffix in {".py", ".json"}},
              "inputs": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                         for folder in (ROOT / "src/mesh_plus/wss", ROOT / "tests/wss")
                         for p in sorted(folder.glob("*")) if p.is_file()},
              "excluded": ["live fleet", "physical suspend", "WAN", "deployment selection"]}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"inputs", "runtimeInputs"}}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
