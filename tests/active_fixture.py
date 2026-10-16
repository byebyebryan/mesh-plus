"""Independent projected DTO fixture/profile; no Observer imports or collection.

Domain semantic qualification additionally uses the exact installed owner codec.
This profile validates frozen structure and exact supports needed by these tests.
"""

import copy
import json
import re
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from mesh_plus.api import CachedPublication, NativeState, descriptor
from mesh_plus.evidence import clock_domain
from mesh_plus.protocol import check
from mesh_plus.transport import boottime_ms

PROFILE = "agent-observer.mesh-active.v1"
NATIVE = Draft202012Validator(json.loads(files("mesh_plus").joinpath(
    "schemas", "agent-active-native.schema.json").read_text()))


class ActiveProfile:
    def __init__(self):
        self.descriptor = descriptor("agent", profile_id=PROFILE)

    def bind(self, host, source):
        return ActiveCodec(self, host, source)

    def validate_response(self, response):
        pass

    def restore_native(self, owner, records):
        return {**owner["service"], "projection": None if owner["metadata"] is None else
                {**owner["metadata"], "sessions": list(records)}}

    def record_host(self, record):
        return record["identity"]["hostScope"]

    def record_identity(self, record):
        return tuple(record["identity"][key] for key in
                     ("hostScope", "provider", "namespace", "nativeIdKind", "nativeId"))

    def record_receipts(self, record, state):
        return frozenset((r["sourceId"], r["component"]) for r in state.receipts)

    def record_eligible(self, record, state):
        return True


class ActiveCodec:
    def __init__(self, profile, host, source):
        self.state_profile, self.host, self.source = profile, host, source
        self.profile_id = PROFILE

    def validate_bridge(self, value):
        self.admit_bridge(value)

    def admit_bridge(self, value):
        check(value["hostId"] == self.host and value["sourceId"] == self.source, "active_source_binding")
        return self.inspect_native(value["ownerFrame"])

    def inspect_native(self, frame):
        NATIVE.validate(frame)
        check(frame["hostScope"] == self.host, "active_host_binding")
        projection = frame["projection"]
        sources = {(s["provider"], s["namespace"]): s for s in frame["sources"]}
        if projection is not None:
            for scope in projection["scopes"]:
                source = sources[scope["provider"], scope["namespace"]]
                for support in scope["coverage"]["supports"]:
                    component = next(c for c in source["components"] if c["name"] == support["component"])
                    check(support["serviceId"] == frame["serviceId"] and
                          support["contextGeneration"] == source["contextGeneration"] and
                          all(support[key] == component[key] for key in
                              ("accepted", "sampledBoottimeMs", "expiresBoottimeMs")), "active_support_binding")
        clock = re.fullmatch(r"time:\[([0-9]+)\]", frame["clockDomain"])
        check(clock is not None, "active_clock_binding")
        return NativeState(
            {"protocol": "agent-observer.active-feed", "version": 1,
             "metadata": None if projection is None else {k: v for k, v in projection.items() if k != "sessions"},
             "service": {k: v for k, v in frame.items() if k != "projection"}},
            () if projection is None else tuple(projection["sessions"]),
            {"bootId": frame["bootId"], "timeNamespace": "time:" + clock[1]},
            frame["serviceId"], frame["emittedBoottimeMs"],
            tuple({"sourceId": s["provider"] + ":" + s["namespace"], "component": c["name"],
                   "accepted": c["accepted"], "health": c["health"], "expiry": c["expiresBoottimeMs"]}
                  for s in frame["sources"] for c in s["components"]))


class ActiveSource:
    def __init__(self, host="fixture", *, empty=False):
        import asyncio

        self.frame = json.loads((Path(__file__).parent / "fixtures/active-feed-v1.json").read_text())
        shift = boottime_ms() - 100 - self.frame["emittedBoottimeMs"]
        clock = clock_domain()

        def rewrite(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "hostScope":
                        value[key] = host
                    elif key in {"sampledBoottimeMs", "expiresBoottimeMs", "emittedBoottimeMs"} and type(item) is int:
                        value[key] += shift
                    elif key == "bootId":
                        value[key] = clock["bootId"]
                    elif key == "clockDomain":
                        value[key] = "time:[" + clock["timeNamespace"].split(":")[1] + "]"
                    else:
                        rewrite(item)
            elif isinstance(value, list):
                for item in value:
                    rewrite(item)
        rewrite(self.frame)
        if empty:
            self.frame["projection"]["sessions"].clear()
            self.frame["projection"]["scopes"][0]["members"].clear()
        self.reads, self.watchers = 0, 0
        self.changes = asyncio.Queue()

    async def snapshot(self):
        self.reads += 1
        return copy.deepcopy(self.frame)

    async def watch(self):
        self.watchers += 1
        try:
            while True:
                yield CachedPublication(copy.deepcopy(self.frame), self.frame["serviceId"],
                                        {"revision": self.frame["viewRevision"]})
                await self.changes.get()
        finally:
            self.watchers -= 1
