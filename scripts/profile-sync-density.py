#!/usr/bin/env python3
"""Normalized nine-field material stress, not an Agent or transport benchmark."""

import argparse
import datetime
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mesh_plus.protocol import check  # noqa: E402
from mesh_plus.sync._boundary import admission_boundary  # noqa: E402
from mesh_plus.sync.budget import AllocationLedger  # noqa: E402
from mesh_plus.sync.canonical import Atom, canonical  # noqa: E402
from mesh_plus.sync.commitment import (  # noqa: E402
    MerkleMap,
    binding_digest,
    body_digest,
    digest_parts,
    field_digest,
    framed,
    native_root,
)
from mesh_plus.sync.model import (  # noqa: E402
    SPACES,
    DomainIndexPatch,
    FieldTokenWrite,
    NativeTag,
    SyncDescriptor,
)
from mesh_plus.sync.reconstruction import Operation, ReconstructionStore  # noqa: E402

EPOCH = "11111111-1111-4111-8111-111111111111"
BIRTH = [EPOCH, 1]


class Profile:
    def __init__(self, view):
        self.descriptor = SyncDescriptor(f"reference.{view}-sync.v1", "00" * 32, "reference.sync", 1, "11" * 32,
                                         canonical({"protocol": "reference.sync", "version": 1, "view": view}))

    def admit_baseline(self, ctx):
        tokens = []
        descriptor = bytes.fromhex(self.descriptor.native_descriptor_digest)
        for op in ctx.changed("records"):
            with ctx.budget.reserve(4096 + op.key.materialization_bytes + op.value.materialization_bytes):
                identity, slot = op.key.materialize(), op.value.materialize()
                body = ctx.after.lookup("bodies", slot["body"])
                with ctx.budget.reserve(4096 + body.materialization_bytes):
                    value = body.materialize()
                    check(value["identity"] == identity and type(value["value"]) is int, "density_body")
                    ref = [identity, slot["birth"]]
                    # This fixture's bounded compact output: refs, token
                    # strings, dataclasses and simultaneous list/tuple slots.
                    ctx.budget.charge(1024 + 4 * len(canonical(ref)) + 256 * len(self.descriptor.fields))
                    for field in self.descriptor.fields:
                        token = field_digest(descriptor, identity, slot["birth"], field, {"value": value["value"]}).hex()
                        tokens.append(FieldTokenWrite(ref, field, token))
        return DomainIndexPatch(field_tokens=tuple(tokens))

    def stage_delta(self, ctx):
        return self.admit_baseline(ctx)

    def check_head(self, ctx, head):
        raise AssertionError("material stress must not request authority")

    def export_committed(self, view):
        raise AssertionError("material stress must not export")


def fixture(profile, count, generation=1):
    descriptor = bytes.fromhex(profile.descriptor.native_descriptor_digest)
    cohort = ["reference", "scope", "runtime"]
    tables, members = {name: [] for name in SPACES}, []
    for number in range(count):
        identity = ["fixture", "reference", "scope", "record", f"id-{number:08d}"]
        value = number + (generation - 1) * 100000 if number == 0 else number
        body = {"identity": identity, "value": value}
        digest = body_digest(descriptor, body).hex()
        tables["records"].append([identity, {"birth": BIRTH, "body": digest, "order": identity, "scope": "scope"}])
        tables["bodies"].append([digest, body])
        tables["observations"].append([[identity, BIRTH], {"stamp": generation if number == 0 else 1}])
        for field in profile.descriptor.fields:
            token = field_digest(descriptor, identity, BIRTH, field, {"value": value}).hex()
            tables["memberships"].append([[cohort, identity, BIRTH, field], token])
            members.append([[identity, BIRTH, field], token])
    member_root = MerkleMap.baseline("cohort-members", members)
    tables["cohorts"].append([cohort, {"seal": [generation, member_root.root.hex(), len(member_root)]}])
    binding = {"hostScope": "fixture", "ownerEpoch": EPOCH, "view": profile.descriptor.profile_id}
    maps = {name: MerkleMap.baseline(name, rows) for name, rows in tables.items()}
    tag = NativeTag(binding_digest(binding, native=True).hex(), generation, native_root(binding, generation, maps).hex())
    return binding, tag, tables


class Loader:
    def __init__(self, store):
        self.store = store

    @admission_boundary
    def baseline(self, binding, tag, tables):
        self.store.stage_baseline(binding, tag, (EPOCH, 1, tag.root), tables)
        self.store.advance_material()

    @admission_boundary
    def delta(self, base, target, operations):
        self.store.stage_delta(base, target, (EPOCH, target.generation, target.root), operations)
        self.store.advance_material()


