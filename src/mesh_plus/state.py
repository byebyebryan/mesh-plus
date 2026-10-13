"""Versioned, explicit pure state-profile boundary; no native I/O."""

import copy
import hashlib
import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from importlib.resources import files
from typing import Protocol, Sequence

from .evidence import bridge_validator, digest
from .protocol import check, encode

SDK_INTERFACE_VERSION = 1
JsonObject = dict
ReceiptKey = tuple[str, str]


@dataclass(frozen=True)
class ProfileDescriptor:
    sdk_version: int
    profile_id: str
    native_protocol: str
    native_version: int
    contract_digest: str
    frame_bytes: int


@dataclass(frozen=True)
class NativeState:
    owner: JsonObject
    records: Sequence[JsonObject]
    clock: JsonObject
    publisher: str
    emitted_ms: int
    receipts: Sequence[JsonObject]


class BoundStateCodec(Protocol):
    host: str
    source: str
    profile_id: str

    def validate_bridge(self, payload: JsonObject) -> None: ...
    def inspect_native(self, frame: JsonObject) -> NativeState: ...


class StateProfile(Protocol):
    descriptor: ProfileDescriptor

    def bind(self, host: str, source: str) -> BoundStateCodec: ...
    def validate_response(self, response: JsonObject) -> None: ...
    def restore_native(self, owner: JsonObject, records: Sequence[JsonObject]) -> JsonObject: ...
    def record_host(self, record: JsonObject) -> str: ...
    def record_identity(self, record: JsonObject) -> tuple[str | int, ...]: ...
    def record_receipts(self, record: JsonObject, state: NativeState) -> frozenset[ReceiptKey] | None: ...
    def record_eligible(self, record: JsonObject, state: NativeState) -> bool: ...


@lru_cache(maxsize=4)
def descriptor(domain, *, profile_id=None):
    check(domain in {"tmux", "agent"}, "observer_domain")
    default = domain + "-observer.mesh-candidate.v1"
    profile_id = default if profile_id is None else profile_id
    versions = {"agent-observer.mesh-candidate.v2": ("-v2", 5),
                "agent-observer.mesh-candidate.v3": ("-v3", 6)}
    extension = versions.get(profile_id) if domain == "agent" else None
    check(profile_id == default or extension is not None, "profile_descriptor")
    suffix, version = extension or ("", 1 if domain == "tmux" else 4)
    raw = files("mesh_plus").joinpath("schemas", "read-" + domain + suffix + ".profile.schema.json").read_bytes()
    return ProfileDescriptor(1, profile_id,
                             "tmux-observer.observation.v1" if domain == "tmux" else "agent-observer.snapshot",
                             version, "sha256:" + hashlib.sha256(raw).hexdigest(),
                             1064960 if domain == "tmux" else 8404992)



def resolve_profile(domain, profile=None):
    profile = ReferenceProfile(domain) if profile is None else profile
    actual = getattr(profile, "descriptor", None)
    check(isinstance(actual, ProfileDescriptor), "profile_descriptor")
    expected = descriptor(domain, profile_id=actual.profile_id)
    check(isinstance(actual, ProfileDescriptor) and actual == expected and
          all(type(getattr(actual, k)) is int for k in ("sdk_version", "native_version", "frame_bytes")),
          "profile_descriptor")
    check(all(callable(getattr(profile, name, None)) for name in
              ("bind", "validate_response", "restore_native", "record_host", "record_identity",
               "record_receipts", "record_eligible")), "profile_interface")
    return profile


def legacy_codec(domain, profile, host, validator):
    """Bound-method introspection is confined to the old reference wrapper."""
    from .observer import ObserverCodec
    legacy = getattr(validator, "__self__", None)
    check(isinstance(legacy, ObserverCodec) and legacy.domain == domain and legacy.host == host,
          "endpoint_codec_required")
    return profile.bind(host, legacy.source)


