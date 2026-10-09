"""Generate candidate delivery schemas and synthetic examples, not a runtime API."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/mesh-delivery-v1"
PREFIX = "urn:mesh-plus:delivery:candidate:1:"
PROTOCOL = "mesh-plus.delivery-candidate.v1"
MAX_INT = 2**53 - 1
MAX_MESSAGE = 8 * 1024 * 1024 + 16384 + 65536


def obj(**fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}


def text(limit=128, pattern=None):
    value = {"type": "string", "minLength": 1, "maxLength": limit}
    if pattern:
        value["pattern"] = pattern
    return value


def integer(minimum=0, maximum=MAX_INT):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def enum(*values):
    return {"enum": list(values)}


def nullable(value):
    return {"anyOf": [value, {"type": "null"}]}


def array(value, maximum=32):
    return {"type": "array", "items": value, "maxItems": maximum, "uniqueItems": True}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


TOKEN = text(128, r"^[a-z][a-z0-9_.-]*$")
HOST = text(16384, r"^[a-z0-9][a-z0-9_.-]*$")
ID = text(64, r"^[a-zA-Z0-9_-]+$")
NONCE = text(64, r"^[0-9a-f]{32,64}$")
UUID = text(36, r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
DIGEST = text(71, r"^sha256:[0-9a-f]{64}$")
OPAQUE = {"type": "object"}
ERROR = obj(code=TOKEN, message={"type": "string", "maxLength": 1024})
LIMITS = obj(maxMessageBytes=integer(1024, MAX_MESSAGE), maxOutstanding=integer(1, 8),
             maxSubscriptions=integer(1, 8))
CREDIT = obj(frames=integer(), bytes=integer())
START = obj(mode=enum("baseline", "live", "retained", "after"), cursor=nullable(OPAQUE))
PRODUCT = enum("state", "events")
CAPABILITY = enum("snapshot", "proof", "subscribe", "digest-proof", "status", "replay")
ENVELOPE = {"protocol": {"const": PROTOCOL}, "version": {"const": 1}, "sequence": integer(1)}


def hello(**fields):
    return obj(**ENVELOPE, kind={"const": "hello"}, **fields)


def frame(kind, **fields):
    return obj(**ENVELOPE, kind={"const": kind}, channelId=UUID, **fields)


def main():
    client = {"oneOf": [
        hello(helloNonce=NONCE, expectedHost=HOST, sourceId=TOKEN, product=PRODUCT,
              profile=TOKEN, requiredCapabilities=array(CAPABILITY), limits=LIMITS),
        frame("request", requestId=ID, operation=enum("snapshot", "proof", "status"),
              timeoutMs=integer(1, 60000), parameters=OPAQUE),
        frame("subscribe", subscriptionId=ID, start=START, credit=CREDIT),
        frame("credit", subscriptionId=ID, credit=CREDIT),
        frame("cancel", handleId=ID, handleType=enum("request", "subscription")),
        frame("close", reason=enum("client_done", "protocol_error")),
    ]}
    server = {"oneOf": [
        hello(helloNonce=NONCE, channelId=UUID, hostId=HOST, sourceId=TOKEN,
              product=PRODUCT, profile=TOKEN, capabilities=array(CAPABILITY), limits=LIMITS),
        frame("result", requestId=ID, outcome=enum("ok", "error"),
              payload=nullable(OPAQUE), error=nullable(ERROR)),
        frame("subscribed", subscriptionId=ID, start=START, barrier=OPAQUE, publisherEpoch=ID),
        frame("data", subscriptionId=ID, streamSequence=integer(1), publisherEpoch=ID,
              deliveryKind=enum("view", "resync", "event"), cursor=nullable(OPAQUE), payload=OPAQUE),
        frame("control", subscriptionId=nullable(ID), streamSequence=nullable(integer(1)),
              control=enum("heartbeat", "gap", "checkpoint", "source_status"), payload=OPAQUE),
        frame("ended", handleId=ID, handleType=enum("request", "subscription"),
              reason=enum("cancelled", "deadline", "gap", "publisher_restart", "unsupported", "completed"),
              cursor=nullable(OPAQUE)),
        frame("error", error=ERROR),
    ]}
    receipt = obj(sourceId=text(256), component=TOKEN, health=enum("current", "partial", "stale", "warming", "unavailable"),
                  accepted=integer(), originalExpiryMs=nullable(integer()), remainingMs=integer())
    compact = obj(kind={"const": "digest-proof"}, nonce=NONCE, ownerDigest=DIGEST,
                  hostId=HOST, sourceId=TOKEN, ownerEpoch=ID,
                  clock=obj(bootId=UUID, timeNamespace=text(128, r"^time:[0-9]+$")),
                  evaluatedAtMs=integer(), receipts=array(receipt))
    endpoint_common = {"registryProtocol": {"const": "mesh-plus.endpoints-candidate.v1"},
                       "revision": DIGEST, "endpointId": ID, "hostId": HOST, "sourceId": TOKEN,
                       "product": PRODUCT, "profile": TOKEN, "authRef": ID}
    endpoint = {"oneOf": [
        obj(**endpoint_common, backend={"const": "ipc"}, address=obj(path=text(4096))),
        obj(**endpoint_common, backend={"const": "ssh-stdio"},
            address=obj(hostMeshRevision=DIGEST, routeToken=DIGEST)),
        obj(**endpoint_common, backend={"const": "wss"}, address=obj(url=text(4096, r"^wss://"))),
    ]}
    for name, schema in [("client-frame", client), ("server-frame", server), ("digest-proof", compact), ("endpoint", endpoint)]:
        write(BASE / (name + ".schema.json"), {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": PREFIX + name, **schema})

    nonce = "1" * 32
    channel = "11111111-1111-4111-8111-111111111111"
    limits = {"maxMessageBytes": MAX_MESSAGE, "maxOutstanding": 8, "maxSubscriptions": 8}
    common = {"protocol": PROTOCOL, "version": 1}
    c = {**common, "kind": "hello", "sequence": 1, "helloNonce": nonce,
         "expectedHost": "fixture-host", "sourceId": "synthetic", "product": "state",
         "profile": "mesh-plus.synthetic.state.v1", "requiredCapabilities": ["snapshot", "subscribe"], "limits": limits}
    s = {**common, "kind": "hello", "sequence": 1, "helloNonce": nonce, "channelId": channel,
         "hostId": c["expectedHost"], "sourceId": c["sourceId"], "product": c["product"],
         "profile": c["profile"], "capabilities": ["snapshot", "subscribe", "proof", "digest-proof"], "limits": limits}
    post = {**common, "channelId": channel}
    examples = {
        "client-hello": c, "server-hello": s,
        "client-request": {**post, "kind": "request", "sequence": 2, "requestId": "r1", "operation": "snapshot", "timeoutMs": 2000, "parameters": {}},
        "client-subscribe": {**post, "kind": "subscribe", "sequence": 3, "subscriptionId": "s1", "start": {"mode": "baseline", "cursor": None}, "credit": {"frames": 8, "bytes": 2 * MAX_MESSAGE}},
        "client-credit": {**post, "kind": "credit", "sequence": 4, "subscriptionId": "s1", "credit": {"frames": 9, "bytes": 2 * MAX_MESSAGE + 1024}},
        "client-cancel": {**post, "kind": "cancel", "sequence": 5, "handleId": "s1", "handleType": "subscription"},
        "client-close": {**post, "kind": "close", "sequence": 6, "reason": "client_done"},
        "server-result": {**post, "kind": "result", "sequence": 2, "requestId": "r1", "outcome": "ok", "payload": {"synthetic": True}, "error": None},
        "server-subscribed": {**post, "kind": "subscribed", "sequence": 3, "subscriptionId": "s1", "start": {"mode": "baseline", "cursor": None}, "barrier": {"view": 1}, "publisherEpoch": "publisher_1"},
        "server-data": {**post, "kind": "data", "sequence": 4, "subscriptionId": "s1", "streamSequence": 1, "publisherEpoch": "publisher_1", "deliveryKind": "view", "cursor": None, "payload": {"synthetic": True, "view": 1}},
        "server-heartbeat": {**post, "kind": "control", "sequence": 5, "subscriptionId": "s1", "streamSequence": 2, "control": "heartbeat", "payload": {}},
        "server-gap": {**post, "kind": "control", "sequence": 6, "subscriptionId": "s1", "streamSequence": 3, "control": "gap", "payload": {"gapKind": "delivery"}},
        "server-resync": {**post, "kind": "data", "sequence": 7, "subscriptionId": "s1", "streamSequence": 4, "publisherEpoch": "publisher_1", "deliveryKind": "resync", "cursor": None, "payload": {"synthetic": True, "view": 4}},
        "server-ended": {**post, "kind": "ended", "sequence": 8, "handleId": "s1", "handleType": "subscription", "reason": "cancelled", "cursor": None},
        "server-error": {**post, "kind": "error", "sequence": 9, "error": {"code": "unsupported", "message": "Source product is not configured"}},
        "compact-proof": {"kind": "digest-proof", "nonce": nonce, "ownerDigest": "sha256:" + "a" * 64, "hostId": "fixture-host", "sourceId": "synthetic", "ownerEpoch": "publisher_1", "clock": {"bootId": channel, "timeNamespace": "time:1"}, "evaluatedAtMs": 1000, "receipts": [{"sourceId": "synthetic", "component": "native", "health": "current", "accepted": 7, "originalExpiryMs": 10000, "remainingMs": 9000}]},
    }
    for product in ["state", "events"]:
        for backend in ["ipc", "ssh-stdio", "wss"]:
            addresses = {"ipc": {"path": "/run/user/1000/mesh-plus/fixture.sock"}, "ssh-stdio": {"hostMeshRevision": "sha256:" + "b" * 64, "routeToken": "sha256:" + "c" * 64}, "wss": {"url": "wss://fixture.example/mesh"}}
            examples["endpoint-" + backend + "-" + product] = {"registryProtocol": "mesh-plus.endpoints-candidate.v1", "revision": "sha256:" + "d" * 64, "endpointId": backend.replace("-", "_") + "_" + product, "hostId": "fixture-host", "sourceId": "synthetic", "product": product, "profile": "mesh-plus.synthetic." + product + ".v1", "authRef": "configured_principal", "backend": backend, "address": addresses[backend]}
    events = {**c, "product": "events", "profile": "mesh-plus.synthetic.events.v1", "requiredCapabilities": ["subscribe", "replay"]}
    examples["client-events-hello"] = events
    examples["client-events-after"] = {**examples["client-subscribe"], "start": {"mode": "after", "cursor": {"epoch": "publisher_1", "sequence": 20}}}
    examples["server-event"] = {**examples["server-data"], "deliveryKind": "event", "cursor": {"epoch": "publisher_1", "sequence": 21}, "payload": {"synthetic": True, "eventId": "receipt_21"}}
    for name, value in examples.items():
        write(BASE / "examples" / (name + ".json"), value)


if __name__ == "__main__":
    main()
