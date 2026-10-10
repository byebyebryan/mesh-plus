"""Pure design oracles. These are not a production Mesh session implementation."""

import hashlib
import json
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "contracts/mesh-delivery-v1"
MAX_MESSAGE = 8 * 1024 * 1024 + 16384 + 65536
MAX_CREDIT_BYTES = 2 * MAX_MESSAGE
MAX_CREDIT_FRAMES = 32
VALIDATORS = {}


def require(condition, code):
    if not condition:
        raise ValueError(code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(encoded(value)).hexdigest()


def validate(value, name):
    if name not in VALIDATORS:
        schema = json.loads((BASE / (name + ".schema.json")).read_text())
        Draft202012Validator.check_schema(schema)
        VALIDATORS[name] = Draft202012Validator(schema)
    VALIDATORS[name].validate(value)
    require(len(encoded(value)) <= MAX_MESSAGE, "message_capacity")
    if name in ["client-frame", "endpoint", "digest-proof"] or value.get("kind") not in ["data", "result"]:
        require(len(encoded(value)) <= 65536, "control_capacity")


def parse(raw, name, line=False):
    require(len(raw) <= MAX_MESSAGE + int(line), "message_capacity")
    if line:
        require(raw.endswith(b"\n") and b"\n" not in raw[:-1] and b"\r" not in raw, "line_framing")
        raw = raw[:-1]
    require(not raw.startswith(b"\xef\xbb\xbf"), "bom")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_key")
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError("nonfinite")

    value = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=pairs, parse_constant=bad_constant)

    def walk(item, depth=0):
        require(depth <= 64, "tree_depth")
        if isinstance(item, str):
            require("\x00" not in item and not any(0xD800 <= ord(c) <= 0xDFFF for c in item), "unicode")
        elif isinstance(item, dict):
            for key, child in item.items():
                walk(key, depth + 1)
                walk(child, depth + 1)
        elif isinstance(item, list):
            for child in item:
                walk(child, depth + 1)
    walk(value)
    validate(value, name)
    if name == "client-frame" or value.get("kind") not in ["data", "result"]:
        require(len(raw) <= 65536, "control_capacity")
    return value


def endpoint(value, local_host="fixture-host"):
    validate(value, "endpoint")
    address = value["address"]
    if value["backend"] == "ipc":
        require(address["path"].startswith("/") and value["hostId"] == local_host, "ipc_scope")
    if value["backend"] == "wss":
        url = urlsplit(address["url"])
        require(url.scheme == "wss" and bool(url.hostname) and url.username is None and url.password is None and not url.fragment, "wss_address")
    # authRef resolves through a configured credential/authorization authority;
    # validation here does not authenticate a peer or establish an ACL.
    return value


