"""Instrumented pure-boundary attribution; never a carrier or resource acceptance."""

import argparse
import asyncio
import cProfile
import json
import pstats
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace import Trace  # noqa: E402

from run import inputs  # noqa: E402

from mesh_plus.api import CachedPublisher, Endpoint, Reader, ReadGuard  # noqa: E402
from mesh_plus.evidence import clock_domain  # noqa: E402
from mesh_plus.reader import PublicationState  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402


async def run(args):
    trace = Trace(args.rows)
    reads = 0

    class Native:
        async def snapshot(self):
            nonlocal reads
            reads += 1
            return trace.frame

        async def watch(self):
            raise AssertionError("pure diagnostic does not select watch")
            yield

    publisher = CachedPublisher("tmux", "beta", "controlled", Native(), profile=trace.profile)

    class Reply:
        codec = trace.codec.validate_bridge

        async def request(self, operation, parameters, **kwargs):
            value = await publisher.proof(parameters)
            publisher.validate(value)  # Bridge result boundary.
            self.codec(value)  # Client's pure callback boundary, no carrier.
            return value

    endpoint = Endpoint("beta", False, "sha256:" + "a" * 64, None, trace.codec)
    reader = Reader("tmux", [endpoint], local_host="alpha", catalog_revision="sha256:" + "b" * 64, profile=trace.profile)
    guard = ReadGuard("tmux", "c" * 32, profile=trace.profile)
    state = PublicationState()
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(args.rounds):
        outcome = await reader.read_host(Reply(), endpoint)
        value = reader.compose([endpoint], {"beta": outcome}, "c" * 32, "watch", state=state)
        guard.accept(value)
        if len(guard.current(boottime_ms(), clock_domain())) != args.rows:
            raise ValueError("diagnostic_current_rows")
    profiler.disable()
    guard.disconnect()
    functions = []
    categories = {name: 0.0 for name in ("mesh", "tmux-pure", "jsonschema", "copy-json", "other")}
    copy_callers = []
    for (filename, line, function), (_, calls, own, cumulative, callers) in pstats.Stats(profiler).stats.items():
        if filename.endswith("/copy.py") and function == "deepcopy":
            for (parent, parent_line, parent_function), counts in callers.items():
                if parent.endswith("/copy.py"):
                    continue
                copy_callers.append({"module": Path(parent).name, "line": parent_line, "function": parent_function,
                                     "calls": counts[1], "selfSeconds": counts[2], "cumulativeSeconds": counts[3]})
        category = ("mesh" if "/mesh_plus/" in filename else "tmux-pure" if "/tmux_observer/" in filename else
                    "jsonschema" if "/jsonschema/" in filename or "/referencing/" in filename else
                    "copy-json" if "/json/" in filename or filename.endswith("/copy.py") else "other")
        categories[category] += own
        if category != "other":
            functions.append({"category": category, "module": Path(filename).name, "line": line,
                              "function": function, "calls": calls, "selfSeconds": own, "cumulativeSeconds": cumulative})
    functions.sort(key=lambda value: value["cumulativeSeconds"], reverse=True)
    report = {"status": "passed", "inputs": inputs(), "rows": args.rows, "rounds": args.rounds,
              "nativeCachedReads": reads, "selfSecondsByCategory": categories, "functions": functions[:100],
              "externalDeepcopyCallers": sorted(copy_callers, key=lambda value: value["cumulativeSeconds"], reverse=True),
              "scope": "instrumented publisher+Bridge result+pure Client callback+Reader composition+consumer guard; no carrier/source I/O",
              "limits": ["cProfile overhead changes timings", "inclusive function times overlap and cannot be added",
                         "not carrier comparison or normal resource acceptance", "consumer fixture oracle excluded"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "nativeCachedReads": reads, "selfSecondsByCategory": categories}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--rounds", type=int, default=24)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists() or not 1 <= args.rounds <= 24:
        parser.error("new_absolute_output_and_bounded_rounds")
    asyncio.run(run(args))
