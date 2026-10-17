"""Private scalar allocation-type audit; diagnostic, no timing/physical claim."""

import argparse
import asyncio
import fcntl
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.mesh, args.observer = args.mesh.resolve(), args.observer.resolve()
    assert not args.output.exists(), "preserve prior audit"
    sys.path[:0] = [str(args.mesh / "src")]
    from mesh_plus.sync._allocation import TrackedAllocation
    from mesh_plus.sync.budget import AllocationLedger
    from mesh_plus.sync.reconstruction import BudgetRef

    bins, charges, failed_retains = {}, {}, []
    create, forget = AllocationLedger._create, AllocationLedger._forget
    adopt, discard, retain = (AllocationLedger.adopt_pending,
                              AllocationLedger.discard_pending, AllocationLedger.retain)
    charge = BudgetRef.charge

    def charged(budget, amount):
        # Read caller location without retaining a frame or its borrowed roots.
        location = Path(sys._getframe(1).f_code.co_filename).name + ":" + str(sys._getframe(1).f_lineno)
        row = charges.setdefault(location, dict(calls=0, bytes=0))
        row["calls"] += 1
        row["bytes"] += amount
        return charge(budget, amount)

    def add(value, sign, cost, encoded):
        row = bins.setdefault(type(value).__name__, dict(count=0, heap=0, encoded=0))
        for key, amount in (("count", 1), ("heap", cost), ("encoded", encoded)):
            row[key] += sign * amount
        assert all(amount >= 0 for amount in row.values()), row

    def new(ledger, value, cost, encoded):
        create(ledger, value, cost, encoded)
        add(value, 1, cost, encoded)

    def dropped(ledger, value, state):
        cost, encoded = ((state._allocation_cost, state._allocation_encoded)
                         if isinstance(value, TrackedAllocation) else (state.cost, state.encoded))
        forget(ledger, value, state)
        add(value, -1, cost, encoded)

    def pending(ledger, value, reservation):
        adopt(ledger, value, reservation)
        add(value, 1, value._allocation_cost, value._allocation_encoded)

    def discarded(ledger, value):
        cost, encoded = value._allocation_cost, value._allocation_encoded
        discard(ledger, value)
        add(value, -1, cost, encoded)

    def retaining(ledger, root, **kwargs):
        try:
            return retain(ledger, root, **kwargs)
        except BaseException:
            # Scalars only: no allocation/graph/root/error history is retained.
            failed_retains.append(dict(rootType=type(root).__name__, ledger=ledger.inspect(),
                                       liveTypes={key: dict(row) for key, row in bins.items()},
                                       cumulativeStageCharges={key: dict(row) for key, row in charges.items()}))
            raise

    spec = importlib.util.spec_from_file_location("reader_intake_probe", Path(__file__).with_name("probe_reader_intake.py"))
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    args.rows, args.backend = 2000, "packed"
    with Path("/home/bryan/.cache/agent-active-feed-cpu.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with (patch.object(AllocationLedger, "_create", new), patch.object(AllocationLedger, "_forget", dropped),
              patch.object(AllocationLedger, "adopt_pending", pending),
              patch.object(AllocationLedger, "discard_pending", discarded),
              patch.object(BudgetRef, "charge", charged),
              patch.object(AllocationLedger, "retain", retaining)):
            asyncio.run(probe.run(args))
    assert all(all(amount == 0 for amount in row.values()) for row in bins.values()), bins
    result = json.loads(args.output.read_text())
    result["privateScalarAllocationAudit"] = dict(
        failedRetains=failed_retains, finalTypes=bins, cumulativeStageCharges=charges,
        exclusions="Additional private ledger method wrappers observe only scalar costs/types, including pending units. Reserved pages/schema/parser/input scratch are separate ledger reservation totals. No per-roster audit registry or copied graph, no resource/CPU/RSS acceptance; instrumentation timing excluded.")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for failure in failed_retains:
        print(json.dumps(dict(rootType=failure["rootType"], ledger=failure["ledger"],
                              liveTypes=sorted(failure["liveTypes"].items(), key=lambda item: item[1]["heap"], reverse=True)[:8],
                              cumulativeStageCharges=sorted(failure["cumulativeStageCharges"].items(),
                                                            key=lambda item: item[1]["bytes"], reverse=True))))


if __name__ == "__main__":
    main()
