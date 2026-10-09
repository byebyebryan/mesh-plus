"""Optional pure Observer codecs and explicit cached IPC adapters."""

import asyncio
import hashlib
import json
import os
import re
import uuid
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from .bridge import Publication
from .protocol import check
from .transport import boottime_ms, connect_ipc


def clock_domain():
    namespace = re.fullmatch(r"time:\[([0-9]+)\]", os.readlink("/proc/self/ns/time"))
    check(namespace is not None, "clock_domain")
    return {"bootId": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "timeNamespace": "time:" + namespace[1]}


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=1)
def bridge_validator():
    return Draft202012Validator(json.loads(files("mesh_plus").joinpath("schemas", "bridge-reply.schema.json").read_text()))


class ObserverCodec:
    """Imports only the producer's supported pure contract facades."""

    def __init__(self, domain, host, source):
        check(domain in {"tmux", "agent"}, "observer_domain")
        self.domain, self.host, self.source = domain, host, source
        if domain == "tmux":
            from tmux_observer.delivery import validate_service_frame
            from tmux_observer.native import FRAME_LIMIT, decode_document
            self.native_validate = validate_service_frame
            self.native_parse = lambda raw: decode_document(raw, limit=FRAME_LIMIT)
            self.maximum = FRAME_LIMIT
        else:
            from agent_observer.service_contract import MAX_FRAME_BYTES
            from agent_observer.service_public import parse_frame, validate_frame
            self.native_validate = validate_frame
            self.native_parse = parse_frame
            self.maximum = MAX_FRAME_BYTES

    def native(self, frame):
        self.native_validate(frame)
        if self.domain == "tmux":
            check(frame["source"]["hostId"] == self.host, "owner_host_scope")
        else:
            check(frame["hostScope"] == self.host, "owner_host_scope")
        return frame

    def clock(self, frame):
        if self.domain == "tmux":
            return frame["clock"]
        match = re.fullmatch(r"time:\[([0-9]+)\]", frame["clockDomain"])
        check(match is not None, "owner_clock_domain")
        return {"bootId": frame["bootId"], "timeNamespace": "time:" + match[1]}

    def epoch(self, frame):
        return frame["publisherId"] if self.domain == "tmux" else frame["serviceId"]

    def emitted(self, frame):
        return frame["encodedAt"] if self.domain == "tmux" else frame["emittedBoottimeMs"]

    def receipts(self, frame):
        if self.domain == "tmux":
            receipt = frame["receipt"]
            return [{"sourceId": "default", "component": "native", "accepted": receipt["accepted"],
                     "health": "current" if receipt["state"] == "ready" else "stale", "expiry": receipt["expiresAt"]}]
        return [{"sourceId": source["provider"] + ":" + source["namespace"], "component": component["name"],
                 "accepted": component["accepted"], "health": component["health"],
                 "expiry": component["expiresBoottimeMs"]}
                for source in frame["sources"] for component in source["components"]]

    def validate(self, payload):
        bridge_validator().validate(payload)
        check(payload["hostId"] == self.host and payload["sourceId"] == self.source, "bridge_source_binding")
        check(payload["kind"] in {"candidate", "proof"} and payload["error"] is None and
              payload["ownerFrame"] is not None, "bridge_success_shape")
        frame = self.native(payload["ownerFrame"])
        check(payload["ownerDigest"] == digest(frame), "owner_digest")
        check(self.clock(frame) == payload["clock"] and self.emitted(frame) <= payload["encodedAtMs"], "bridge_clock")
        if payload["kind"] == "candidate":
            check(payload["nonce"] is None and not payload["remaining"], "candidate_receipts")
        else:
            check(payload["nonce"] is not None, "proof_nonce")
            expected = []
            for receipt in self.receipts(frame):
                expiry = receipt.pop("expiry")
                remaining = max(0, expiry - payload["encodedAtMs"]) if receipt["health"] in {"current", "partial"} else 0
                expected.append({**receipt, "remainingMs": remaining})
            check(payload["remaining"] == expected, "proof_receipts")
        return payload


