"""Bound actual private bucket metadata, including Reservation instance dicts."""

import argparse
import gc
import hashlib
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mesh = args.mesh.resolve()
    assert not args.output.exists()
    sys.path[:0] = [str(mesh / "src")]
    from mesh_plus.protocol import ProtocolError
    from mesh_plus.sync._patch_workspace import _IndexWorkspace
    from mesh_plus.sync.budget import AllocationLedger
    from mesh_plus.sync.canonical import Atom, packed

    gc.disable()
    ledger, rows = AllocationLedger(), []

    def reservation_size(credit):
        if credit is None:
            return 0
        # Field-name strings and ledger are shared framework owners. Include
        # every instance dictionary/container and the mutable amount integer.
        return (sys.getsizeof(credit) + sys.getsizeof(credit.__dict__) +
                (2 * sys.getsizeof(credit.amount) if credit.amount > 256 else 0))

    def measured(work):
        actual = sys.getsizeof(work) + reservation_size(work.credit) + reservation_size(work.entries_credit)
        if work.seen is not None:
            actual += 2 * sys.getsizeof(work.seen) + sum(sys.getsizeof(marker) for marker in work.seen)
        actual += 2 * sys.getsizeof(work.entries)
        for bucket in work.entries.values():
            actual += (sys.getsizeof(bucket) + reservation_size(bucket.credit) + 2 * sys.getsizeof(bucket.rows) +
                       sum(sys.getsizeof(row) for row in bucket.rows))
        funded = ((0 if work.credit is None else work.credit.amount) + work.entries_credit.amount +
                  sum(bucket.credit.amount for bucket in work.entries.values()))
        assert funded >= actual, (funded, actual)
        assert all(key._allocation_owner is ledger and value._allocation_owner is ledger
                   for bucket in work.entries.values() for key, value in bucket.rows)
        return dict(metadataBound=actual, metadataCredit=funded)

    with ledger.allocations():
        work = _IndexWorkspace(ledger, baseline=True)
        key = value = owned = None
        try:
            for count in range(1, 4097):
                name = "index" + str(count % 32)
                key, value = Atom.own([count, "雪"]), packed(Atom.own({"value": count}))
                owned = work.remember(name, key, "sync_duplicate_index_operation")
                work.append(name, owned, value)
                if count in (1, 2, 5, 8, 16, 32, 100, 500, 4096):
                    rows.append(dict(rows=count, phase="before-seen-retirement", **measured(work)))
            encoded = ledger.encoded + ledger.pending_encoded + ledger.encoded_reserved
            before = ledger.used + ledger.reserved
            credit = work.credit.amount
            work.finish_seen()
            assert ledger.used + ledger.reserved == before - credit
            assert ledger.encoded + ledger.pending_encoded + ledger.encoded_reserved == encoded
            rows.append(dict(rows=4096, phase="after-seen-retirement", **measured(work)))
            maximum = ledger.maximum
            ledger.maximum = ledger.used + ledger.reserved
            try:
                bucket = next(iter(work.entries.values()))
                size = len(bucket)
                try:
                    bucket.append(owned, value)
                except ProtocolError as error:
                    assert str(error) == "sync_decoded_capacity"
                else:
                    raise AssertionError("missing refusal")
                assert len(bucket) == size
                bucket = None
            finally:
                ledger.maximum = maximum
        finally:
            key = value = owned = None
            work.close()
            work.close()
    final = [ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
             ledger.pending_units, ledger.pending_encoded]
    assert final == [0] * 6 and not gc.isenabled()
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).suffix == ".py":
            path = Path(filename).resolve()
            if path.is_relative_to(mesh):
                loaded[str(path.relative_to(mesh))] = hashlib.sha256(path.read_bytes()).hexdigest()
    args.output.write_text(json.dumps(dict(python=sys.version.split()[0], checkpoints=rows,
        finalCounters=final, gcDisabled=True, loadedInputs=loaded,
        exclusions="Private metadata census includes instance dictionaries, bucket/list/tuple storage and resize overlap. Key/value Atom graphs are separately ledger-owned and excluded from metadata sum; no whole-process/RSS/CPU/producer acceptance."),
        indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
