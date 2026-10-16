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
    require(lock["lockRevision"] == 5 and lock["status"] == "frozen_for_implementation", "lock disposition")
    require(lock["products"] == ["state"], "unsupported product promoted")
    require(lock["capabilities"] == ["snapshot", "proof", "subscribe"], "unsupported capability promoted")
    require(lock["backends"] == ["ipc", "ssh-stdio", "wss"], "unsupported backend promoted")
    require(lock["meshProtocol"] == 1 and lock["deliveryVersion"] == 1 and
            lock["deliveryProtocol"] == "mesh-plus.delivery-candidate.v1", "protocol binding")
    expected = {"docs/contract-freeze.md", "contracts/mesh-read-v1/contract.md",
                "contracts/mesh-delivery-v1/contract.md"}
    expected.update(str(path.relative_to(ROOT)) for path in READ.glob("*.json")
                    if path.name != "bridge-request.schema.json")
    expected.update("contracts/mesh-delivery-v1/" + name for name in
                    ("client-frame.schema.json", "server-frame.schema.json"))
    expected.update(file["path"] for profile in lock["nativeInputs"].values() for file in profile["schemas"])
    expected.update("contracts/wss-v1/" + name for name in
                    ("contract.md", "registry.schema.json", "authorization.schema.json"))
    expected.update("contracts/agent-profile-v2/" + name for name in ("contract.md", "profile.schema.json"))
    expected.update("contracts/agent-profile-v3/" + name for name in ("contract.md", "profile.schema.json"))
    expected.update("contracts/agent-active-v1/" + name for name in ("contract.md", "profile.schema.json"))
    require(set(lock["normativeDigests"]) == expected, "normative inventory changed")
    require("wss-runtime" not in lock["excluded"], "WSS disposition")
    for name in ("registry", "authorization"):
        require((ROOT / "src/mesh_plus/wss" / (name + ".schema.json")).read_bytes() ==
                (ROOT / "contracts/wss-v1" / (name + ".schema.json")).read_bytes(), "WSS configuration schema drift")
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
    copies["read-agent-v2.profile.schema.json"] = ROOT / "contracts/agent-profile-v2/profile.schema.json"
    copies["read-agent-v3.profile.schema.json"] = ROOT / "contracts/agent-profile-v3/profile.schema.json"
    copies["read-agent-active.profile.schema.json"] = ROOT / "contracts/agent-active-v1/profile.schema.json"
    active = ROOT / "reference/agent-observer-active/agent_observer/contracts"
    copies["agent-active-native.schema.json"] = active / "active-frame.schema.json"
    copies["agent-active-request.schema.json"] = active / "active-request.schema.json"
    packaged = ROOT / "src/mesh_plus/schemas"
    require({path.name for path in packaged.glob("*.json")} == set(copies), "schema copy inventory changed")
    for name, path in copies.items():
        require((packaged / name).read_bytes() == path.read_bytes(), "packaged schema drift: " + name)
    for name in ("tmux", "agent"):
        require(lock["profiles"][name] == name + "-observer.mesh-candidate.v1", "profile binding")
    require(set(lock["profileExtensions"]) == {"agent-observer.mesh-candidate.v2", "agent-observer.mesh-candidate.v3",
                                                "agent-observer.mesh-active.v1"}, "profile extension binding")
    extension = lock["profileExtensions"]["agent-observer.mesh-candidate.v2"]
    require(extension == {"domain": "agent", "sdkInterface": 1, "nativeProtocol": "agent-observer.snapshot",
                          "nativeVersion": 5, "serviceProtocol": 3,
                          "schema": "contracts/agent-profile-v2/profile.schema.json"}, "timing profile disposition")
    native = json.loads((ROOT / "reference/agent-observer-timing/agent_observer/contracts/snapshot.schema.json").read_text())
    profile = json.loads((ROOT / extension["schema"]).read_text())
    require(profile["properties"]["sessions"]["items"] == native["properties"]["sessions"]["items"], "timing native projection")
    extension = lock["profileExtensions"]["agent-observer.mesh-candidate.v3"]
    require(extension == {"domain": "agent", "sdkInterface": 1, "nativeProtocol": "agent-observer.snapshot",
                          "nativeVersion": 6, "serviceProtocol": 4,
                          "schema": "contracts/agent-profile-v3/profile.schema.json"}, "system profile disposition")
    native = json.loads((ROOT / "reference/agent-observer-system/agent_observer/contracts/snapshot.schema.json").read_text())
    profile = json.loads((ROOT / extension["schema"]).read_text())
    require(profile["properties"]["sessions"]["items"] == native["properties"]["sessions"]["items"], "system native projection")
    extension = lock["profileExtensions"]["agent-observer.mesh-active.v1"]
    require(extension == {"domain": "agent", "sdkInterface": 1, "nativeProtocol": "agent-observer.active-feed",
                          "nativeVersion": 1, "schema": "contracts/agent-active-v1/profile.schema.json",
                          "nativeSchema": "reference/agent-observer-active/agent_observer/contracts/active-frame.schema.json",
                          "requestSchema": "reference/agent-observer-active/agent_observer/contracts/active-request.schema.json"},
            "active profile disposition")
    native = json.loads((ROOT / extension["nativeSchema"]).read_text())
    profile = json.loads((ROOT / extension["schema"]).read_text())
    projection = native["properties"]["projection"]["anyOf"][0]
    require(profile["properties"]["sessions"]["items"] == projection["properties"]["sessions"]["items"],
            "active native body projection")
    previous = json.loads((ROOT / "contracts/agent-profile-v3/profile.schema.json").read_text())
    require(profile["properties"]["sessions"]["items"] == previous["properties"]["sessions"]["items"],
            "active changes existing API4 body")
    native_digest = hashlib.sha256((ROOT / extension["nativeSchema"]).read_bytes()).hexdigest()
    require(profile["$comment"] == "Native frame SHA-256: " + native_digest + "; selector " +
            native["properties"]["selectorDigest"]["const"], "active native selector binding")
    owner = profile["properties"]["mesh"]["allOf"][1]["properties"]["hosts"]["items"]["properties"]["owner"]["anyOf"][0]
    require(owner["properties"]["protocol"] == {"const": "agent-observer.active-feed"} and
            owner["properties"]["version"] == {"const": 1}, "active owner binding")
    metadata = owner["properties"]["metadata"]["anyOf"][0]
    require(metadata["properties"] == {"scopes": projection["properties"]["scopes"]} and
            metadata["required"] == ["scopes"] and metadata["additionalProperties"] is False,
            "active owner metadata projection")
    header = owner["properties"]["service"]
    require(header["properties"] == {k: v for k, v in native["properties"].items() if k != "projection"} and
            header["required"] == [k for k in native["required"] if k != "projection"] and
            header["additionalProperties"] is False, "active owner service projection")
    print(f"PASS: {len(expected)} locked inputs, {len(copies)} identical packaged schemas; state core only")


if __name__ == "__main__":
    main()
