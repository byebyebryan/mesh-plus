"""Read-only verification of retained pre-wrap bytes, objects and artifacts."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def verify(path, expected):
    data = path.read_bytes()
    assert len(data) == expected["bytes"], path
    assert hashlib.sha256(data).hexdigest() == expected["sha256"], path


def main():
    receipt = json.loads((HERE / "receipt.json").read_text())
    preserved = [p for p in receipt["preWrapTrackedFiles"] if p["preservedUnchanged"]]
    for item in preserved:
        verify(ROOT / item["path"], item)
    for item in receipt["retainedWheels"]:
        verify(ROOT / item["path"], item)
    for item in receipt["externalCacheReviewPins"]:
        verify(Path(item["path"]), item)
    for item in receipt["preWrapRefs"]:
        current = git("rev-parse", item["ref"])
        if item["ref"] == "refs/heads/" + receipt["owningBranch"]:
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", item["commit"], current],
                cwd=ROOT, check=True,
            )
        else:
            assert current == item["object"], item["ref"]
    for commit in receipt["protectedAncestorCommits"]:
        assert git("cat-file", "-t", commit) == "commit", commit
    print(json.dumps({
        "preservedTrackedFiles": len(preserved),
        "retainedWheels": len(receipt["retainedWheels"]),
        "externalCacheReviewPins": len(receipt["externalCacheReviewPins"]),
        "protectedRefs": len(receipt["preWrapRefs"]),
        "protectedCommits": len(receipt["protectedAncestorCommits"]),
        "status": "PASS; read-only preservation audit, no producer acceptance",
    }, indent=2))


if __name__ == "__main__":
    main()
