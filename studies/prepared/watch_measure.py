"""Persistent changing-watch CPU and separate traced legacy/prepared allocation."""

import argparse
import asyncio
import gc
import hashlib
import importlib.metadata
import json
import sys
import time
import tracemalloc
import weakref
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepared_fixture import StaticPreparation  # noqa: E402
from test_simplification import fleet  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402
from watch_workload import normalized_digest, oracle, publications  # noqa: E402

from mesh_plus.api import PreparedReadGuard, ReadGuard  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402
from mesh_plus.view import profile_validator  # noqa: E402


async def main(args):
    _, _, seed = await fleet(hosts=args.hosts, rows=32)
    profile = TmuxMeshProfile()
    frames = publications(seed, profile, args.publications, args.change)
    expected = [oracle(frame["sessions"]) for frame in frames]
    clock = seed["mesh"]["reader"]["clock"]
    constructor = ReadGuard if args.mode == "legacy" else PreparedReadGuard

    def new_guard():
        kwargs = {} if args.mode == "legacy" else {"preparation": StaticPreparation(profile)}
        return constructor("tmux", "a" * 32, profile=profile, **kwargs)

    def consume(guard, frame, identities, *, fixed=False):
        guard.accept(frame)
        for _ in range(args.reads):
            now = seed["mesh"]["reader"]["encodedAtMs"] if fixed else boottime_ms()
            rows = guard.current(now, clock)
            if oracle(rows) != identities:
                raise ValueError("watch_row_oracle")

    def lifetime():
        guard = new_guard()
        try:
            for frame, identities in zip(frames, expected):
                consume(guard, frame, identities)
        finally:
            guard.disconnect()
        if guard.current(boottime_ms(), clock):
            raise ValueError("retired_positive")

    # Untimed mandatory assertion: each changed publication incurs one full
    # profile-schema validation in both paths. Never patch inside decision CPU.
    validator = profile_validator("tmux", profile.descriptor.profile_id)
    validate = type(validator).validate
    calls = 0

    def counted(instance, *values, **kwargs):
        nonlocal calls
        calls += instance is validator
        return validate(instance, *values, **kwargs)

    # Start preflight from a deliberately different valid schema digest.
    other = publications(seed, profile, args.publications + 1, args.change)[-1]
    from mesh_plus.api import validate_response
    validate_response(other, profile=profile)
    with patch.object(type(validator), "validate", counted):
        lifetime()
    if calls != len(frames):
        raise ValueError("watch_schema_admission_count")

    report = dict(status="passed", mode=args.mode, hosts=args.hosts, rowsPerHost=32,
                  reads=args.reads, publications=args.publications, change=args.change,
                  inputOracleSha256=normalized_digest(frames), preflightSchemaAdmissions=calls,
                  sourceAcquisitions=0, cleanup=True, python=sys.version.split()[0],
                  meshVersion=importlib.metadata.version("mesh-plus"),
                  harnessDigests={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                  (Path(__file__), Path(__file__).with_name("watch_workload.py"),
                                   ROOT / "tests/prepared_fixture.py")})
    import mesh_plus
    package = Path(mesh_plus.__file__).parent
    report["runtimeDigests"] = {name: hashlib.sha256((package / name).read_bytes()).hexdigest()
                                for name in ("api.py", "view.py", "prepared.py", "state.py",
                                             "schemas/read-schema.json", "schemas/read-tmux.profile.schema.json")}
    if args.memory:
        gc.collect()
        tracemalloc.start()
        guard = new_guard()
        consume(guard, frames[0], expected[0], fixed=True)
        gc.collect()
        steady, _ = tracemalloc.get_traced_memory()
        for frame, identities in zip(frames[1:], expected[1:]):
            previous = weakref.ref(guard._generation) if args.mode == "prepared" else None
            consume(guard, frame, identities, fixed=True)
            if previous is not None and previous() is not None:
                raise ValueError("old_generation_retained")
        gc.collect()
        retained, peak = tracemalloc.get_traced_memory()
        guard.disconnect()
        del guard
        gc.collect()
        retired, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report.update(steadyTracedBytes=steady, retainedTracedBytes=retained, peakTracedBytes=peak,
                      retiredTracedBytes=retired, allocations="guard-only; input frames prebuilt; fixed admitted-time query; not RSS/PSS")
    else:
        cpu, wall = time.process_time_ns(), time.perf_counter_ns()
        for _ in range(args.cycles):
            lifetime()
        report.update(cpuNs=time.process_time_ns() - cpu, wallNs=time.perf_counter_ns() - wall,
                      cycles=args.cycles, admissions=args.cycles * len(frames),
                      queries=args.cycles * len(frames) * args.reads,
                      scope="persistent consumer only; changing admitted fixtures; no source/network I/O; no timed counters/tracing")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("legacy", "prepared"), required=True)
    parser.add_argument("--hosts", type=int, choices=(1, 4, 16), required=True)
    parser.add_argument("--reads", type=int, choices=(1, 4, 16), required=True)
    parser.add_argument("--change", choices=("envelope", "native"), required=True)
    parser.add_argument("--publications", type=int, default=8)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--memory", action="store_true")
    args = parser.parse_args()
    if not 2 <= args.publications <= 128 or not 1 <= args.cycles <= 4:
        parser.error("bounded_watch_work")
    asyncio.run(main(args))
