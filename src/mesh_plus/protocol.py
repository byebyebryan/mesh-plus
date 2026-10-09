"""Strict candidate framing and transactional state-product lifecycle guards."""

import copy
import json
import math
from functools import lru_cache
from importlib.resources import files

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

PROTOCOL = "mesh-plus.delivery-candidate.v1"
MAX_MESSAGE = 8 * 1024 * 1024 + 80 * 1024
MAX_CONTROL = 64 * 1024
MAX_HANDLES = 4096


class ProtocolError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def check(condition, code):
    if not condition:
        raise ProtocolError(code)


@lru_cache(maxsize=4)
def validator(direction):
    check(direction in {"client", "server"}, "frame_direction")
    schema = json.loads(files("mesh_plus").joinpath("schemas", direction + "-frame.schema.json").read_text())
    return Draft202012Validator(schema)


def tree(value, depth=0):
    check(depth <= 64, "tree_depth")
    if isinstance(value, str):
        check("\x00" not in value and not any(0xD800 <= ord(c) <= 0xDFFF for c in value), "unicode")
    elif isinstance(value, float):
        check(math.isfinite(value), "nonfinite")
    elif isinstance(value, dict):
        for key, child in value.items():
            tree(key, depth + 1)
            tree(child, depth + 1)
    elif isinstance(value, list):
        for child in value:
            tree(child, depth + 1)


