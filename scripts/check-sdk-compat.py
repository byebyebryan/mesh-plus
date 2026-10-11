"""Compare pure native projections/effective rows against a pinned prior SDK."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample():
    from mesh_plus.view import current_sessions, reconstructed, validate_response
    results = []
    for path in sorted((ROOT / "contracts/mesh-read-v1/examples").glob("*.json")):
        if not path.name.startswith(("tmux-", "agent-")) or "wss" in path.name:
            continue
        response = json.loads(path.read_text())
        validate_response(response)
        clock = response["mesh"]["reader"]["clock"]
        encoded = response["mesh"]["reader"]["encodedAtMs"]
        times = [encoded, encoded + 1000, 2**52]
        results.append({"fixture": path.name,
                        "native": [reconstructed(response, host) for host in response["mesh"]["hosts"]
                                   if host["owner"] is not None],
                        "effective": [current_sessions(response, now, clock) for now in times]})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-python", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--sample", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.sample:
        print(json.dumps(sample(), sort_keys=True, separators=(",", ":")))
        return 0
    if args.baseline_python is None:
        parser.error("--baseline-python must select a separately pinned prior SDK/native environment")
    command = [str(Path(__file__).resolve()), "--sample"]
    baseline = subprocess.check_output([str(args.baseline_python), *command])
    candidate = subprocess.check_output([sys.executable, *command])
    original, current = json.loads(baseline), json.loads(candidate)
    versions = "import importlib.metadata as m,json;print(json.dumps({n:m.version(n) for n in ['mesh-plus','tmux-observer','agent-observer']}))"
    report = {"status": "passed" if current == original else "failed", "fixtureCount": len(current),
              "selectionComparisons": 3 * len(current),
              "baselineVersions": json.loads(subprocess.check_output([str(args.baseline_python), "-c", versions])),
              "candidateVersions": json.loads(subprocess.check_output([sys.executable, "-c", versions])),
              "baselineResultSha256": hashlib.sha256(baseline).hexdigest(),
              "candidateResultSha256": hashlib.sha256(candidate).hexdigest(),
              "fixtureDigests": {result["fixture"]: hashlib.sha256(
                  (ROOT / "contracts/mesh-read-v1/examples" / result["fixture"]).read_bytes()).hexdigest() for result in current},
              "limits": ["Pure frozen IPC/SSH-profile projections and effective selections only",
                         "No native provider collection, live services, WSS runtime or deployment"]}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if current == original else 1


if __name__ == "__main__":
    raise SystemExit(main())
