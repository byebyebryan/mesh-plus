"""Run SSH Plus regressions with its in-process model bound to Mesh authority."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mesh_plus import authority


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ssh-plus", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--backend", choices=("legacy", "mesh-plus"), default="legacy")
    args = parser.parse_args()
    report_path = args.report.resolve() if args.report else None
    root = args.ssh_plus.resolve()
    source = root / "rofi_ssh_plus/mesh.py"
    if (root / "rofi_ssh_plus/_legacy_mesh.py").exists():
        source = root / "rofi_ssh_plus/_legacy_mesh.py"
    extracted = Path(authority.__file__)
    if source.read_bytes() != extracted.read_bytes():
        raise SystemExit("authority source drift: review extraction before running compatibility gate")
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"]).strip():
        raise SystemExit("SSH Plus tracked source must be clean for baseline compatibility evidence")
    os.chdir(root)
    sys.path.insert(0, str(root))
    import rofi_ssh_plus
    if args.backend == "mesh-plus":
        os.environ["ROFI_SSH_PLUS_MESH_BACKEND"] = "mesh-plus"
        os.environ["PYTHONPATH"] = str(extracted.parent.parent)
        from rofi_ssh_plus import mesh
        if mesh is not authority:
            raise SystemExit("SSH Plus did not select the canonical Mesh authority")
    else:
        os.environ["ROFI_SSH_PLUS_MESH_BACKEND"] = "legacy"
        sys.modules["rofi_ssh_plus.mesh"] = authority
        rofi_ssh_plus.mesh = authority
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestLoader().discover(str(root / "tests")))
    report = {"status": "passed" if result.wasSuccessful() else "failed",
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
              "sourceProject": "rofi-ssh-plus",
              "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "sourceFile": str(source.relative_to(root)),
              "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "extractedFile": "src/mesh_plus/authority.py",
              "testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "backend": args.backend,
              "skipped": [{"test": test.id(), "reason": reason} for test, reason in result.skipped],
              "method": "Byte-identical model/store extraction; process-only CLI isolated from picker",
              "limits": [("Canonical Mesh authority selected in SSH imports and subprocesses" if args.backend == "mesh-plus"
                          else "In-process model imports bound to Mesh; subprocess wrapper tests still use legacy SSH authority"),
                         "Mesh process is separately tested in runtime suite",
                         "No operational authority selection, history migration or SSH facade deployment"]}
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