class Session:
    """Client-side lifecycle oracle, with fixture-only event cursor semantics."""

    def __init__(self, hello, authenticated_host=None):
        validate(hello, "client-frame")
        require(hello["kind"] == "hello" and hello["sequence"] == 1, "initial_hello")
        self.hello = hello
        self.authenticated_host = authenticated_host or hello["expectedHost"]
        self.channel = None
        self.client_sequence = 1
        self.server_sequence = 0
        self.closed = False
        self.handles = {}
        self.limits = hello["limits"]
        self.capabilities = set()

    def send(self, frame, now=0, *, receive_late=False):
        validate(frame, "client-frame")
        require(not self.closed and self.channel is not None, "session_not_ready")
        require(frame.get("channelId") == self.channel, "channel_binding")
        require(frame["sequence"] == self.client_sequence + 1, "client_order")
        kind = frame["kind"]
        if kind in ["request", "subscribe"]:
            key = frame["requestId"] if kind == "request" else frame["subscriptionId"]
            require(key not in self.handles, "handle_reuse")
            require(len(self.handles) < 4096, "channel_handle_capacity")
            count = sum(h["type"] == kind and h["phase"] != "done" for h in self.handles.values())
            require(count < self.limits["maxOutstanding" if kind == "request" else "maxSubscriptions"], "handle_capacity")
            if kind == "request":
                op = frame["operation"]
                require(op in self.capabilities, "unsupported_operation")
                require(op in (["snapshot", "proof"] if self.hello["product"] == "state" else ["status"]), "operation_product")
                require("knownDigest" not in frame["parameters"] or "digest-proof" in self.capabilities, "unsupported_digest_proof")
                self.handles[key] = {"type": kind, "phase": "pending", "deadline": now + frame["timeoutMs"]}
            else:
                require("subscribe" in self.capabilities, "unsupported_subscription")
                start = frame["start"]
                require((start["mode"] == "after") == (start["cursor"] is not None), "cursor_start")
                require(start["mode"] in (["baseline"] if self.hello["product"] == "state" else ["live", "retained", "after"]), "start_product")
                require(start["mode"] not in ["retained", "after"] or "replay" in self.capabilities, "unsupported_replay")
                credit = frame["credit"]
                require(credit["frames"] <= MAX_CREDIT_FRAMES and credit["bytes"] <= MAX_CREDIT_BYTES, "credit_window")
                self.handles[key] = {"type": kind, "phase": "pending", "start": start, "credit": credit.copy(), "frames": 0, "bytes": 0, "stream": 0, "resync": False, "cursor": None}
        elif kind in ["credit", "cancel"]:
            key = frame["subscriptionId"] if kind == "credit" else frame["handleId"]
            require(key in self.handles and (self.handles[key]["phase"] != "done" or receive_late), "unknown_handle")
            handle = self.handles[key]
            if kind == "cancel":
                require(handle["type"] == ("request" if frame["handleType"] == "request" else "subscribe"), "handle_type")
                if handle["phase"] != "done":
                    handle["phase"] = "closing"
            else:
                require(handle["type"] == "subscribe", "handle_type")
                credit = frame["credit"]
                require(all(credit[k] >= handle["credit"][k] for k in credit), "credit_regression")
                require(credit["frames"] - handle["frames"] <= MAX_CREDIT_FRAMES and credit["bytes"] - handle["bytes"] <= MAX_CREDIT_BYTES, "credit_window")
                handle["credit"] = credit.copy()
        elif kind == "close":
            self.closed = True
        else:
            raise ValueError("unexpected_client_frame")
        self.client_sequence = frame["sequence"]

    def expire(self, now):
        for handle in self.handles.values():
            if handle["type"] == "request" and handle["phase"] == "pending" and now >= handle["deadline"]:
                handle["phase"] = "closing"

    def receive(self, frame, size=None):
        validate(frame, "server-frame")
        require(not self.closed, "session_closed")
        require(frame["sequence"] == self.server_sequence + 1, "server_order")
        if self.channel is None:
            if frame["kind"] == "setup-error":
                require(frame["helloNonce"] == self.hello["helloNonce"], "hello_binding")
                self.closed, self.server_sequence = True, 1
                return "setup_error"
            require(frame["kind"] == "hello" and frame["sequence"] == 1, "initial_hello")
            for returned, requested in [("hostId", "expectedHost"), ("sourceId", "sourceId"), ("product", "product"), ("profile", "profile"), ("helloNonce", "helloNonce")]:
                require(frame[returned] == self.hello[requested], "hello_binding")
            require(frame["hostId"] == self.authenticated_host, "authenticated_host_binding")
            require(set(self.hello["requiredCapabilities"]) <= set(frame["capabilities"]), "unsupported_capability")
            require(all(frame["limits"][k] <= self.limits[k] for k in self.limits), "limit_enlargement")
            self.limits = frame["limits"]
            self.capabilities = set(frame["capabilities"])
            self.channel = frame["channelId"]
            self.server_sequence = 1
            return "hello"
        require(frame.get("channelId") == self.channel, "channel_binding")
        size = len(encoded(frame)) if size is None else size
        require(size <= self.limits["maxMessageBytes"], "negotiated_capacity")
        kind = frame["kind"]
        if kind == "error":
            self.closed = True
            self.server_sequence = frame["sequence"]
            return "error"
        if kind == "control" and frame["subscriptionId"] is None:
            require(frame["streamSequence"] is None and frame["control"] == "heartbeat" and frame["payload"] == {}, "channel_control")
            self.server_sequence = frame["sequence"]
            return "heartbeat"
        key = frame.get("requestId", frame.get("subscriptionId", frame.get("handleId")))
        require(key in self.handles, "unknown_handle")
        handle = self.handles[key]
        require(handle["phase"] != "done", "terminal_barrier")
        ignored = handle["phase"] == "closing"
        if kind == "result":
            require(handle["type"] == "request", "handle_type")
            require((frame["outcome"] == "ok") == (frame["payload"] is not None and frame["error"] is None), "result_shape")
            require(frame["outcome"] == "ok" or frame["payload"] is None and frame["error"] is not None, "result_shape")
            handle["phase"] = "done"
        elif kind == "ended":
            require(handle["type"] == ("request" if frame["handleType"] == "request" else "subscribe"), "handle_type")
            handle["phase"] = "done"
        elif kind == "subscribed":
            require(handle["type"] == "subscribe" and handle["phase"] in ["pending", "closing"], "subscription_barrier")
            require("epoch" not in handle, "subscription_barrier")
            require(frame["start"] == handle["start"], "start_binding")
            handle["epoch"] = frame["publisherEpoch"]
            handle["phase"] = "closing" if ignored else "active"
            if self.hello["product"] == "events":
                require(self.hello["profile"] == "mesh-plus.synthetic.events.v1", "native_cursor_codec_required")
                barrier = frame["barrier"]
                require(barrier["epoch"] == handle["epoch"] and 0 <= barrier["lossFloor"] <= barrier["startSequence"] <= barrier["highWater"], "replay_barrier")
                if handle["start"]["mode"] == "after":
                    require(handle["start"]["cursor"] == {"epoch": handle["epoch"], "sequence": barrier["startSequence"]}, "after_cursor_binding")
                if handle["start"]["mode"] == "live":
                    require(barrier["startSequence"] == barrier["highWater"], "live_barrier")
                if handle["start"]["mode"] == "retained":
                    require(barrier["startSequence"] == barrier["lossFloor"], "retained_barrier")
                handle["admission"] = barrier["startSequence"]
        else:
            require(handle["type"] == "subscribe" and handle["phase"] in ["active", "closing"] and "epoch" in handle, "subscription_barrier")
            require(frame["streamSequence"] == handle["stream"] + 1, "stream_order")
            if kind == "data":
                require(frame["publisherEpoch"] == handle["epoch"], "publisher_epoch")
                require(not handle.get("event_gap"), "event_gap_terminal")
                require(handle["frames"] + 1 <= handle["credit"]["frames"] and handle["bytes"] + size <= handle["credit"]["bytes"], "credit_exhausted")
                if self.hello["product"] == "state":
                    require(frame["deliveryKind"] in ["view", "resync"] and frame["cursor"] is None, "data_product")
                    require(not handle["resync"] or frame["deliveryKind"] == "resync", "resync_required")
                    handle["resync"] = False
                else:
                    require(frame["deliveryKind"] == "event" and frame["cursor"] is not None, "data_product")
                    cursor = frame["cursor"]
                    require(cursor == {"epoch": handle["epoch"], "sequence": handle["admission"] + 1}, "event_admission_order")
                    handle["admission"] += 1
                    if not ignored:
                        handle["cursor"] = cursor
                handle["frames"] += 1
                handle["bytes"] += size
            elif kind == "control":
                if frame["control"] == "heartbeat":
                    require(frame["payload"] == {}, "heartbeat_evidence")
                if frame["control"] == "gap":
                    require(frame["payload"].get("gapKind") in ["delivery", "retention", "publisher_restart"], "gap_kind")
                    handle["resync"] = True
                    handle["event_gap"] = self.hello["product"] == "events"
                if frame["control"] == "checkpoint":
                    require(self.hello["product"] == "events" and not handle.get("event_gap"), "checkpoint_product")
                    cursor = frame["payload"]["cursor"]
                    require(cursor["epoch"] == handle["epoch"] and cursor["sequence"] == handle["admission"], "checkpoint_skips_admission")
                    if not ignored:
                        handle["cursor"] = cursor
            else:
                raise ValueError("unexpected_server_frame")
            handle["stream"] = frame["streamSequence"]
        self.server_sequence = frame["sequence"]
        return "quarantined" if ignored else kind


