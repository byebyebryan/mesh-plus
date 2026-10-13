"""Unprofiled owned pure admission/publisher pipeline; no carrier-performance claim."""

import argparse
import asyncio
import copy
import hashlib
import importlib.metadata
import json
import resource
import sys
import time
from pathlib import Path

from mesh_plus.api import CachedPublisher, Endpoint, Reader, ReadGuard, current_sessions, validate_response
from mesh_plus.evidence import clock_domain
from mesh_plus.reader import PublicationState
from mesh_plus.testing.sample import Profile, Publisher
from mesh_plus.transport import boottime_ms


class CountingProfile:
    def __init__(self, native=False):
        if native:
            from tmux_observer.mesh_profile import TmuxMeshProfile
            self.base = TmuxMeshProfile()
        else:
            self.base = Profile("tmux")
        self.descriptor = self.base.descriptor
        self.classifications = 0

    def __getattr__(self, name):
        return getattr(self.base, name)

    def record_host(self, row):
        self.classifications += 1
        return self.base.record_host(row)


async def run(args):
    profile = CountingProfile(args.native_profile)
    native_reads = 0
    sources, endpoints = [], []
    for index in range(args.hosts):
        host = "host" + str(index)
        native = Publisher("tmux", host, profile=profile)
        seed = native.frame["snapshot"]["sessions"][0]
        native.frame["snapshot"]["sessions"] = [{**copy.deepcopy(seed), "sessionId": "$" + str(100 + n)} for n in range(args.rows)]
        frame = native.frame

        class Source:
            def __init__(self, frame):
                self.frame = frame

            async def snapshot(self):
                nonlocal native_reads
                native_reads += 1
                return self.frame

            async def watch(self):
                raise AssertionError("pure pipeline does not replace actual push testing")
                yield

        publisher = CachedPublisher("tmux", host, "default", Source(frame), profile=profile)
        sources.append(publisher)
        endpoints.append(Endpoint(host, index == 0, None if index == 0 else "sha256:" + "b" * 64,
                                  None, profile.bind(host, "default")))
    reader = Reader("tmux", endpoints, local_host="host0", catalog_revision="sha256:" + "a" * 64, profile=profile)
    state = PublicationState()
    guard = ReadGuard("tmux", "a" * 32, profile=profile)
    expected = [(endpoint.host, "$" + str(100 + n)) for endpoint in endpoints for n in range(args.rows)]
    original = [copy.deepcopy(p.native.frame["receipt"]) for p in sources]

    async def pipeline():
        outcomes = {}
        for endpoint, publisher in zip(endpoints, sources, strict=True):
            class Reply:
                codec = publisher.codec.validate_bridge

                async def request(self, operation="snapshot", parameters=None, **kwargs):
                    value = await publisher.snapshot({}) if parameters is None else await publisher.proof(parameters)
                    publisher.validate(value)  # Real Bridge result admission boundary.
                    self.codec(value)  # Real Client owner callback boundary.
                    return value
            outcomes[endpoint.host] = await reader.read_host(Reply(), endpoint)
        response = reader.compose(endpoints, outcomes, "a" * 32, "watch", state=state)
        guard.accept(response)
        return guard.current(boottime_ms(), clock_domain())

    await pipeline()
    response = guard.view
    control = {"protocol": response["protocol"], "schemaVersion": 1,
               "mesh": {key: response["mesh"][key] for key in ("meshProtocol", "requestId", "operation", "access")}}
    control["mesh"].update(reader=copy.deepcopy(response["mesh"]["reader"]), kind="heartbeat")
    error = {"meshProtocol": 1, "requestId": "a" * 32, "error": {"code": "scope_changed", "message": "fixture terminal"}}

    async def operation():
        if args.phase == "pipeline":
            return await pipeline()
        if args.phase == "admission":
            validate_response(response, profile=profile)
            return current_sessions(response, boottime_ms(), clock_domain(), profile=profile)
        if args.phase == "heartbeat":
            control["mesh"]["reader"]["sequence"] += 1
            control["mesh"]["reader"]["encodedAtMs"] = boottime_ms()
            guard.accept(control)
        else:
            ReadGuard("tmux", "a" * 32, profile=profile).accept(error)
        return None

    # Warm schema/input paths separately; no acquisition or copy cost omitted
    # inside measured pipeline. Reports expose oracle-inclusive workload scope.
    await operation()
    before_reads = native_reads
    before_classifications = profile.classifications
    cpu, wall = time.process_time_ns(), time.perf_counter_ns()
    for _ in range(args.rounds):
        result = await operation()
        if result is not None and [(r["hostId"], r["sessionId"]) for r in result] != expected:
            raise ValueError("independent_consumer_rows")
    cpu_ns, wall_ns = time.process_time_ns() - cpu, time.perf_counter_ns() - wall
    if [p.native.frame["receipt"] for p in sources] != original:
        raise ValueError("receipts_renewed")
    reads = native_reads - before_reads
    if reads != (args.rounds * args.hosts if args.phase == "pipeline" else 0):
        raise ValueError("source_work_mismatch")
    guard.disconnect()
    if guard.current(boottime_ms(), clock_domain()):
        raise ValueError("disconnect_did_not_revoke")
    import mesh_plus
    runtime = Path(mesh_plus.__file__).parent
    return {"status": "passed", "phase": args.phase, "hosts": args.hosts, "rowsPerHost": args.rows,
            "rounds": args.rounds, "nativeProfile": args.native_profile, "expectedRowsSha256": hashlib.sha256(json.dumps(expected).encode()).hexdigest(), "nativeReads": reads, "classifications": profile.classifications - before_classifications,
            "cpuNs": cpu_ns, "wallNs": wall_ns, "peakRssKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "python": sys.version.split()[0], "packages": {n: importlib.metadata.version(n) for n in
                ("mesh-plus", "jsonschema", "attrs", "referencing", "rpds-py")},
            "runtimeSha256": hashlib.sha256(b"".join(p.relative_to(runtime).as_posix().encode() + p.read_bytes()
                for p in sorted(runtime.rglob("*")) if p.suffix in {".py", ".json"})).hexdigest(),
            "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "cleanup": True, "scope": "same installed pure Tmux fixture profile, owner proof/Reader/Guard boundaries; oracle inclusive, no carrier/source I/O"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("admission", "pipeline", "heartbeat", "error"), required=True)
    parser.add_argument("--hosts", type=int, choices=(1, 4, 16), default=1)
    parser.add_argument("--rows", type=int, choices=(1, 32, 128), default=32)
    parser.add_argument("--rounds", type=int, default=8)
    parser.add_argument("--native-profile", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.rounds <= 1000:
        parser.error("bounded_rounds")
    print(json.dumps(asyncio.run(run(args))))