class ObserverAdapter(ObserverCodec):
    capabilities = ("snapshot", "proof", "subscribe")

    def __init__(self, domain, host, source, path):
        super().__init__(domain, host, source)
        self.path = Path(path)
        self.profile = domain + "-observer.mesh-candidate.v1"
        self.bridge_id = str(uuid.uuid4())
        self.sequence = 0
        self.accepted = {}
        self.owner_binding = None

    def wrap(self, frame, nonce=None):
        self.native(frame)
        check(self.clock(frame) == clock_domain(), "source_clock_context")
        now = boottime_ms()
        check(self.emitted(frame) <= now, "source_future_frame")
        binding = (self.epoch(frame), tuple(sorted(self.clock(frame).items())))
        receipts = self.receipts(frame)
        if binding == self.owner_binding:
            for receipt in receipts:
                key = receipt["sourceId"], receipt["component"]
                previous = self.accepted.get(key)
                if previous:
                    check(receipt["accepted"] >= previous[0], "source_receipt_regression")
                    check(receipt["accepted"] != previous[0] or receipt["expiry"] == previous[1], "source_lease_renewal")
        self.owner_binding = binding
        self.accepted = {(r["sourceId"], r["component"]): (r["accepted"], r["expiry"]) for r in receipts}
        self.sequence += 1
        remaining = []
        if nonce is not None:
            for receipt in self.receipts(frame):
                expiry = receipt.pop("expiry")
                lease = max(0, expiry - now) if receipt["health"] in {"current", "partial"} else 0
                remaining.append({**receipt, "remainingMs": lease})
        result = {"meshProtocol": 1, "kind": "proof" if nonce else "candidate", "nonce": nonce,
                  "bridgeId": self.bridge_id, "sequence": self.sequence, "sourceId": self.source,
                  "hostId": self.host, "clock": self.clock(frame), "encodedAtMs": now, "ownerFrame": frame,
                  "ownerDigest": digest(frame), "remaining": remaining, "error": None}
        return self.validate(result)

    async def frames(self, operation):
        channel = await connect_ipc(self.path, maximum=self.maximum)
        request_id = uuid.uuid4().hex
        if self.domain == "tmux":
            request = {"protocol": "tmux-observer.service.v1", "schemaVersion": 1, "operation": operation,
                       "requestId": request_id, "expectedHost": self.host}
            guard = None
        else:
            from agent_observer.service_public import StreamGuard
            guard = StreamGuard(expected_host=self.host, expected_uid=os.getuid())
            request = {"serviceProtocol": 2, "operation": operation, "hostScope": self.host}
        epoch, sequence, revision, emitted = None, None, None, None
        try:
            channel.writer.write(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            await asyncio.wait_for(channel.writer.drain(), 2)
            while True:
                raw = await asyncio.wait_for(channel.reader.readuntil(b"\n"), 15)
                check(len(raw) <= self.maximum, "native_capacity")
                frame = self.native_parse(raw)
                self.native(frame)
                if guard:
                    guard.accept(frame)
                else:
                    current_epoch = self.epoch(frame)
                    check(epoch is None or current_epoch == epoch, "publisher_restart")
                    check(sequence is None or frame["sequence"] == sequence + 1, "native_stream_order")
                    check(revision is None or frame["viewRevision"] >= revision, "native_revision_regression")
                    check(emitted is None or self.emitted(frame) >= emitted, "native_clock_regression")
                    if sequence is None:
                        check(frame["requestId"] == request_id, "native_request_binding")
                    epoch, sequence, revision, emitted = current_epoch, frame["sequence"], frame["viewRevision"], self.emitted(frame)
                uid = frame["source"]["uid"] if self.domain == "tmux" else frame["uid"]
                check(uid == os.getuid(), "native_uid")
                check(self.clock(frame) == clock_domain(), "source_clock_context")
                check(frame["kind"] not in {"error", "gap"}, "native_gap_or_error")
                yield frame
                if operation != "watch":
                    return
        finally:
            await channel.close()

    async def snapshot(self, parameters):
        check(parameters == {}, "snapshot_parameters")
        iterator = self.frames("status")
        try:
            return self.wrap(await anext(iterator))
        finally:
            await iterator.aclose()

    async def proof(self, parameters):
        check(set(parameters) == {"nonce"} and isinstance(parameters["nonce"], str) and
              re.fullmatch(r"[0-9a-f]{32,64}", parameters["nonce"]), "proof_parameters")
        iterator = self.frames("status")
        try:
            # Open/read occurs after nonce receipt; no retained pipe copy proves source liveness.
            return self.wrap(await anext(iterator), parameters["nonce"])
        finally:
            await iterator.aclose()

    async def watch(self):
        async for frame in self.frames("watch"):
            if frame["kind"] == "heartbeat":
                continue
            yield Publication(self.wrap(frame), self.epoch(frame), {"viewRevision": frame["viewRevision"]})