def semantic_version(frame):
    # Fixture adapter's exact allowlist. Real adapters must prove their own list.
    return {k: v for k, v in frame.items() if k not in ["sequence", "encodedAt"]}


def compact_reply(retained, current_cached_read, nonce, now, owner_available=True):
    require(owner_available, "owner_unavailable")
    require(semantic_version(retained) == semantic_version(current_cached_read), "full_replacement_required")
    return {"kind": "digest-proof", "nonce": nonce, "ownerDigest": digest(retained),
            "hostId": retained["hostId"], "sourceId": retained["sourceId"], "ownerEpoch": retained["ownerEpoch"],
            "clock": retained["clock"], "evaluatedAtMs": now,
            "receipts": [{**r, "remainingMs": max(0, r["originalExpiryMs"] - now) if r["health"] in ["current", "partial"] and r["originalExpiryMs"] is not None else 0} for r in retained["receipts"]]}


def check_compact(proof, retained, nonce, sent, received, margin=100):
    validate(proof, "digest-proof")
    require(proof["nonce"] == nonce and proof["ownerDigest"] == digest(retained), "proof_binding")
    require(all(proof[k] == retained[k] for k in ["hostId", "sourceId", "ownerEpoch", "clock"]), "proof_source_binding")
    require(0 <= sent <= received <= sent + 2000 and 100 <= margin <= 2000, "proof_deadline")
    require(proof["evaluatedAtMs"] >= retained["encodedAt"], "proof_before_source")
    require(len(proof["receipts"]) == len(retained["receipts"]), "receipt_set")
    keys = [(r["sourceId"], r["component"]) for r in proof["receipts"]]
    require(len(keys) == len(set(keys)), "receipt_set")
    results = []
    for receipt, original in zip(proof["receipts"], retained["receipts"], strict=True):
        require({k: v for k, v in receipt.items() if k != "remainingMs"} == original, "receipt_binding")
        expiry = original["originalExpiryMs"]
        remaining = max(0, expiry - proof["evaluatedAtMs"]) if original["health"] in ["current", "partial"] and expiry is not None else 0
        require(receipt["remainingMs"] == remaining, "lease_from_arrival")
        results.append(received + max(0, remaining - (received - sent) - margin))
    return results


