"""Bind redacted reports, package parity and preservation after owned jobs end."""

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
scratch = Path("/tmp/mesh-hardening")
output = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--checkpoint", action="store_true", help="record completed work without accepting pending soaks"
)
args = parser.parse_args()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


reports = [
    *scratch.glob("matched*.json"),
    *scratch.glob("replay*.json"),
    *scratch.glob("live-fixed*.json"),
    *scratch.glob("live-starship*.json"),
    *[
        scratch / name
        for name in (
            "refresh-mesh-installed.json",
            "refresh-detailed.json",
            "refresh-delivery.json",
            "validator-comparison.json",
            "wheel-core.json",
            "wheel-native.json",
            "tmux-source-mesh.json",
            "tmux-source-mesh-a10.json",
            "tmux-source-mesh-a10-refined.json",
            "tmux-source-first-run.json",
            "tmux-source-final.json",
            "process-abort.json",
            "rotation-tmux.json",
            "rotation-agent.json",
        )
    ],
]
assert all(path.is_file() for path in reports)
reports.extend(scratch.glob("candidate-rotation-*.json"))
if (scratch / "refresh-candidate-a10.json").is_file():
    reports.append(scratch / "refresh-candidate-a10.json")
soaks = {}
for domain in ("tmux", "agent"):
    name = f"candidate-rotation-{domain}.json"
    retry = scratch / f"candidate-rotation-{domain}-retry.json"
    path = retry if retry.is_file() else scratch / name
    if path.is_file():
        report = json.loads(path.read_bytes())
        rotations = all(
            len(frame["hostRotations"]) == 2
            and all(
                count >= 2 and frame["hostRecoveries"].get(host) == count
                for host, count in frame["hostRotations"].items()
            )
            for frame in report["frames"]
        )
        complete = all(
            not m["partial"] and not m["activeConnections"] and not m["cleanupFailures"]
            for m in report["readerMetrics"]
        )
        soaks[domain] = {
            "report": path.name,
            "state": report["state"],
            "rotationCoverage": rotations,
            "completeMetricsAndCleanup": complete,
        }
    else:
        soaks[domain] = {"state": "pending"}
    if not args.checkpoint:
        assert soaks[domain]["state"] == "passed", domain
        assert soaks[domain]["rotationCoverage"] and soaks[domain]["completeMetricsAndCleanup"], domain
for path in reports:
    shutil.copyfile(path, output / path.name)

preservation = {}
for host in ("snap", "starship"):
    before, after = scratch / f"baseline-{host}.json", scratch / f"final-{host}.json"
    assert before.read_bytes() == after.read_bytes(), host
    preservation[host] = {
        "state": "unchanged",
        "beforeSha256": sha(before),
        "afterSha256": sha(after),
        "scope": "Recorded Python/JSON runtime files, protected controls and service incarnations",
        "excludes": [
            "Python bytecode",
            "Unlisted launchers and dependency binaries",
            "Native provider records",
        ],
    }
    shutil.copyfile(before, output / before.name)
(output / "preservation.json").write_text(json.dumps(preservation, indent=2) + "\n")

wheel = scratch / "candidate/mesh_plus-0.1.0a10-py3-none-any.whl"
with zipfile.ZipFile(wheel) as archive:
    members = {
        name: hashlib.sha256(archive.read(name)).hexdigest()
        for name in archive.namelist()
        if name.startswith("mesh_plus/") and name.endswith((".py", ".json"))
    }
source = {
    "mesh_plus/" + str(path.relative_to(root / "src/mesh_plus")): sha(path)
    for path in (root / "src/mesh_plus").rglob("*")
    if path.suffix in {".py", ".json"}
}
assert members == source
protected = [
    "src/mesh_plus/authority.py",
    "src/mesh_plus/authority_cli.py",
    "contracts/LOCK.json",
    *[str(path.relative_to(root)) for path in (root / "src/mesh_plus/schemas").glob("*.json")],
]
for name in protected:
    previous = subprocess.check_output(["git", "show", "v0.1.0a9:" + name], cwd=root)
    assert hashlib.sha256(previous).hexdigest() == sha(root / name), name
