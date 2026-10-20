"""Verify the additive feed lock, independent vectors and packaged schema."""

import hashlib
import importlib.util
import json
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "view-feed-v1"


def main():
    lock = json.loads((CONTRACT / "LOCK.json").read_text())
    for name, expected in lock["sha256"].items():
        path = CONTRACT / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, name
    raw = files("mesh_plus.view_feed").joinpath("packet.schema.json").read_bytes()
    assert raw == (CONTRACT / "packet.schema.json").read_bytes(), "packaged feed schema"
    validator = Draft202012Validator(json.loads(raw))
    fixture = json.loads((CONTRACT / "vectors.json").read_text())
    for case in fixture["positive"]:
        validator.validate(case["packet"])
    spec = importlib.util.spec_from_file_location("view_feed_reference", CONTRACT / "reference.py")
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    result = reference.run()
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
