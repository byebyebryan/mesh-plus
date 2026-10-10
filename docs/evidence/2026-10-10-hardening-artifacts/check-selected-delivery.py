"""Supplement local artifact gates with actual cached Agent fleet delivery.

Prepared-reader reports independently prove captured desktop context and the
reader incarnation after recovery. Raw cached responses stay private.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("snap", "starship"), required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--prepared", type=Path)
    parser.add_argument("--before-recovery", type=Path)
    args = parser.parse_args()
    assert args.label and args.label.replace("-", "").isalnum(), "unsafe report label"
    baseline_raw = (args.work / "baseline.json").read_bytes()
    baseline = json.loads(baseline_raw)
    assert baseline["host"] == args.host
    receipts = []
    for scope in ("local", "fleet"):
        result = subprocess.run(
            [str(Path.home() / ".local/bin/agent-observer"), "mesh", "snapshot", "--scope", scope],
            capture_output=True,
            timeout=40,
            cwd="/tmp",
        )
        assert result.returncode == 0, "cached Agent read failed"
        raw_path = args.work / (args.label + "-agent-" + scope + "-private.json")
        raw_path.write_bytes(result.stdout)
        raw_path.chmod(0o600)
        frame = json.loads(result.stdout)
        assert frame["protocol"] == "agent-observer.mesh-candidate.v1", "unexpected Agent profile"
        assert frame["mesh"]["status"] == "complete", "cached Agent delivery incomplete"
        hosts = frame["mesh"]["scope"]["hostIds"]
        expected = (
            [args.host] if scope == "local" else [args.host, "starship" if args.host == "snap" else "snap"]
        )
        assert hosts == expected, "cached Agent scope differs from captured two-host fleet"
        receipts.append(
            {
                "scope": scope,
                "hostIds": hosts,
                "rows": len(frame["sessions"]),
                "sha256": hashlib.sha256(result.stdout).hexdigest(),
            }
        )
    reader = {"applicable": baseline["desktopActive"], "physicalDesktopAcceptance": False}
    if baseline["desktopActive"]:
        assert args.prepared is not None, "headed reader receipt required"
        original_raw = (args.work / "baseline-tmux.json").read_bytes()
        current_raw = args.prepared.read_bytes()
        original = json.loads(original_raw)["prepared"]
        current = json.loads(current_raw)["prepared"]
        assert current["contextId"] == original["contextId"], "captured desktop context changed"
        reader["capturedContextPreserved"] = True
        reader["baselinePreparedSha256"] = hashlib.sha256(original_raw).hexdigest()
        reader["currentPreparedSha256"] = hashlib.sha256(current_raw).hexdigest()
        if args.before_recovery:
            before_raw = args.before_recovery.read_bytes()
            before = json.loads(before_raw)["prepared"]
            assert current["readerId"] != before["readerId"], "headed reader incarnation unchanged"
            reader["recoveryIncarnationChanged"] = True
            reader["beforeRecoverySha256"] = hashlib.sha256(before_raw).hexdigest()
    else:
        assert args.prepared is None and args.before_recovery is None, (
            "headless baseline has no prepared reader"
        )
    report = {
        "state": "passed",
        "hostId": args.host,
        "label": args.label,
        "scope": "selected local and SSH fleet cached Agent reads; existing prepared Tmux reader receipts",
        "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "baselineSha256": hashlib.sha256(baseline_raw).hexdigest(),
        "cachedReads": receipts,
        "headedReader": reader,
        "providerActions": False,
    }
    (args.work / (args.label + "-delivery-summary.json")).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