class RetainedEvents:
    """Synthetic publisher suffix oracle, not a durable Mesh event journal."""

    def __init__(self, maximum=3, epoch="publisher_1"):
        self.maximum = maximum
        self.epoch = epoch
        self.high = 0
        self.floor = 0
        self.records = []

    def publish(self):
        self.high += 1
        self.records.append({"epoch": self.epoch, "sequence": self.high})
        while len(self.records) > self.maximum:
            self.floor = self.records.pop(0)["sequence"]

    def expire_all(self):
        self.records = []
        self.floor = self.high

    def after(self, cursor):
        require(cursor["epoch"] == self.epoch, "publisher_restart")
        require(self.floor <= cursor["sequence"] <= self.high, "retention_gap")
        return [r for r in self.records if r["sequence"] > cursor["sequence"]]


def sharing_key(endpoint_descriptor, selector, start=None):
    keys = ["authRef", "revision", "endpointId", "hostId", "sourceId", "product", "profile", "backend", "address"]
    value = {k: endpoint_descriptor[k] for k in keys}
    value["selector"] = selector
    if endpoint_descriptor["product"] == "events":
        value["start"] = start
    return encoded(value)


class PendingQueue:
    """Bounded unsent-queue oracle; transport/library buffers are separate gates."""

    def __init__(self, product, max_records=64, max_bytes=1024 * 1024):
        self.product = product
        self.max_records = max_records
        self.max_bytes = max_bytes
        self.pending = deque()
        self.started = None
        self.gap = False
        self.stopped = False

    def size(self):
        return sum(len(encoded(v)) for v in self.pending) + (len(encoded(self.started)) if self.started is not None else 0)

    def enqueue(self, record):
        require(not self.stopped, "queue_closed")
        require(len(encoded(record)) <= self.max_bytes, "queue_record_capacity")
        if self.product == "state":
            require((len(encoded(self.started)) if self.started is not None else 0) + len(encoded(record)) <= self.max_bytes, "queue_byte_capacity")
            if self.pending:
                self.pending.clear()
                self.gap = True
            self.pending.append(record)
        else:
            if len(self.pending) >= self.max_records or self.size() + len(encoded(record)) > self.max_bytes:
                self.gap = True
                self.stopped = True
                self.pending.clear()
                raise ValueError("event_queue_gap")
            self.pending.append(record)
        require(self.size() <= self.max_bytes, "queue_byte_capacity")

    def begin(self):
        require(self.started is None, "frame_already_started")
        require(bool(self.pending), "queue_empty")
        self.started = self.pending.popleft()
        gap = self.gap
        self.gap = False
        return {"gapBefore": gap, "kind": "resync" if self.product == "state" and gap else "view" if self.product == "state" else "event", "record": self.started}

    def finish(self):
        require(self.started is not None, "no_started_frame")
        self.started = None