def differences(before, after):
    result = []
    for name in SPACES:
        old = {canonical(key): (key, value) for key, value in before[name]}
        new = {canonical(key): (key, value) for key, value in after[name]}
        for encoded in old.keys() | new.keys():
            if encoded in old and encoded in new and canonical(old[encoded][1]) == canonical(new[encoded][1]):
                continue
            expected = (None if encoded not in old else
                        digest_parts(b"mesh-sync-value\0", framed(name.encode()), framed(canonical(old[encoded][1]))).hex())
            key, value = (new if encoded in new else old)[encoded]
            result.append(Operation(name, "put" if encoded in new else "remove", Atom.own(key), expected,
                                    Atom.own(value) if encoded in new else None))
    return tuple(result)


def source_hashes():
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted([*ROOT.glob("src/mesh_plus/**/*.py"), Path(__file__).resolve()])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts", type=int, nargs="+", default=[100, 500, 2000])
    parser.add_argument("--views", type=int, choices=(1, 2), default=2)
    parser.add_argument("--packed-nodes", action="store_true", help="private paged-node prototype; no public factory")
    parser.add_argument("--generations", type=int, choices=(1, 3), default=1,
                        help="three retains current/predecessor and stages one-row changes")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not output.is_relative_to(ROOT) or not all(1 <= count <= 2000 for count in args.counts):
        parser.error("use a new owning-repository output and counts in 1..2000")
    before, results, unexpected = source_hashes(), [], False
    for count in args.counts:
        ledger, stores, cases = AllocationLedger(), [], []
        arena = None
        if args.packed_nodes:
            from mesh_plus.sync._packed_nodes import PackedNodeArena
            arena = PackedNodeArena(ledger)
        try:
            for view in ("first", "second")[:args.views]:
                profile = Profile(view)
                started = time.process_time_ns()
                binding, tag, tables = fixture(profile, count)
                case = {"view": view, "records": count, "fieldsPerRecord": 9,
                        "fixtureCpuMs": (time.process_time_ns() - started) / 1e6}
                cases.append(case)
                try:
                    store = ReconstructionStore(profile, host="fixture", ledger=ledger)
                    stores.append(store)
                    started = time.process_time_ns()
                    Loader(store).baseline(binding, tag, tables)
                    case.update(status="material-only", admissionCpuMs=(time.process_time_ns() - started) / 1e6)
                    case["generations"] = [{"generation": 1, "root": tag.root, "accounted": ledger.inspect()}]
                    for generation in range(2, args.generations + 1):
                        _, target, updated = fixture(profile, count, generation)
                        changes = differences(tables, updated)
                        started = time.process_time_ns()
                        Loader(store).delta(tag, target, changes)
                        case["generations"].append({"generation": generation, "root": target.root,
                                                    "changedKeys": len(changes),
                                                    "admissionCpuMs": (time.process_time_ns() - started) / 1e6,
                                                    "accounted": ledger.inspect()})
                        tag, tables = target, updated
                except Exception as error:
                    code = str(error)[:128]
                    capacity = code in {"sync_decoded_capacity", "sync_encoded_capacity"}
                    unexpected |= not capacity
                    case.update(status="rejected", capacityRejected=capacity,
                                error={"type": type(error).__name__, "code": code})
                    break
                finally:
                    case["accounted"] = ledger.inspect()
                    if arena is not None:
                        case["packedNodes"] = arena.inspect()
                    tables = None
        finally:
            for store in stores:
                store.close()
            if arena is not None:
                arena.close()
        results.append({"recordsPerView": count, "views": cases, "afterClose": ledger.inspect()})
    report = {"kind": "normalized private-material density diagnostic; not acceptance",
              "privatePackedNodes": args.packed_nodes,
              "generationsPerView": args.generations,
              "cyclicGcEnabled": gc.isenabled(),
              "checkedAtUtc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "python": sys.version.split()[0], "sourceInputs": before,
              "sourceStableDuringRun": before == source_hashes(), "unexpectedFailure": unexpected, "results": results,
              "exclusions": ["not Agent full/active semantics or capacity", "no source/native frames, IPC, SSH or proof",
                             "no installed wheel or paired CPU/RSS/plateau evidence",
                             "caller-owned normalized fixtures/oracle outside cache ledger; not total process memory",
                             "minimal bodies and no declared domain indexes", "no sibling edits, service or rollout"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"sourceStableDuringRun": report["sourceStableDuringRun"], "results": results}, sort_keys=True))
    return int(not report["sourceStableDuringRun"] or unexpected)


if __name__ == "__main__":
    raise SystemExit(main())
