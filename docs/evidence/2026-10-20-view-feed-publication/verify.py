"""Verify retained a24 publication evidence; optionally check downloaded assets."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(name: str) -> dict:
    return json.loads((HERE / name).read_text())


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path)
    args = parser.parse_args()
    receipt = read("publication.json")
    review = read("review.json")
    assert digest((HERE / "review.json").read_bytes()) == receipt["sourceReview"]["sha256"]
    assert review["runtimeSource"] == receipt["runtimeSource"]
    for name, record in receipt["artifacts"].items():
        data = (HERE / name).read_bytes()
        assert digest(data) == record["sha256"], name
        assert len(data) == record["size"], name
    for name, record in review["artifacts"].items():
        data = (HERE / name).read_bytes()
        assert digest(data) == record["sha256"], name
        assert len(data) == record["bytes"], name

    # Historical source is checked against its immutable object, not today's tree.
    archive = git("archive", receipt["runtimeSource"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
        for name, expected in review["sources"].items():
            stream = tree.extractfile(name)
            assert stream is not None, name
            assert digest(stream.read()) == expected, name
    assert git("rev-parse", receipt["tag"]).decode().strip() == receipt["tagObject"]
    assert git("rev-parse", receipt["tag"] + "^{}").decode().strip() == receipt["tagCommit"]
    for name in ["branch-ci", "tag-ci"]:
        run = read(name + ".json")
        assert run["headSha"] == receipt["tagCommit"]
        assert run["conclusion"] == "success"
        assert len(run["jobs"]) == 4
        assert all(job["conclusion"] == "success" for job in run["jobs"])

    release = read("public-release.json")
    assert release["tagName"] == receipt["tag"]
    assert release["targetCommitish"] == receipt["tagCommit"]
    assert release["isPrerelease"] and not release["isDraft"]
    expected = {name: record["sha256"] for name, record in receipt["assets"].items()}
    assert {a["name"]: a["digest"] for a in release["assets"]} == {
        name: "sha256:" + value for name, value in expected.items()
    }
    statement = read("release-attestation.json")["verificationResult"]["statement"]
    assert statement["predicate"]["repository"] == "byebyebryan/mesh-plus"
    assert statement["predicate"]["tag"] == receipt["tag"]
    assert statement["subject"][0]["digest"]["sha1"] == receipt["tagObject"]
    assert {s["name"]: s["digest"]["sha256"] for s in statement["subject"][1:]} == expected

    def prior_assets(name: str) -> dict:
        return {
            a["name"]: (a["digest"], a["size"], a["id"])
            for a in read(name)["assets"]
        }

    assert prior_assets("prior-a23-release.json") == prior_assets("prior-a23-after.json")
    observer = read("public-observer.json")
    assert observer["gcEnabled"] is False
    assert len(observer["scenarios"]) == 6
    assert all(s["freshNonces"] == 2 for s in observer["scenarios"])
    installed = read("public-install-check.json")
    assert installed["version"] == "0.1.0a24"
    assert installed["installedRuntimeSchemaFiles"] == 107
    assert installed["optionalObserversInstalled"] is False
    tests = (HERE / "public-feed-tests.log").read_text()
    assert "Ran 40 tests" in tests and tests.rstrip().endswith("OK")

    if args.assets is not None:
        for name, record in receipt["assets"].items():
            data = (args.assets / name).read_bytes()
            assert digest(data) == record["sha256"], name
            assert len(data) == record["size"], name
        for line in (args.assets / "SHA256SUMS").read_text().splitlines():
            expected_hash, name = line.split("  ", 1)
            assert digest((args.assets / name).read_bytes()) == expected_hash, name
        print("PASS: recorded evidence, immutable source/tag and all four supplied assets")
    else:
        print("PASS: recorded evidence and immutable source/tag; assets not supplied")


if __name__ == "__main__":
    main()
