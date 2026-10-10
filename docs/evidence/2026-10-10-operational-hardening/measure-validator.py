"""ABBA CPU comparison of one pure validator change on a private cached input."""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import time
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--agent-checkout", type=Path, required=True)
parser.add_argument(
    "--before-revision",
    default="3e17a9b33aef43d51c7ce2ef6a4cb51ecd6756cf",
    help="explicit pre-optimization source; never the moving checkout HEAD",
)
parser.add_argument("--frame", type=Path, required=True)
parser.add_argument("--report", type=Path, required=True)
args = parser.parse_args()
old_bytes = subprocess.check_output(
    ["git", "show", args.before_revision + ":agent_observer/contract.py"], cwd=args.agent_checkout
)
new_bytes = (args.agent_checkout / "agent_observer/contract.py").read_bytes()
import agent_observer.contract as new

old = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("agent_observer.contract_before", loader=None)
)
exec(compile(old_bytes, "contract_before.py", "exec"), old.__dict__)
snapshot = json.loads(args.frame.read_bytes())["snapshot"]
assert old.schema_document("snapshot") == new.schema_document("snapshot")
assert old.schema_document("watch") == new.schema_document("watch")
old.validate_snapshot(snapshot)
new.validate_snapshot(snapshot)
measurements = []
for label, module in (("before", old), ("after", new), ("after", new), ("before", old)):
    started = time.process_time()
    for _ in range(100):
        module.validate_snapshot(snapshot)
    measurements.append(
        {"variant": label, "validations": 100, "cpuMs": round((time.process_time() - started) * 1000, 3)}
    )
report = {
    "format": "agent-observer.validator-comparison.v1",
    "state": "passed",
    "rows": len(snapshot["sessions"]),
    "measurements": measurements,
    "beforeSha256": hashlib.sha256(old_bytes).hexdigest(),
    "afterSha256": hashlib.sha256(new_bytes).hexdigest(),
    "inputSha256": hashlib.sha256(args.frame.read_bytes()).hexdigest(),
    "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "schemaParity": True,
    "limits": [
        "Pure snapshot validation only; not complete Reader or collector cost",
        "ABBA process CPU with identical immutable cached input; host load uncontrolled",
        "No input records published; no source receipts or native facts renewed",
    ],
}
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"state": "passed", "measurements": measurements}))