def check_binding(codec, host, source, profile_id):
    check(getattr(codec, "host", None) == host and getattr(codec, "source", None) == source and
          getattr(codec, "profile_id", None) == profile_id, "endpoint_codec_binding")
    check(isinstance(host, str) and re.fullmatch(r"[a-z0-9][a-z0-9_.-]*", host) and len(host) <= 16384,
          "configured_host_id")
    check(isinstance(source, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,127}", source), "configured_source_id")
    check(callable(getattr(codec, "validate_bridge", None)) and callable(getattr(codec, "inspect_native", None)),
          "codec_interface")


def inspect_state(profile, codec, frame):
    check(len(encode(frame)) + 1 <= profile.descriptor.frame_bytes, "native_capacity")
    check_binding(codec, codec.host, codec.source, profile.descriptor.profile_id)
    state = codec.inspect_native(frame)
    check(isinstance(state, NativeState), "native_state")
    check(state.owner["protocol"] == profile.descriptor.native_protocol and
          state.owner["version"] == profile.descriptor.native_version, "owner_version")
    check(profile.restore_native(state.owner, state.records) == frame, "native_roundtrip")
    check(type(state.emitted_ms) is int and state.emitted_ms >= 0 and
          isinstance(state.publisher, str) and bool(state.publisher), "native_chronology")
    check(type(state.clock) is dict and set(state.clock) == {"bootId", "timeNamespace"} and
          all(type(v) is str for v in state.clock.values()), "native_clock")
    keys = []
    for receipt in state.receipts:
        check(set(receipt) == {"sourceId", "component", "accepted", "health", "expiry"}, "native_receipt_shape")
        check(all(isinstance(receipt[k], str) and bool(receipt[k]) for k in ("sourceId", "component")) and
              type(receipt["accepted"]) is int and receipt["accepted"] >= 0 and
              (receipt["expiry"] is None or (type(receipt["expiry"]) is int and receipt["expiry"] >= 0)) and
              receipt["health"] in {"current", "partial", "stale", "unknown", "unsupported", "unavailable", "warming"}, "native_receipt_range")
        if receipt["health"] in {"current", "partial"}:
            check(receipt["expiry"] is not None and receipt["accepted"] > 0, "native_positive_receipt")
        keys.append((receipt["sourceId"], receipt["component"]))
    check(len(keys) == len(set(keys)), "native_receipt_duplicate")
    check(all(profile.record_host(row) == codec.host for row in state.records), "owner_host_scope")
    return state


def validate_bridge(profile, codec, payload):
    """Domain admission cannot bypass Mesh proof, scope or receipt checks."""
    bridge_validator().validate(payload)
    check(payload["hostId"] == codec.host and payload["sourceId"] == codec.source, "bridge_source_binding")
    check(payload["kind"] in {"candidate", "proof"} and payload["error"] is None and
          payload["ownerFrame"] is not None, "bridge_success_shape")
    codec.validate_bridge(payload)
    state = inspect_state(profile, codec, payload["ownerFrame"])
    check(payload["ownerDigest"] == digest(payload["ownerFrame"]), "owner_digest")
    check(state.clock == payload["clock"] and state.emitted_ms <= payload["encodedAtMs"], "bridge_clock")
    if payload["kind"] == "candidate":
        check(payload["nonce"] is None and not payload["remaining"], "candidate_receipts")
    else:
        check(payload["nonce"] is not None, "proof_nonce")
        expected = []
        for original in state.receipts:
            receipt = dict(original)
            expiry = receipt.pop("expiry")
            remaining = max(0, expiry - payload["encodedAtMs"]) if receipt["health"] in {"current", "partial"} else 0
            expected.append({**receipt, "remainingMs": remaining})
        check(payload["remaining"] == expected, "proof_receipts")
    return state


class ReferenceProfile:
    """Compatibility implementation using only supported pure Observer facades."""

    def __init__(self, domain):
        self.domain = domain
        self.descriptor = descriptor(domain)

    def bind(self, host, source):
        return ReferenceCodec(self, host, source)

    def validate_response(self, response):
        # The compulsory packaged profile schema is checked by Mesh itself.
        pass

    def restore_native(self, owner, records):
        metadata = owner["metadata"]
        return {**owner["service"], "snapshot": None if metadata is None else {**metadata, "sessions": list(records)}}

    def record_host(self, record):
        return record["hostId"] if self.domain == "tmux" else record["identity"]["hostScope"]

    def record_identity(self, record):
        return (tuple(record[k] for k in ("hostId", "serverGeneration", "sessionId", "createdAt"))
                if self.domain == "tmux" else
                tuple(record["identity"][k] for k in ("hostScope", "provider", "namespace", "nativeIdKind", "nativeId")))

    def record_receipts(self, record, state):
        source = "default" if self.domain == "tmux" else record["identity"]["provider"] + ":" + record["identity"]["namespace"]
        return frozenset((r["sourceId"], r["component"]) for r in state.receipts
                         if r["sourceId"] == source and r["health"] in {"current", "partial"}) or None

    def record_eligible(self, record, state):
        if self.domain == "agent" and not record["hasSavedHistory"]:
            return record["runtime"]["health"] == "current" and any(
                component == "runtime" for source, component in self.record_receipts(record, state) or ())
        return True


@dataclass(frozen=True)
class ReferenceCodec:
    profile: ReferenceProfile
    host: str
    source: str

    @property
    def profile_id(self):
        return self.profile.descriptor.profile_id

    @cached_property
    def legacy(self):
        from .observer import ObserverCodec
        return ObserverCodec(self.profile.domain, self.host, self.source)

    def validate_bridge(self, payload):
        # Direct Client users retain full native/bridge admission as before.
        self.legacy.validate(payload)

    def inspect_native(self, frame):
        codec = self.legacy
        codec.native(frame)
        snapshot = frame["snapshot"]
        return NativeState(
            {"protocol": self.profile.descriptor.native_protocol, "version": self.profile.descriptor.native_version,
             "metadata": None if snapshot is None else {k: v for k, v in snapshot.items() if k != "sessions"},
             "service": {k: v for k, v in frame.items() if k != "snapshot"}},
            [] if snapshot is None else snapshot["sessions"], codec.clock(frame), codec.epoch(frame),
            codec.emitted(frame), copy.deepcopy(codec.receipts(frame)))
