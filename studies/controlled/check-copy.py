"""Differential ownership and full-pipeline CPU screening for a private hypothesis."""

import argparse
import asyncio
import copy
import json
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from trace import Trace  # noqa: E402

from copy_hypothesis import owned_copy  # noqa: E402

from mesh_plus import publisher as publisher_module  # noqa: E402
from mesh_plus import reader as reader_module  # noqa: E402
from mesh_plus.api import CachedPublisher, Endpoint, Reader, ReadGuard  # noqa: E402
from mesh_plus.evidence import clock_domain  # noqa: E402
from mesh_plus.reader import PublicationState  # noqa: E402
from mesh_plus.transport import boottime_ms  # noqa: E402


def differential():
    class Custom(dict):
        pass

    alias = {"values": [1, 2, None, True, 1.25]}
    cycle = []
    cycle.append(cycle)
    inputs = [None, True, 17, 1.25, "text", [alias, alias], {"left": alias, "right": alias},
              cycle, Custom(value=alias), {1: alias}, {"tuple": (alias, alias)}, ({"shared": alias}, [alias])]
    outcomes = []
    for value in inputs:
        reference = copy.deepcopy(value)
        candidate = owned_copy(value)
        if value is cycle:
            assert candidate[0] is candidate and candidate is not value
        else:
            assert type(candidate) is type(reference) and candidate == reference
        if isinstance(candidate, list) and value is not cycle:
            assert candidate[0] is candidate[1] and candidate[0] is not alias
        if isinstance(candidate, dict) and "left" in candidate:
            assert candidate["left"] is candidate["right"] and candidate["left"] is not alias
        if isinstance(value, tuple):
            assert candidate[0]["shared"] is candidate[1][0] and candidate[1][0] is not alias
        outcomes.append("passed")
    return len(outcomes)


async def pipeline(rounds, candidate):
    trace = Trace(32, expired=True)

    class Native:
        async def snapshot(self):
            return trace.frame

        async def watch(self):
            raise AssertionError("not selected")
            yield

    pub = CachedPublisher("tmux", "beta", "controlled", Native(), profile=trace.profile)

    class Reply:
        codec = trace.codec.validate_bridge

        async def request(self, operation, parameters, **kwargs):
            value = await pub.proof(parameters)
            pub.validate(value)
            self.codec(value)
            return value

    endpoint = Endpoint("beta", False, "sha256:" + "a" * 64, None, trace.codec)
    reader = Reader("tmux", [endpoint], local_host="alpha", catalog_revision="sha256:" + "b" * 64, profile=trace.profile)
    guard = ReadGuard("tmux", "c" * 32, profile=trace.profile)
    state = PublicationState()
    copier = SimpleNamespace(deepcopy=owned_copy if candidate else copy.deepcopy)
    # Explicit study-local modules only. The stdlib and Tmux facade are unchanged.
    with patch.object(publisher_module, "copy", copier), patch.object(reader_module, "copy", copier):
        started = time.process_time()
        for _ in range(rounds):
            outcome = await reader.read_host(Reply(), endpoint)
            value = reader.compose([endpoint], {"beta": outcome}, "c" * 32, "watch", state=state)
            guard.accept(value)
            assert not guard.current(boottime_ms(), clock_domain())
        elapsed = time.process_time() - started
    return elapsed


async def run(args):
    comparisons = differential()
    blocks = []
    for number in range(4):
        times = [await pipeline(args.rounds, candidate) for candidate in (False, True, True, False)]
        a, b = statistics.mean((times[0], times[3])), statistics.mean((times[1], times[2]))
        blocks.append({"block": number, "cpuSeconds": times, "cpuReductionPercent": 100 * (1 - b / a)})
    report = {"status": "passed_differential_screen", "ownershipCases": comparisons, "rounds": args.rounds,
              "blocks": blocks, "scope": "private module-local copy prototype; unchanged native/proof/consumer admission; expired fixed 32-row pure pipeline",
              "excluded": ["packaged runtime candidate", "carrier or positive receipt resource acceptance", "promotion"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=80)
    args = parser.parse_args()
    if not args.output.is_absolute() or args.output.exists() or not 1 <= args.rounds <= 100:
        parser.error("bounded_new_output")
    asyncio.run(run(args))