candidate = {
    "state": "candidate_only",
    "wheelSha256": sha(wheel),
    "wheel": wheel.name,
    "sourceRuntimeParity": True,
    "members": members,
    "frozenFiles": {name: sha(root / name) for name in protected},
    "sourceCheckpoint": "504a176d9d9037634465ef1ab7a71988f317ca60",
    "limits": ["No immutable release or deployed selection; consumers still select a9"],
}
(output / "candidate.json").write_text(json.dumps(candidate, indent=2) + "\n")
(output / "review-status.json").write_text(
    json.dumps(
        {
            "state": "checkpoint" if args.checkpoint else "source_and_candidate_review_complete",
            "soaks": soaks,
            "releasedSelection": "0.1.0a9",
            "candidateSelected": False,
            "limits": ["No release, managed selection or physical desktop acceptance"],
        },
        indent=2,
    )
    + "\n"
)

# Soaks loaded this exact script before the multi-Reader ownership correction.
# The original reporting code reads its pathname at completion. Preserve the
# executed bytes separately instead of attributing execution to that later hash.
soak_harness = scratch / "profile-fleet-soak.py"
assert sha(soak_harness) == "7959f9613c3a7802a8aae6ef04834f3bae86b8d733081512e16758ccbb238560"
shutil.copyfile(soak_harness, output / "profile-fleet-soak.py")
(output / "soak-provenance.json").write_text(
    json.dumps(
        {
            "executedHarnessSha256": sha(soak_harness),
            "reports": {name: sha(scratch / name) for name in ("rotation-tmux.json", "rotation-agent.json")},
            "limits": [
                "Report harnessSha256 reads completion-time pathname bytes",
                "Executed harness bytes were captured before that pathname changed",
                "One Reader per domain; shared-authority multi-Reader issue is not exercised",
                "Production handle budget with accelerated proof cadence, not ordinary-cadence multi-hour acceptance",
            ],
        },
        indent=2,
    )
    + "\n"
)

# The new soaks execute an immutable copy. Retain exact measurement versions
# separately from later formatting and diagnostics changes in the source tools.
for name in (
    "profile-fleet-candidate-soak.py",
    "profile-fleet-candidate-retry.py",
    "measure-validator-executed.py",
    "measure-reader-executed.py",
    "measure-processes-executed.py",
    "investigate-refresh-executed.py",
    "accept-process-abort.py",
):
    path = scratch / name
    if path.is_file():
        shutil.copyfile(path, output / name)
for name in ("profile-fleet", "measure-reader", "measure-processes", "investigate-refresh"):
    raw = subprocess.check_output(["git", "show", "504a176:scripts/" + name + ".py"], cwd=root)
    (output / (name + "-checkpoint-504.py")).write_bytes(raw)
(output / "harness-provenance.json").write_text(
    json.dumps(
        {
            "immutableCandidateSoakSha256": sha(scratch / "profile-fleet-candidate-soak.py"),
            "candidateRefreshExecutedSha256": sha(scratch / "investigate-refresh-executed.py"),
            "limits": [
                "Candidate refresh loaded captured pre-format bytes; its reported pathname digest reads later formatting",
                "Initial refresh-mesh-installed harness bytes were not archived; only its recorded digest survives",
                "Checkpoint 504 and executed copies preserve distinct matrix and diagnostic versions",
                "The private native replay inputs are never copied into this evidence",
            ],
        },
        indent=2,
    )
    + "\n"
)
index = {
    path.name: sha(path)
    for path in sorted(output.iterdir())
    if path.is_file() and path.name != "checksums.json"
}
(output / "checksums.json").write_text(json.dumps(index, indent=2) + "\n")
print(json.dumps({"reports": len(reports), "candidateSha256": sha(wheel), "preservation": preservation}))
