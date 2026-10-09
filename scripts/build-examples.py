"""Build design schemas and synthetic examples from frozen public fixtures.

This is design tooling, not a Mesh networking or Observer implementation.
"""

import copy
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/mesh-read-v1"
MAX_INT = 2**53 - 1
PREFIX = "urn:mesh-plus:read:1:"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load(repo, path):
    return json.loads((ROOT / "reference" / repo / path).read_text())


def obj(**properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def nullable(schema):
    return {"anyOf": [schema, {"type": "null"}]}


def enum(*values):
    return {"enum": list(values)}


def array(item, maximum=128, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}


def string(maximum=256, pattern=None):
    value = {"type": "string", "minLength": 1, "maxLength": maximum}
    if pattern:
        value["pattern"] = pattern
    return value


def schema(name, value):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": PREFIX + name, **value}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


INTEGER = {"type": "integer", "minimum": 0, "maximum": MAX_INT}
HOST = string(16384, r"^[a-z0-9][a-z0-9_.-]*$")
TOKEN = string(128, r"^[a-z][a-z0-9_]{0,127}$")
NONCE = string(64, r"^[0-9a-f]{32,64}$")
UUID = string(36, r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
DIGEST = string(71, r"^sha256:[0-9a-f]{64}$")
CLOCK = obj(bootId=UUID, timeNamespace=string(128, r"^time:[0-9]+$"))
ERROR = obj(code=TOKEN, message={"type": "string", "maxLength": 4096})
EXTENSIONS = {"type": "object"}
RECEIPT = obj(sourceId=string(), component=TOKEN,
              health=enum("current", "partial", "stale", "warming", "unavailable"),
              accepted=INTEGER, remainingMs=INTEGER, expiresAtMs=nullable(INTEGER))
PROOF = obj(nonce=NONCE, bridgeId=UUID, bridgeClock=CLOCK, bridgeEncodedAtMs=INTEGER,
            sentAtMs=INTEGER, receivedAtMs=INTEGER,
            marginMs={"type": "integer", "minimum": 100, "maximum": 2000},
            payloadDigest=DIGEST)
OWNER = obj(protocol=string(), version=INTEGER,
            metadata=nullable({"type": "object"}), service=nullable({"type": "object"}))
DELIVERY = obj(path=enum("ipc", "ssh", "wss"),
               status=enum("ready", "connecting", "unavailable", "incompatible", "invalid"),
               epoch=INTEGER, routeToken=nullable(DIGEST),
               error=nullable(ERROR), proof=nullable(PROOF))
HOST_RESULT = obj(hostId=HOST, local={"type": "boolean"}, delivery=DELIVERY,
                  viewState=enum("current", "historical", "warming", "unavailable"),
                  owner=nullable(OWNER), receipts=array(RECEIPT, 32))
MESH = obj(meshProtocol={"const": 1}, requestId=NONCE,
           operation=enum("snapshot", "watch"), access={"const": "cached"},
           scope=obj(hostIds={**array(HOST, 16, 1), "uniqueItems": True}),
           catalog=obj(state=enum("ready", "local_only"), revision=nullable(DIGEST), localHostId=HOST),
           reader=obj(id=UUID, clock=CLOCK, encodedAtMs=INTEGER,
                      sequence={"type": "integer", "minimum": 1, "maximum": MAX_INT}, revision=INTEGER),
           kind=enum("view", "resync"),
           status=enum("complete", "partial", "pending", "unavailable"),
           hosts=array(HOST_RESULT, 16, 1), extensions=EXTENSIONS)
SELECTION = obj(mode=enum("local", "fleet", "hosts"),
                hostIds={**array(HOST, 16), "uniqueItems": True})
REQUEST = obj(meshProtocol={"const": 1}, requestId=NONCE, profile=string(),
              operation=enum("snapshot", "watch"), access={"const": "cached"},
              selection=SELECTION, extensions=EXTENSIONS)
BRIDGE_REQUEST = obj(meshProtocol={"const": 1}, nonce=NONCE,
                     sourceId=TOKEN, operation=enum("proof", "watch"), expectedHost=HOST)
REMAINING = obj(sourceId=string(), component=TOKEN,
                health=enum("current", "partial", "stale", "warming", "unavailable"),
                accepted=INTEGER, remainingMs=INTEGER)
BRIDGE_REPLY = obj(meshProtocol={"const": 1}, kind=enum("proof", "candidate", "heartbeat", "gap", "error"),
                   nonce=nullable(NONCE), bridgeId=UUID,
                   sequence={"type": "integer", "minimum": 1, "maximum": MAX_INT},
                   sourceId=TOKEN, hostId=HOST, clock=CLOCK, encodedAtMs=INTEGER,
                   ownerFrame=nullable({"type": "object"}), ownerDigest=nullable(DIGEST),
                   remaining=array(REMAINING, 32), error=nullable(ERROR))
CONTROL = obj(protocol=string(), schemaVersion={"const": 1},
              mesh=obj(meshProtocol={"const": 1}, requestId=NONCE,
                       operation={"const": "watch"}, access={"const": "cached"},
                       reader=MESH["properties"]["reader"], kind=enum("heartbeat", "gap")))


def owner_snapshot(domain, empty=False):
    if domain == "tmux":
        return load("tmux-observer", "contracts/observation-v1/fixtures/" +
                    ("no-server.json" if empty else "complete.json"))
    snap = load("agent-observer", "tests/fixtures/contract-v4/claude-interactive.json")
    if empty:
        snap["sessions"] = []
    return snap


def frame_for(domain, snapshot):
    if domain == "tmux":
        frame = load("tmux-observer", "contracts/service-v1/fixtures/ready.json")
        frame["snapshot"] = snapshot
        return frame
    sources = [{k: s[k] for k in ("provider", "namespace", "configHome", "configHomeKind")}
               for s in snapshot["sources"]]
    for source in sources:
        source["contextGeneration"] = 1
        source["components"] = [
            {"name": component, "attempts": 1, "accepted": 1, "sampledBoottimeMs": 100,
             "expiresBoottimeMs": expiry, "health": "current", "lastResult": "complete",
             "inFlight": False}
            for component, expiry in [("runtime", 90100), ("history", 360100)]]
    return {"serviceProtocol": 2, "serviceId": "11111111-1111-4111-8111-111111111111",
            "bootId": "00000000-0000-0000-0000-000000000001", "uid": 1000,
            "hostScope": snapshot["host"]["authority"], "sequence": 1, "viewRevision": 1,
            "kind": "status", "state": "ready", "emittedAt": 1700000020000,
            "emittedBoottimeMs": 1000, "clock": "boottime", "clockDomain": "time:[42]",
            "reason": "native_snapshot", "sources": sources, "snapshot": snapshot}


def host_id(domain, snapshot):
    return snapshot["source"]["hostId"] if domain == "tmux" else snapshot["host"]["authority"]


def origin_clock(domain, frame):
    if domain == "tmux":
        return frame["clock"]
    match=re.fullmatch(r"time:\[([0-9]+)\]",frame["clockDomain"])
    if match is None:
        raise ValueError("unsupported source clock encoding")
    return {"bootId": frame["bootId"], "timeNamespace": "time:"+match[1]}


def native_receipts(domain, frame, encoded_at):
    if domain == "tmux":
        r = frame["receipt"]
        return [{"sourceId": "default", "component": "native", "health": "current",
                 "accepted": r["accepted"], "remainingMs": max(0, r["expiresAt"]-encoded_at),
                 "expiresAtMs": r["expiresAt"]}]
    return [{"sourceId": s["provider"] + ":" + s["namespace"], "component": c["name"],
             "health": c["health"], "accepted": c["accepted"],
             "remainingMs": max(0, c["expiresBoottimeMs"] - encoded_at),
             "expiresAtMs": c["expiresBoottimeMs"]}
            for s in frame["sources"] for c in s["components"]]


def build(domain, *, fleet=False, empty=False, failed=False, warming=False, historical=False):
    snap = owner_snapshot(domain, empty)
    frame = frame_for(domain, snap)
    hid = host_id(domain, snap)
    metadata = {k: v for k, v in snap.items() if k != "sessions"}
    header = {k: v for k, v in frame.items() if k != "snapshot"}
    receipt = native_receipts(domain, frame, 2000)
    host = {"hostId": hid, "local": True,
            "delivery": {"path": "ipc", "status": "ready", "epoch": 1,
                         "routeToken": None, "error": None, "proof": None},
            "viewState": "current", "owner": {"protocol": "tmux-observer.observation.v1" if domain == "tmux" else "agent-observer.snapshot",
                                               "version": 1 if domain == "tmux" else 4,
                                               "metadata": metadata, "service": header}, "receipts": receipt}
    rows = copy.deepcopy(snap["sessions"])
    if warming:
        if domain == "tmux":
            warm = load("tmux-observer", "contracts/service-v1/fixtures/warming.json")
        else:
            warm = copy.deepcopy(frame)
            warm.update(state="warming", reason="service_warming", snapshot=None)
            for source in warm["sources"]:
                for c in source["components"]:
                    c.update(attempts=0, accepted=0, sampledBoottimeMs=None,
                             expiresBoottimeMs=None, health="warming", lastResult="none")
        host.update(viewState="warming", receipts=[])
        host["owner"].update(metadata=None, service={k: v for k, v in warm.items() if k != "snapshot"})
        rows = []
    if historical:
        host["viewState"] = "historical"
        host["delivery"].update(status="unavailable", error={"code": "disconnected", "message": "Read channel ended"})
        for r in host["receipts"]:
            r.update(health="stale", remainingMs=0, expiresAtMs=None)
    hosts = [host]
    if fleet:
        remote = copy.deepcopy(host)
        remote["hostId"] = "fixture-remote"
        remote["local"] = False
        remote["delivery"].update(path="ssh", routeToken="sha256:" + "a"*64)
        if failed:
            remote["delivery"].update(status="unavailable", error={"code": "timeout", "message": "Setup deadline exceeded"})
            remote.update(viewState="unavailable", owner=None, receipts=[])
        else:
            rem_rows = copy.deepcopy(snap["sessions"])
            rem_meta = remote["owner"]["metadata"]
            rem_service = remote["owner"]["service"]
            if domain == "tmux":
                rem_meta["source"].update(hostId="fixture-remote", nativeHostname="fixture-remote")
                rem_service["source"].update(hostId="fixture-remote", nativeHostname="fixture-remote")
                for row in rem_rows:
                    row["hostId"] = "fixture-remote"
            else:
                rem_meta["host"].update(authority="fixture-remote", nativeHostname="fixture-remote")
                rem_service["hostScope"] = "fixture-remote"
                for row in rem_rows:
                    row["identity"]["hostScope"] = "fixture-remote"
            # Use a distinct remote BOOTTIME origin while preserving lease length.
            offset = 1_000_000
            if domain == "tmux":
                rem_meta["clock"]["timeNamespace"] = "time:20"
                rem_service["clock"]["timeNamespace"] = "time:20"
                rem_service["encodedAt"] += offset
                for key in ["startedAt", "acceptedAt", "expiresAt", "lastAttemptAt"]:
                    rem_service["receipt"][key] += offset
                for key in ["startedAt", "finishedAt"]:
                    rem_meta["sample"][key] += offset
            else:
                rem_service["clockDomain"] = "time:[43]"
                rem_service["emittedBoottimeMs"] += offset
                for source in rem_service["sources"]:
                    for c in source["components"]:
                        c["sampledBoottimeMs"] += offset
                        c["expiresBoottimeMs"] += offset
            owner_frame = {**rem_service, "snapshot": {**rem_meta, "sessions": rem_rows}}
            proof = {"nonce": "2"*32, "bridgeId": "22222222-2222-4222-8222-222222222222",
                     "bridgeClock": origin_clock(domain, owner_frame), "bridgeEncodedAtMs": offset + 1000,
                     "sentAtMs": 1800, "receivedAtMs": 2000, "marginMs": 100,
                     "payloadDigest": digest(owner_frame)}
            remote["delivery"]["proof"] = proof
            encoded = proof["bridgeEncodedAtMs"]
            remote["receipts"] = native_receipts(domain, owner_frame, encoded)
            for r in remote["receipts"]:
                r["expiresAtMs"] = 2000 + max(0, r["remainingMs"] - 200 - 100)
            rows += rem_rows
        hosts.append(remote)
    ready = sum(h["delivery"]["status"] == "ready" for h in hosts)
    status = "complete" if ready == len(hosts) else "partial" if ready else "unavailable"
    return {"protocol": domain + "-observer.mesh-candidate.v1", "schemaVersion": 1,
            "mesh": {"meshProtocol": 1, "requestId": "1"*32, "operation": "snapshot", "access": "cached",
                     "scope": {"hostIds": [h["hostId"] for h in hosts]},
                     "catalog": {"state": "ready" if fleet else "local_only",
                                 "revision": "sha256:" + "b"*64 if fleet else None, "localHostId": hid},
                     "reader": {"id": "33333333-3333-4333-8333-333333333333",
                                "clock": origin_clock(domain, frame), "encodedAtMs": 2000, "sequence": 1, "revision": 1},
                     "kind": "view", "status": status, "hosts": hosts, "extensions": {}},
            "sessions": rows}


def main():
    write(BASE / "schema.json", schema("mesh", MESH))
    write(BASE / "request.schema.json", schema("request", REQUEST))
    write(BASE / "error.schema.json", schema("error", obj(meshProtocol={"const": 1}, requestId=nullable(NONCE), error=ERROR)))
    write(BASE / "bridge-request.schema.json", schema("bridge-request", BRIDGE_REQUEST))
    write(BASE / "bridge-reply.schema.json", schema("bridge-reply", BRIDGE_REPLY))
    write(BASE / "control.schema.json", schema("control", CONTROL))
    for domain in ["tmux", "agent"]:
        native_schema = load("tmux-observer", "contracts/observation-v1/schema.json") if domain == "tmux" else load("agent-observer", "agent_observer/contracts/snapshot.schema.json")
        item = ({"$ref": native_schema["$id"] + "#/$defs/Session"} if domain == "tmux" else native_schema["properties"]["sessions"]["items"])
        profile = obj(protocol={"const": domain + "-observer.mesh-candidate.v1"}, schemaVersion={"const": 1},
                      mesh={"$ref": PREFIX + "mesh"}, sessions=array(item, 65536))
        write(BASE / (domain + ".profile.schema.json"), schema(domain + "-profile", profile))
        write(BASE / (domain + ".stream.schema.json"), schema(domain + "-stream", {"anyOf": [
            {"$ref": PREFIX + domain + "-profile"},
            {"allOf": [{"$ref": PREFIX + "control"}, {"properties": {"protocol": {"const": domain + "-observer.mesh-candidate.v1"}}}]},
            {"$ref": PREFIX + "error"}]}))
        for name, kwargs in [("local", {}), ("fleet", {"fleet": True}), ("partial-host", {"fleet": True, "failed": True}),
                             ("empty", {"empty": True}), ("warming", {"warming": True}), ("historical", {"historical": True})]:
            write(BASE / "examples" / f"{domain}-{name}.json", build(domain, **kwargs))
        alternative = build(domain, fleet=True)
        alternative["mesh"]["hosts"][1]["delivery"]["path"] = "wss"
        write(BASE / "examples" / f"{domain}-wss-fleet.json", alternative)
    write(BASE / "examples/request-local.json", {"meshProtocol": 1, "requestId": "1"*32,
          "profile": "agent-observer.mesh-candidate.v1", "operation": "snapshot", "access": "cached",
          "selection": {"mode": "local", "hostIds": []}, "extensions": {}})
    write(BASE / "examples/request-hosts.json", {"meshProtocol": 1, "requestId": "1"*32,
          "profile": "tmux-observer.mesh-candidate.v1", "operation": "watch", "access": "cached",
          "selection": {"mode": "hosts", "hostIds": ["fixture-local", "fixture-remote"]}, "extensions": {}})
    write(BASE / "examples/request-error.json", {"meshProtocol": 1, "requestId": "1"*32,
          "error": {"code": "unknown_host", "message": "Selected host is not configured"}})
    request = {"meshProtocol": 1, "nonce": "2"*32, "sourceId": "agent_default", "operation": "proof", "expectedHost": "fixture-remote"}
    write(BASE / "examples/bridge-request.json", request)
    view = build("agent", fleet=True)
    host = view["mesh"]["hosts"][1]
    rows = [r for r in view["sessions"] if r["identity"]["hostScope"] == host["hostId"]]
    frame = {**host["owner"]["service"], "snapshot": {**host["owner"]["metadata"], "sessions": rows}}
    reply={"meshProtocol": 1, "kind":"proof", "nonce": "2"*32,
          "bridgeId": host["delivery"]["proof"]["bridgeId"], "sequence": 1,
          "sourceId": "agent_default", "hostId": host["hostId"], "clock": origin_clock("agent", frame),
          "encodedAtMs": host["delivery"]["proof"]["bridgeEncodedAtMs"], "ownerFrame": frame, "ownerDigest": digest(frame),
          "remaining": [{k: v for k, v in r.items() if k != "expiresAtMs"} for r in host["receipts"]], "error": None}
    write(BASE / "examples/bridge-reply.json", reply)
    candidate={**reply,"kind":"candidate","nonce":None,"remaining":[],"sequence":2}
    write(BASE / "examples/bridge-candidate.json", candidate)
    write(BASE / "examples/bridge-heartbeat.json", {**candidate,"kind":"heartbeat","sequence":3,
          "ownerFrame":None,"ownerDigest":None})
    local=build("agent")
    write(BASE / "examples/control-heartbeat.json", {"protocol":local["protocol"],"schemaVersion":1,
          "mesh":{"meshProtocol":1,"requestId":"1"*32,"operation":"watch","access":"cached",
                  "reader":{**local["mesh"]["reader"],"sequence":2,"encodedAtMs":2001},"kind":"heartbeat"}})
    print("Built ten candidate schemas and twenty-two synthetic examples")


if __name__ == "__main__":
    main()
