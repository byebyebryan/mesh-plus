"""Export the proposed working-set schemas from one explicit Observer source.

This maintenance tool changes only new working-set reference/package files. It
does not update LOCK.json, older schemas, runtime selections or artifacts.
"""

import argparse
import copy
import hashlib
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def document(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def generated(frame_raw, request_raw):
    native = json.loads(frame_raw)
    projection = native["properties"]["projection"]["anyOf"][0]
    scope = projection["properties"]["scopes"]["items"]
    if "supportTable" not in scope["properties"]:
        raise ValueError("compact_support_table_required")
    profile = json.loads((ROOT / "contracts/agent-active-v1/profile.schema.json").read_text())
    profile["$id"] = "urn:mesh-plus:read:1:agent-working-set-profile"
    profile["$comment"] = (
        "Native frame SHA-256: " + hashlib.sha256(frame_raw).hexdigest()
        + "; selector family; immutable configured window required"
    )
    profile["properties"]["protocol"] = {"const": "agent-observer.mesh-working-set.v1"}
    profile["properties"]["sessions"]["items"] = copy.deepcopy(
        projection["properties"]["sessions"]["items"]
    )
    owner = profile["properties"]["mesh"]["allOf"][1]["properties"]["hosts"]["items"]["properties"]["owner"]["anyOf"][0]
    owner["properties"]["protocol"] = {"const": "agent-observer.working-set"}
    owner["properties"]["version"] = {"const": 1}
    metadata_scopes = copy.deepcopy(projection["properties"]["scopes"])
    # The domain validator independently checks exact canonical uniqueness.
    # The packaged public schema also rejects duplicate complete JSON maps,
    # which Draft202012 can express without owner callbacks.
    metadata_scopes["items"]["properties"]["supportTable"]["uniqueItems"] = True
    owner["properties"]["metadata"] = {"anyOf": [
        {"type": "object", "properties": {"scopes": metadata_scopes},
         "required": ["scopes"], "additionalProperties": False},
        {"type": "null"},
    ]}
    owner["properties"]["service"] = {
        "type": "object",
        "properties": {key: copy.deepcopy(value) for key, value in native["properties"].items()
                       if key != "projection"},
        "required": [key for key in native["required"] if key != "projection"],
        "additionalProperties": False,
    }
    profile_raw = document(profile)
    reference = "reference/agent-observer-working-set/agent_observer/contracts/"
    return {
        reference + "working-set-frame.schema.json": frame_raw,
        reference + "working-set-request.schema.json": request_raw,
        "contracts/agent-working-set-v1/profile.schema.json": profile_raw,
        "src/mesh_plus/schemas/agent-working-set-native.schema.json": frame_raw,
        "src/mesh_plus/schemas/agent-working-set-request.schema.json": request_raw,
        "src/mesh_plus/schemas/read-agent-working-set.profile.schema.json": profile_raw,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if re.fullmatch(r"[0-9a-f]{40}", args.source_revision) is None:
        raise ValueError("exact_source_revision_required")
    sys.path.insert(0, str(args.source_root.resolve()))
    contract = importlib.import_module("agent_observer.working_set_contract")
    if Path(contract.__file__).resolve().parent.parent != args.source_root.resolve():
        raise ValueError("foreign_source_import")
    outputs = generated(document(contract.schema_document("frame")),
                        document(contract.schema_document("request")))
    # A revision label alone is not source provenance. Every imported Observer
    # implementation file must equal that exact Git object before any export.
    # This also catches dirty schema dependencies outside the entry module.
    source_root = args.source_root.resolve()
    imported = {}
    for name, module in tuple(sys.modules.items()):
        if not name.startswith("agent_observer") or not getattr(module, "__file__", None):
            continue
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(source_root) or path.suffix != ".py":
            raise ValueError("foreign_source_dependency:" + name)
        relative = path.relative_to(source_root).as_posix()
        expected = subprocess.run(
            ["git", "-C", str(source_root), "show", args.source_revision + ":" + relative],
            check=True, capture_output=True,
        ).stdout
        actual = path.read_bytes()
        if expected != actual:
            raise ValueError("source_revision_mismatch:" + relative)
        imported[relative] = hashlib.sha256(actual).hexdigest()
    for name, raw in outputs.items():
        path = args.output_root / name
        if args.check:
            if path.read_bytes() != raw:
                raise ValueError("working_set_schema_drift:" + name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print(json.dumps({"sourceRevision": args.source_revision, "checkOnly": args.check,
                      "sourceInputs": imported,
                      "files": {name: hashlib.sha256(raw).hexdigest()
                                for name, raw in outputs.items()}}, indent=2))


if __name__ == "__main__":
    main()
