"""Complete consumer lifetimes, including preparation; no SDK promotion claim."""

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from test_simplification import fleet  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepared import PreparedGuard  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import ReadGuard  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402


async def main(args):
    _, _, response = await fleet(hosts=args.hosts, rows=32)
    profile = TmuxMeshProfile()
    expected = [("host" + str(host), "$" + str(100 + row)) for host in range(args.hosts) for row in range(32)]
    clock = response["mesh"]["reader"]["clock"]
    constructor = ReadGuard if args.mode == "legacy" else PreparedGuard

    def lifetime():
        guard = constructor("tmux", "a" * 32, profile=profile)
        guard.accept(response)
        for _ in range(args.reads):
            rows = guard.current(boottime_ms(), clock)
            if [(r["hostId"], r["sessionId"]) for r in rows] != expected:
                raise ValueError("current_row_oracle")
        guard.disconnect()
        if guard.current(boottime_ms(), clock):
            raise ValueError("retired_positive")

    lifetime()
    cpu, wall = time.process_time_ns(), time.perf_counter_ns()
    for _ in range(args.cycles):
        lifetime()
    cpu, wall = time.process_time_ns() - cpu, time.perf_counter_ns() - wall
    return {"status": "passed", "mode": args.mode, "hosts": args.hosts, "rowsPerHost": 32, "reads": args.reads,
            "cycles": args.cycles, "cpuNs": cpu, "wallNs": wall, "admissions": args.cycles,
            "queries": args.reads * args.cycles, "sourceAcquisitions": 0, "cleanup": True,
            "expectedRowsSha256": hashlib.sha256(json.dumps(expected).encode()).hexdigest(),
            "harnessSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "limits": "sealed study consumer; includes double full preparation admission and oracle; installed Tmux a7 facade; no transport/source I/O"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("legacy", "prepared"), required=True)
    parser.add_argument("--hosts", type=int, choices=(1, 4), required=True)
    parser.add_argument("--reads", type=int, choices=(1, 4, 16), required=True)
    parser.add_argument("--cycles", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 32:
        parser.error("bounded_cycles")
    print(json.dumps(asyncio.run(main(args))))
