"""Separate traced allocation/churn qualification; never decision CPU timing."""

import asyncio
import copy
import gc
import json
import sys
import tracemalloc
import weakref
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from prepared_fixture import StaticPreparation  # noqa: E402
from test_simplification import fleet  # noqa: E402
from tmux_observer.mesh_profile import TmuxMeshProfile  # noqa: E402

from mesh_plus.api import PreparedReadGuard  # noqa: E402


async def main():
    cases = []
    for hosts, rows in ((1, 32), (4, 32), (16, 32), (1, 1024)):
        _, _, frame = await fleet(hosts=hosts, rows=rows)
        profile = TmuxMeshProfile()
        kwargs = dict(profile=profile, preparation=StaticPreparation(profile))
        # Warm global schema state, outside the allocation observation.
        warm = PreparedReadGuard("tmux", "a" * 32, **kwargs)
        warm.accept(frame)
        warm.disconnect()
        del warm
        gc.collect()
        tracemalloc.start()
        guard = PreparedReadGuard("tmux", "a" * 32, **kwargs)
        guard.accept(frame)
        gc.collect()
        steady, first_peak = tracemalloc.get_traced_memory()
        generation = guard._generation
        body_bytes = len(generation.header) + sum(len(r.payload) + 1 for r in generation.rows)
        del generation
        clock = frame["mesh"]["reader"]["clock"]
        now = frame["mesh"]["reader"]["encodedAtMs"]
        for sequence in range(2, 130):
            previous = weakref.ref(guard._generation)
            replacement = copy.deepcopy(frame)
            replacement["mesh"]["reader"].update(sequence=sequence, revision=sequence)
            guard.accept(replacement)
            del replacement
            assert previous() is None, "retained_old_generation"
            actual = guard.current(now, clock)
            assert actual == frame["sessions"], "row_oracle"
            actual.clear()
            assert guard.snapshot() == {**frame, "mesh": {**frame["mesh"], "reader": {
                **frame["mesh"]["reader"], "sequence": sequence, "revision": sequence}}}
        gc.collect()
        after_churn, peak = tracemalloc.get_traced_memory()
        previous = weakref.ref(guard._generation)
        guard.disconnect()
        assert previous() is None and guard.snapshot() is None
        assert not guard.current(now, clock)
        del guard
        gc.collect()
        retired, _ = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        # Fixed overhead may grow briefly as Python/schema caches settle; a
        # retained full history would exceed this bound many times over.
        assert after_churn <= steady + 128 * 1024, "unbounded_retained_churn"
        cases.append(dict(hosts=hosts, rowsPerHost=rows, replacements=128, bodyBytes=body_bytes,
                          steadyTracedBytes=steady, firstAcceptPeakTracedBytes=first_peak,
                          afterChurnTracedBytes=after_churn, peakTracedBytes=peak,
                          afterDisconnectTracedBytes=retired, oldGenerationsReleased=True))
    print(json.dumps(dict(status="passed", cases=cases,
                         limits="tracemalloc allocations, not RSS/PSS; controlled fixed admission-time queries for churn; test-only compiler; no live fleet performance"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