def encode(value):
    try:
        tree(value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    except (RecursionError, UnicodeError, TypeError, ValueError) as error:
        raise ProtocolError("invalid_json") from error


def validate(value, direction, size=None, maximum=MAX_MESSAGE):
    try:
        validator(direction).validate(value)
    except (ValidationError, RecursionError) as error:
        raise ProtocolError("frame_schema") from error
    tree(value)
    size = len(encode(value)) if size is None else size
    check(type(size) is int and 0 <= size <= maximum, "message_capacity")
    if direction == "client" or value["kind"] not in {"data", "result"}:
        check(size <= MAX_CONTROL, "control_capacity")
    return value


def decode(raw, direction, maximum=MAX_MESSAGE):
    value = decode_json(raw, maximum)
    return validate(value, direction, len(raw), maximum)


def decode_json(raw, maximum=MAX_MESSAGE):
    """Strict bounded JSON, independent of any outer protocol discriminator."""
    check(type(raw) is bytes and len(raw) <= maximum, "message_capacity")
    check(not raw.startswith(b"\xef\xbb\xbf"), "bom")

    def pairs(items):
        result = {}
        for key, value in items:
            check(key not in result, "duplicate_key")
            result[key] = value
        return result

    def constant(_):
        raise ProtocolError("nonfinite")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProtocolError("invalid_json") from error
    tree(value)
    return value


class Lifecycle:
    """One state channel; domain payload acceptance remains the codec's job.

    Transactions validate on a bounded copy before committing. Invalid frames
    never advance sequence, credit or handle state. Events are explicitly gated.
    """

    def __init__(self, hello, authenticated_host):
        validate(hello, "client")
        check(hello["kind"] == "hello" and hello["sequence"] == 1, "initial_hello")
        check(hello["product"] == "state", "unsupported_product")
        self.hello = copy.deepcopy(hello)
        self.authenticated_host = authenticated_host
        self.channel = None
        self.client_sequence = 1
        self.server_sequence = 0
        self.limits = hello["limits"].copy()
        self.capabilities = set()
        self.handles = {}
        self.closed = False

    def _transaction(self, method, *args):
        candidate = copy.copy(self)
        candidate.handles = self.handles.copy()
        frame = args[0]
        key = frame.get("requestId", frame.get("subscriptionId", frame.get("handleId")))
        if key in candidate.handles:
            candidate.handles[key] = copy.deepcopy(candidate.handles[key])
        result = method(candidate, *args)
        self.__dict__.update(candidate.__dict__)
        return result

    def sent(self, frame, now_ms):
        return self._transaction(Lifecycle._sent, frame, now_ms)

    def received(self, frame, size):
        return self._transaction(Lifecycle._received, frame, size)

    def _sent(self, frame, now_ms):
        validate(frame, "client", maximum=self.limits["maxMessageBytes"])
        check(not self.closed and self.channel is not None, "session_not_ready")
        check(frame["channelId"] == self.channel, "channel_binding")
        check(frame["sequence"] == self.client_sequence + 1, "client_order")
        kind = frame["kind"]
        if kind in {"request", "subscribe"}:
            key = frame["requestId"] if kind == "request" else frame["subscriptionId"]
            check(key not in self.handles and len(self.handles) < MAX_HANDLES, "handle_reuse_or_capacity")
            active = sum(h["kind"] == kind and h["phase"] != "done" for h in self.handles.values())
            limit = self.limits["maxOutstanding" if kind == "request" else "maxSubscriptions"]
            check(active < limit, "handle_capacity")
            handle = {"kind": kind, "phase": "pending"}
            if kind == "request":
                check(frame["operation"] in {"snapshot", "proof"} & self.capabilities, "unsupported_operation")
                check("knownDigest" not in frame["parameters"] or "digest-proof" in self.capabilities,
                      "unsupported_digest_proof")
                handle["deadline"] = now_ms + frame["timeoutMs"]
            else:
                check("subscribe" in self.capabilities, "unsupported_subscription")
                check(frame["start"] == {"mode": "baseline", "cursor": None}, "start_product")
                handle.update(start=copy.deepcopy(frame["start"]), stream=0, frames=0, bytes=0,
                              credit={"frames": 0, "bytes": 0}, resync=False)
                self._credit(handle, frame["credit"])
            self.handles[key] = handle
        elif kind in {"cancel", "credit"}:
            key = frame["handleId"] if kind == "cancel" else frame["subscriptionId"]
            check(key in self.handles, "unknown_handle")
            handle = self.handles[key]
            check(handle["phase"] != "done", "terminal_barrier")
            if kind == "credit":
                check(handle["kind"] == "subscribe", "handle_type")
                self._credit(handle, frame["credit"])
            else:
                check(frame["handleType"] == ("request" if handle["kind"] == "request" else "subscription"),
                      "handle_type")
                handle["phase"] = "closing"
        elif kind == "close":
            self.closed = True
        self.client_sequence = frame["sequence"]

    def _credit(self, handle, credit):
        check(all(credit[k] >= handle["credit"][k] for k in credit), "credit_regression")
        check(0 <= credit["frames"] - handle["frames"] <= 32 and
              0 <= credit["bytes"] - handle["bytes"] <= 2 * self.limits["maxMessageBytes"], "credit_window")
        handle["credit"] = credit.copy()

    def expire(self, now_ms):
        expired = []
        for key, handle in self.handles.items():
            if handle["kind"] == "request" and handle["phase"] == "pending" and now_ms >= handle["deadline"]:
                handle["phase"] = "closing"
                expired.append(key)
        return expired

    def _received(self, frame, size):
        validate(frame, "server", size, self.limits["maxMessageBytes"])
        check(not self.closed, "session_closed")
        check(frame["sequence"] == self.server_sequence + 1, "server_order")
        if self.channel is None:
            check(frame["kind"] == "hello", "initial_hello")
            for returned, requested in [("hostId", "expectedHost"), ("sourceId", "sourceId"),
                                        ("product", "product"), ("profile", "profile"), ("helloNonce", "helloNonce")]:
                check(frame[returned] == self.hello[requested], "hello_binding")
            check(frame["hostId"] == self.authenticated_host, "authenticated_host_binding")
            check(set(self.hello["requiredCapabilities"]) <= set(frame["capabilities"]), "unsupported_capability")
            check(all(frame["limits"][k] <= self.limits[k] for k in self.limits), "limit_enlargement")
            self.channel = frame["channelId"]
            self.limits = frame["limits"].copy()
            self.capabilities = set(frame["capabilities"])
            self.server_sequence = frame["sequence"]
            return "hello"
        check(frame.get("channelId") == self.channel, "channel_binding")
        kind = frame["kind"]
        if kind == "error":
            self.closed = True
            outcome = "error"
        elif kind == "control" and frame["subscriptionId"] is None:
            check(frame["streamSequence"] is None and frame["control"] == "heartbeat" and frame["payload"] == {},
                  "channel_control")
            outcome = "heartbeat"
        else:
            key = frame.get("requestId", frame.get("subscriptionId", frame.get("handleId")))
            check(key in self.handles, "unknown_handle")
            handle = self.handles[key]
            check(handle["phase"] != "done", "terminal_barrier")
            outcome = "quarantined" if handle["phase"] == "closing" else kind
            if kind == "result":
                check(handle["kind"] == "request", "handle_type")
                check((frame["outcome"] == "ok" and frame["payload"] is not None and frame["error"] is None) or
                      (frame["outcome"] != "ok" and frame["payload"] is None and frame["error"] is not None),
                      "result_shape")
                handle["phase"] = "done"
            elif kind == "ended":
                check(frame["handleType"] == ("request" if handle["kind"] == "request" else "subscription"),
                      "handle_type")
                handle["phase"] = "done"
            elif kind == "subscribed":
                check(handle["kind"] == "subscribe" and handle["phase"] in {"pending", "closing"} and
                      "epoch" not in handle, "subscription_barrier")
                check(frame["start"] == handle["start"], "start_binding")
                handle["epoch"] = frame["publisherEpoch"]
                if handle["phase"] != "closing":
                    handle["phase"] = "active"
            else:
                check(handle["kind"] == "subscribe" and handle["phase"] in {"active", "closing"} and
                      "epoch" in handle, "subscription_barrier")
                check(frame["streamSequence"] == handle["stream"] + 1, "stream_order")
                if kind == "data":
                    check(frame["publisherEpoch"] == handle["epoch"], "publisher_epoch")
                    check(frame["deliveryKind"] in {"view", "resync"} and frame["cursor"] is None, "data_product")
                    check(not handle["resync"] or frame["deliveryKind"] == "resync", "resync_required")
                    check(handle["frames"] + 1 <= handle["credit"]["frames"] and
                          handle["bytes"] + size <= handle["credit"]["bytes"], "credit_exhausted")
                    handle["frames"] += 1
                    handle["bytes"] += size
                    handle["resync"] = False
                elif kind == "control":
                    check(frame["control"] in {"heartbeat", "gap"}, "unsupported_control_codec")
                    if frame["control"] == "heartbeat":
                        check(frame["payload"] == {}, "heartbeat_evidence")
                    elif frame["control"] == "gap":
                        handle["resync"] = True
                handle["stream"] = frame["streamSequence"]
        self.server_sequence = frame["sequence"]
        return outcome
