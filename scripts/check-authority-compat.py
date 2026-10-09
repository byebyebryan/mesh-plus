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
    args = parser.parse_args()
    report_path = args.report.resolve() if args.report else None
    root = args.ssh_plus.resolve()
    source = root / "rofi_ssh_plus/mesh.py"
    extracted = Path(authority.__file__)
    if source.read_bytes() != extracted.read_bytes():
        raise SystemExit("authority source drift: review extraction before running compatibility gate")
    if subprocess.check_output(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"]).strip():
        raise SystemExit("SSH Plus tracked source must be clean for baseline compatibility evidence")
    os.chdir(root)
    sys.path.insert(0, str(root))
    import rofi_ssh_plus
    sys.modules["rofi_ssh_plus.mesh"] = authority
    rofi_ssh_plus.mesh = authority
    result = unittest.TextTestRunner(verbosity=1).run(unittest.TestLoader().discover(str(root / "tests")))
    report = {"status": "passed" if result.wasSuccessful() else "failed",
              "checkedAtUtc": datetime.now(timezone.utc).isoformat(),
              "sourceProject": "rofi-ssh-plus",
              "sourceCommit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "sourceFile": "rofi_ssh_plus/mesh.py",
              "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "extractedFile": "src/mesh_plus/authority.py",
              "testsRun": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "method": "Byte-identical model/store extraction; process-only CLI isolated from picker",
              "limits": ["In-process model imports bound to Mesh; subprocess wrapper tests still use original SSH source",
                         "Mesh process is separately tested in runtime suite",
                         "No operational authority selection, history migration or SSH facade deployment"]}
    if report_path:
        report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
