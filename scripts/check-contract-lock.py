"""Verify reviewed normative inputs and packaged schema parity without producers."""

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
READ = ROOT / "contracts/mesh-read-v1"
DELIVERY = ROOT / "contracts/mesh-delivery-v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    lock = json.loads((ROOT / "contracts/LOCK.json").read_text())
    require(lock["lockRevision"] == 1 and lock["status"] == "frozen_for_implementation", "lock disposition")
    require(lock["products"] == ["state"], "unsupported product promoted")
    require(lock["capabilities"] == ["snapshot", "proof", "subscribe"], "unsupported capability promoted")
    require(lock["backends"] == ["ipc", "ssh-stdio"], "unsupported backend promoted")
    require(lock["meshProtocol"] == 1 and lock["deliveryVersion"] == 1 and
            lock["deliveryProtocol"] == "mesh-plus.delivery-candidate.v1", "protocol binding")
    expected = {"docs/contract-freeze.md", "contracts/mesh-read-v1/contract.md",
                "contracts/mesh-delivery-v1/contract.md"}
    expected.update(str(path.relative_to(ROOT)) for path in READ.glob("*.json")
                    if path.name != "bridge-request.schema.json")
    expected.update("contracts/mesh-delivery-v1/" + name for name in
                    ("client-frame.schema.json", "server-frame.schema.json"))
    expected.update(file["path"] for profile in lock["nativeInputs"].values() for file in profile["schemas"])
    require(set(lock["normativeDigests"]) == expected, "normative inventory changed")
    for profile in lock["nativeInputs"].values():
        for file in profile["schemas"]:
            require(lock["normativeDigests"][file["path"]] == file["sha256"], "native schema binding")
    for name, wanted in lock["normativeDigests"].items():
        path = ROOT / name
        require(path.is_relative_to(ROOT) and ".." not in Path(name).parts, "unsafe lock path")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == wanted, "unreviewed contract drift: " + name)
        if path.suffix == ".json":
            Draft202012Validator.check_schema(json.loads(path.read_text()))
    copies = {}
    for path in READ.glob("*.json"):
        target = "read-" + ("schema.json" if path.name == "schema.json" else path.name)
        copies[target] = path
        if path.name == "bridge-reply.schema.json":
            copies[path.name] = path
    copies.update({path.name: path for path in DELIVERY.glob("*.json")})
    host = ROOT / "reference/rofi-ssh-plus/contracts/host-mesh-v1/schemas"
    copies.update({"host-" + path.name: path for path in host.glob("*.json")})
    copies["tmux-native.schema.json"] = ROOT / "reference/tmux-observer/contracts/observation-v1/schema.json"
    packaged = ROOT / "src/mesh_plus/schemas"
    require({path.name for path in packaged.glob("*.json")} == set(copies), "schema copy inventory changed")
    for name, path in copies.items():
        require((packaged / name).read_bytes() == path.read_bytes(), "packaged schema drift: " + name)
    for name in ("tmux", "agent"):
        require(lock["profiles"][name] == name + "-observer.mesh-candidate.v1", "profile binding")
    print(f"PASS: {len(expected)} locked inputs, {len(copies)} identical packaged schemas; state core only")


if __name__ == "__main__":
    main()
