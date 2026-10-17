"""Actual compact IPC intake plus Reader retention; diagnostic, not G2."""

import argparse
import asyncio
import gc
import hashlib
import json
import sys
import time
import traceback
import uuid
from pathlib import Path
from unittest.mock import patch


async def run(args):
    sys.path[:0] = [str(args.mesh / "src"), str(args.observer), str(args.observer / "tests")]
    from agent_observer.mesh_sync_codec import AgentCompactSyncCodec
    from agent_observer.mesh_sync_profile import AgentSyncProfile
    from agent_observer.service_state import ServiceState
    from agent_observer.sync_compact_source import CachedCompactAgentSyncSource
    from agent_observer.sync_native import parse_message
    from bench_sync_producer import native_shaped_snapshot
    from test_service_runtime import Running

    from mesh_plus.sync import OwnedSyncCache, source_binding
    from mesh_plus.sync._packed_nodes import PackedNodeArena
    from mesh_plus.sync.budget import AllocationLedger
    from mesh_plus.sync.canonical import canonical
    from mesh_plus.sync.inputs import input_bytes

    gc.disable()
    _boot, value, wall = native_shaped_snapshot(args.rows)
    reader_time = [100000]
    with patch("agent_observer.service_state.uuid.uuid4", return_value=uuid.UUID(int=61440)):
        owner = ServiceState(host_scope="fixture", configs={"codex": ("/fixture/codex", "explicit")},
                             sync_serialization="compact")
    owner.wall_clock = lambda: wall
    owner.collection_id = lambda: str(uuid.UUID(int=61440))
    def sample():
        sampled = owner.clock()
        for row in value["sessions"]:
            for field in ("lastUpdated", "latestTurn"):
                row[field]["receipt"].update(sampledBoottimeMs=sampled, observedBoottimeMs=sampled)
        return sampled
    owner.attempt("codex", "history")
    owner.accept("codex", "history", value, sampled_ms=sample(), ttl_ms=60000, runtime_ttl_ms=60000)
    ledger, phases, reserves, errors = AllocationLedger(), [], [], []
    peak_encoded, peak_reserved_calls = 0, 0
    original_reserve = AllocationLedger.reserve

    def tracked_reserve(current, amount, *, encoded=0):
        nonlocal peak_encoded, peak_reserved_calls
        try:
            result = original_reserve(current, amount, encoded=encoded)
        except BaseException as error:
            if current is ledger:
                reserves.append(dict(code=str(error), heap=amount, encoded=encoded,
                                     state=current.inspect()))
            raise
        if current is ledger:
            peak_reserved_calls += 1
            peak_encoded = max(peak_encoded, current.encoded + current.pending_encoded + current.encoded_reserved)
        return result

    def mark(name, **extra):
        phases.append(dict(phase=name, reader=ledger.inspect(), **extra))

    arena = cache = source = session = ticket = batch = None
    started = time.monotonic()
    outcome, failure = "incomplete", None
    stage = "construct"
    reader_clock = {"bootId": "reader-boot", "timeNamespace": "time:2"}
    profile = AgentSyncProfile(profile_schema_digest="a" * 64, view="full")
    binding = source_binding("fixture", "agents", profile.descriptor)
    request = {"readerEpoch": "r" * 32, "channelEpoch": "c" * 32,
               "bridgeId": "b" * 32, "hosts": ["fixture"], "route": "disposable-native-ipc"}
    codec = AgentCompactSyncCodec("full", encoding_id="fixture-compact/1", expected_host="fixture")

    async def confirm(candidate):
        # Test-owned nonce/native pin/proof carrier, never a network dispatcher.
        # Its head/proof copies have extra independent shared-ledger credit.
        with ledger.reserve(4 * 1024 * 1024, encoded=3 * 65536):
            challenge = cache._proof_request(candidate)
            ref = await session.head_after_nonce(challenge)
            with input_bytes(cache, ref) as (raw, _):
                head = parse_message(raw, "full", "fixture")
                raw = None
            bridge_time = head["ownerClock"]["boottimeMs"] + 1
            proof = {"protocol": "mesh.state-sync/1", "kind": "proof", "descriptor": cache.descriptor.wire(),
                     "sourceBinding": binding, "sourceTag": candidate.tag.wire(), "requestBinding": request,
                     "challenge": challenge, "bridgeId": request["bridgeId"],
                     "bridgeClock": {"bootId": head["ownerClock"]["bootId"],
                                     "timeNamespace": head["ownerClock"]["clockDomain"].replace("[", "").replace("]", ""),
                                     "boottimeMs": bridge_time}, "head": head,
                     "remaining": [[key, max(0, item["expiresBoottimeMs"] - bridge_time)
                                    if item["health"] in {"current", "partial"} else 0]
                                   for key, item in head["originalReceipts"]]}
            reader_time[0] += 20
            result = cache.confirm(candidate, canonical(proof), reader_clock)
            head = proof = None
            return result

    meter = patch.object(AllocationLedger, "reserve", tracked_reserve)
    meter.start()
    try:
        with patch.object(AllocationLedger, "reserve", tracked_reserve):
            if args.backend == "packed":
                arena = PackedNodeArena(ledger)  # explicit private owning prototype
            cache = OwnedSyncCache(profile, binding, request_binding=request, native_codec=codec,
                                   ledger=ledger, _clock=reader_clock, _now_ms=lambda: reader_time[0])
            with Running(state=owner) as server:
                source = CachedCompactAgentSyncSource("fixture", server.path, view="full", timeout=15)
                session = source.open_session(cache.input_owner())
                mark("source-open")
                stage = "baseline-receive"
                ticket = await session.baseline()
                mark("baseline-received", rawBytes=ticket.data.nbytes)
                stage = "baseline-admit"
                candidate = cache.admit_baseline(ticket.data)
                ticket.close()
                ticket = None
                assert candidate.tag.native.wire() == list(owner.sync_current_tag("full"))
                mark("baseline-admitted", tag=candidate.tag.native.wire())
                stage = "baseline-confirm"
                await confirm(candidate)
                mark("baseline-confirmed")
                for generation in range(2):
                    stage = f"generation-{generation + 1}"
                    base = owner.sync_current_tag("full")
                    value["sessions"][generation]["title"] += " changed"
                    owner.attempt("codex", "history")
                    owner.accept("codex", "history", value, sampled_ms=sample(),
                                 ttl_ms=60000, runtime_ttl_ms=60000)
                    target = owner.sync_current_tag("full")
                    cache.revoke("screen_head_moved")
                    batch = await session.changes_with_completion(base, target=target)
                    if not hasattr(batch, "transactions"):
                        raise RuntimeError("native_recovery_control:" + batch.status + ":" + batch.reason)
                    assert type(batch.transactions) is tuple and 0 < len(batch.transactions) <= 4
                    assert batch.completion.status == "complete"
                    mark(stage + "-received", transactionBytes=sum(ref.nbytes for ref in batch.transactions),
                         controlBytes=batch.completion.data.nbytes, transactionCount=len(batch.transactions))
                    for index, ref in enumerate(batch.transactions):
                        candidate = cache.stage(ref)
                        mark(stage + f"-staged-{index}", tag=candidate.tag.native.wire())
                    assert candidate.tag.native.wire() == list(target)
                    batch.close()
                    batch = None
                    await confirm(candidate)
                    mark(stage + "-confirmed")
                outcome = "baseline-and-two-generations-confirmed"
    except BaseException as error:
        errors.append(error)  # retain the actual failed operation/trace with GC disabled
        failure = dict(stage=stage, type=type(error).__name__, code=str(error),
                       trace="".join(traceback.format_exception(error)))
        outcome = "refused-or-failed"
        mark("failure", stage=stage)
    finally:
        try:
            if ticket is not None:
                ticket.close()
            if batch is not None:
                batch.close()
            if session is not None:
                await session.aclose()
            if source is not None:
                await source.aclose()
            if cache is not None:
                cache.close()
            if arena is not None:
                arena.close()
            native_account = native_memberships = None
            if owner._sync_cache is not None:
                account = owner._sync_cache.account
                native_account = account.snapshot()
                native_memberships = owner._sync_cache.views["full"].current.tables["memberships"].count
                owner._sync_cache.close()
                assert account.snapshot()["used"] == account.snapshot()["base"]
        finally:
            meter.stop()
    counters = [ledger.used, ledger.reserved, ledger.encoded, ledger.encoded_reserved,
                ledger.pending_units, ledger.pending_encoded]
    loaded = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename and Path(filename).suffix == ".py":
            path = Path(filename).resolve()
            for name, root in (("mesh", args.mesh), ("observer", args.observer)):
                if path.is_relative_to(root):
                    loaded[name + "/" + str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(rows=args.rows, backend=args.backend, python=sys.version.split()[0], gcDisabled=not gc.isenabled(),
                  outcome=outcome, failure=failure, phases=phases, heapPeak=ledger.peak,
                  encodedPeakReservedBound=peak_encoded, reservationCalls=peak_reserved_calls,
                  reservationRefusals=reserves, finalCounters=counters, loadedInputs=loaded,
                  nativeOwnerAccount=native_account, nativeMembershipCells=native_memberships,
                  workload="full-only; baseline plus two single-body changes with whole native timing-receipt refresh; not an O(K) or dense9 claim",
                  elapsedDiagnosticSeconds=time.monotonic()-started,
                  exclusions="Synthetic native-shape fixture: not dense9. Actual disposable Runtime/source IPC and all source+Reader reservations share one Reader ledger; native owner has its separate account. Private packed backend if selected. Test nonce/native pin/proof carrier with extra prepaid fixture scratch; synthetic clocks, no absolute end-to-end deadline gate; no relay/controller/auth/selected-route, inclusive-process RSS/physical-heap/CPU/2k recovery/native/installed acceptance. No detached full DTO oracle.")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    assert counters == [0] * 6, counters
    print(json.dumps({key:result[key] for key in ("rows","backend","python","outcome","heapPeak","encodedPeakReservedBound","finalCounters")} | {"failure":failure and failure["code"]}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mesh", type=Path, required=True)
    parser.add_argument("--observer", type=Path, required=True)
    parser.add_argument("--rows", type=int, choices=(100,500,2000), required=True)
    parser.add_argument("--backend", choices=("default","packed"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.mesh, args.observer = args.mesh.resolve(), args.observer.resolve()
    assert not args.output.exists(), "preserve prior evidence"
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
