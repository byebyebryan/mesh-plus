"""Independent normalized roots and per-generation sparse work; source only."""
import gc
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("density_fixture", ROOT / "scripts/profile-sync-density.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from mesh_plus.sync._packed_nodes import PackedNodeArena  # noqa: E402


def main():
    output = Path(__file__).with_name("packed-node-sparse-work.json")
    if output.exists():
        raise SystemExit("preserve prior evidence")
    gc.disable()
    before, cases = fixture.source_hashes(), []
    for count in (100, 500, 2000):
        ledger = fixture.AllocationLedger()
        arena = PackedNodeArena(ledger)
        profile = fixture.Profile("sparse")
        store = fixture.ReconstructionStore(profile, host="fixture", ledger=ledger)
        generations = []
        try:
            binding, tag, tables = fixture.fixture(profile, count)
            loader = fixture.Loader(store)
            loader.baseline(binding, tag, tables)
            maps = [table for _, table in (*store.current.tables, *store.current.indexes)]
            maps += [tree for _, (_, tree) in store.current.groups]
            meters = {id(table.work): table.work for table in maps}
            maps = None  # instrumentation must not pin an old map generation
            for generation in (2, 3):
                _, target, updated = fixture.fixture(profile, count, generation)
                operations = fixture.differences(tables, updated)
                work_before = {id(meter): meter.snapshot() for meter in meters.values()}
                reads, allocations, released = arena.record_reads, ledger.visited, arena.released_nodes
                loader.delta(tag, target, operations)
                work = {name: sum(getattr(meter, name) - work_before[id(meter)][name] for meter in meters.values())
                        for name in next(iter(meters.values())).__slots__}
                assert len(operations) == 14
                assert work["iterated_entries"] == 1  # the one bounded cohort head
                assert store.current.tag == target
                generations.append({"generation": generation, "independentNativeRoot": target.root,
                                    "changedKeys": len(operations), "work": work,
                                    "actualPackedRecordReads": arena.record_reads - reads,
                                    "newAllocationVisits": ledger.visited - allocations,
                                    "releasedNodes": arena.released_nodes - released,
                                    "callbackLookups": store.last_work["callbackLookups"],
                                    "callbackIterations": store.last_work["callbackIterations"]})
                tag, tables = target, updated
        finally:
            maps = meters = None
            store.close()
            arena.close()
        assert (ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
                ledger.pending_units, ledger.pending_encoded) == (0, 0, 0, 0, 0, 0)
        cases.append({"records": count, "generations": generations, "afterClose": ledger.inspect()})
    report = {"scope": "private normalized sparse material work, not Agent or performance acceptance",
              "meshRuntime": "18e95c1791e66d20a211aa7d96b44d49b7fb78b7", "cyclicGcEnabled": gc.isenabled(),
              "sourceInputs": before, "sourceStableDuringRun": before == fixture.source_hashes(), "cases": cases}
    assert report["sourceStableDuringRun"]
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"stable": True, "cases": cases}))


if __name__ == "__main__":
    main()
