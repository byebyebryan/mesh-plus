"""Read-only verification of this source/evidence checkpoint."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def hashed(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(root, commit, name):
    return subprocess.check_output(["git", "-C", str(root), "show", commit + ":" + name])


def main():
    receipt = json.loads((HERE / "receipt.json").read_text())
    for name, expected in receipt["artifacts"].items():
        raw = (HERE / name).read_bytes()
        assert len(raw) == expected["bytes"] and hashed(raw) == expected["sha256"], name
    for name, expected in receipt["sources"].items():
        assert hashed(blob(ROOT, receipt["runtimeCommit"], name)) == expected, name
    observer = Path(receipt["observerRoot"])
    for name, expected in receipt["loadedObserverInputs"].items():
        name = name.removeprefix("observer/")
        assert hashed(blob(observer, receipt["observerCommit"], name)) == expected, name
    for artifact in (receipt["wheel"], receipt["beforeWitness"]):
        assert hashed((ROOT / artifact["path"]).read_bytes()) == artifact["sha256"]
    print("PASS: recorded artifacts, immutable Mesh/Observer source objects and private wheels")


if __name__ == "__main__":
    main()
