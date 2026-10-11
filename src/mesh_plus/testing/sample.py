"""Independent test profile over frozen fixtures. No Observer imports or I/O."""

import asyncio
import copy
import re
import uuid

from mesh_plus.api import NativeState, Publication, descriptor
from mesh_plus.evidence import clock_domain, digest
from mesh_plus.protocol import check
from mesh_plus.transport import boottime_ms

from .cases import profile_cases


class Profile:
    def __init__(self, domain):
        self.domain = domain
        self.descriptor = descriptor(domain)

    def bind(self, host, source):
        return Codec(self, host, source)

    def validate_response(self, response):
        pass

    def restore_native(self, owner, records):
        metadata = owner["metadata"]
        return {**owner["service"], "snapshot": None if metadata is None else {**metadata, "sessions": list(records)}}

    def record_host(self, row):
        return row["hostId"] if self.domain == "tmux" else row["identity"]["hostScope"]

    def record_identity(self, row):
        return (tuple(row[k] for k in ("hostId", "serverGeneration", "sessionId", "createdAt"))
                if self.domain == "tmux" else
                tuple(row["identity"][k] for k in ("hostScope", "provider", "namespace", "nativeIdKind", "nativeId")))

    def record_receipts(self, row, state):
        source = "default" if self.domain == "tmux" else row["identity"]["provider"] + ":" + row["identity"]["namespace"]
        return frozenset((r["sourceId"], r["component"]) for r in state.receipts
                         if r["sourceId"] == source and r["health"] in {"current", "partial"}) or None

    def record_eligible(self, row, state):
        return self.domain != "agent" or row["hasSavedHistory"] or (row["runtime"]["health"] == "current" and any(
            component == "runtime" for source, component in self.record_receipts(row, state) or ()))


class Codec:
    def __init__(self, profile, host, source):
        self.profile = profile
        self.host, self.source = host, source
        self.profile_id = profile.descriptor.profile_id

    def validate_bridge(self, payload):
        # Deliberately no network checks: the SDK must enforce them itself.
        pass

    def inspect_native(self, frame):
        p = self.profile
        snapshot = frame["snapshot"]
        owner = {"protocol": p.descriptor.native_protocol, "version": p.descriptor.native_version,
                 "metadata": None if snapshot is None else {k: v for k, v in snapshot.items() if k != "sessions"},
                 "service": {k: v for k, v in frame.items() if k != "snapshot"}}
        if p.domain == "tmux":
            check(frame["source"]["hostId"] == self.host, "owner_host_scope")
            original = frame["receipt"]
            receipts = [{"sourceId": "default", "component": "native", "accepted": original["accepted"],
                         "expiry": original["expiresAt"], "health": "current" if original["state"] == "ready" else "stale"}]
            clock, publisher, emitted = frame["clock"], frame["publisherId"], frame["encodedAt"]
        else:
            check(frame["hostScope"] == self.host, "owner_host_scope")
            receipts = [{"sourceId": s["provider"] + ":" + s["namespace"], "component": c["name"],
                         "accepted": c["accepted"], "expiry": c["expiresBoottimeMs"], "health": c["health"]}
                        for s in frame["sources"] for c in s["components"]]
            clock = {"bootId": frame["bootId"], "timeNamespace": "time:" + re.fullmatch(r"time:\[([0-9]+)\]", frame["clockDomain"])[1]}
            publisher, emitted = frame["serviceId"], frame["emittedBoottimeMs"]
        return NativeState(owner, [] if snapshot is None else snapshot["sessions"], clock, publisher, emitted, receipts)


class Publisher:
    capabilities = ("snapshot", "proof", "subscribe")

    def __init__(self, domain, host, source="default", profile=None):
        self.state_profile = Profile(domain) if profile is None else profile
        self.host, self.source = host, source
        self.profile = self.state_profile.descriptor.profile_id
        self.codec = self.state_profile.bind(host, source)
        self.validate = self.codec.validate_bridge
        fixture = next(case.response for case in profile_cases(domain) if case.case_id == domain + "-local")
        owner = fixture["mesh"]["hosts"][0]["owner"]
        self.frame = self.state_profile.restore_native(owner, fixture["sessions"])
        # Rebind fixture host, timestamps and clock without any native package.
        service = owner["service"]
        emitted = service["encodedAt"] if domain == "tmux" else service["emittedBoottimeMs"]
        shift = boottime_ms() - 100 - emitted
        clock = clock_domain()
        def rewrite(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"hostId", "hostScope", "authority"}:
                        value[key] = host
                    elif key in {"encodedAt", "startedAt", "finishedAt", "acceptedAt", "expiresAt", "lastAttemptAt",
                                 "emittedBoottimeMs", "sampledBoottimeMs", "expiresBoottimeMs"} and type(item) is int:
                        value[key] += shift
                    elif key == "bootId":
                        value[key] = clock["bootId"]
                    elif key == "timeNamespace":
                        value[key] = clock["timeNamespace"]
                    elif key == "clockDomain":
                        value[key] = "time:[" + clock["timeNamespace"].split(":")[1] + "]"
                    else:
                        rewrite(item)
            elif isinstance(value, list):
                for item in value:
                    rewrite(item)
        rewrite(self.frame)
        self.bridge_id, self.sequence = str(uuid.uuid4()), 0
        self.watchers = 0
        self.changes = asyncio.Queue()

    def wrap(self, nonce=None):
        self.sequence += 1
        state = self.codec.inspect_native(self.frame)
        now = boottime_ms()
        remaining = []
        if nonce is not None:
            for original in state.receipts:
                receipt = dict(original)
                expiry = receipt.pop("expiry")
                lease = max(0, expiry - now) if receipt["health"] in {"current", "partial"} else 0
                remaining.append({**receipt, "remainingMs": lease})
        return {"meshProtocol": 1, "kind": "proof" if nonce else "candidate", "nonce": nonce,
                "bridgeId": self.bridge_id, "sequence": self.sequence, "sourceId": self.source, "hostId": self.host,
                "clock": state.clock, "encodedAtMs": now, "ownerFrame": copy.deepcopy(self.frame),
                "ownerDigest": digest(self.frame), "remaining": remaining, "error": None}

    async def snapshot(self, parameters):
        return self.wrap()

    async def proof(self, parameters):
        return self.wrap(parameters["nonce"])

    async def watch(self):
        self.watchers += 1
        try:
            while True:
                state = self.codec.inspect_native(self.frame)
                yield Publication(self.wrap(), state.publisher, {"revision": self.frame["viewRevision"]})
                await self.changes.get()
        finally:
            self.watchers -= 1
