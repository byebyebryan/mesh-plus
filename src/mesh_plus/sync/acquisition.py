"""Captured-head acquisition, compact proof and one separate moved-head retry."""

import asyncio
import secrets
from dataclasses import dataclass

from ..protocol import check
from ..transport import boottime_ms, finish_owned, within_deadline
from ._boundary import async_admission_boundary
from .cache import MovedHead, ResyncRequired
from .wire import MAX_NATIVE, MAX_PROOF


@dataclass(frozen=True, slots=True)
class AcquisitionResult:
    view: object
    baselines: int
    transactions: int
    proofs: int
    moved_heads: int
    material_bytes: int
    proof_bytes: int


@async_admission_boundary
async def acquire(cache, endpoint, *, clock, deadline_ms=None, _now=boottime_ms, _until=within_deadline):
    """Use an already source-bound owned endpoint; never collect or fall back.

    Endpoint.baseline/changes return immutable native bytes. Endpoint.proof
    returns the exact source/request-bound Mesh proof envelope. The endpoint
    owns and retires its pending I/O on cancellation; its Reader owns close.
    """
    started = _now()
    deadline = started + 15000 if deadline_ms is None else deadline_ms
    check(type(deadline) is int and started < deadline <= started + 15000, "sync_acquisition_deadline")
    baselines = transactions = proofs = moved = byte_count = proof_bytes = 0
    token = secrets.token_hex(16)
    with cache._lock:
        cache._check()
        check(cache._acquisition is None, "sync_acquisition_in_progress")
        cache._acquisition = token

    def alive():
        check(_now() < deadline, "sync_acquisition_deadline")

    async def io(awaitable, limit):
        # Revoke in this operation before waiting for nested endpoint cleanup.
        # The shield leaves ownership here on cancellation; the finally block
        # cancels and awaits the task despite repeated caller cancellation.
        job = asyncio.create_task(_until(awaitable, limit))
        try:
            return await asyncio.shield(job)
        except BaseException:
            cache.disconnect()
            raise
        finally:
            if not job.done():
                job.cancel()
            await finish_owned(asyncio.gather(job, return_exceptions=True))

    async def baseline():
        nonlocal baselines, byte_count
        alive()
        cache.revoke("baseline_pending")
        cache._discard_candidate()
        cache.store.retire_material()
        receive = cache.ledger.reserve(MAX_NATIVE + 65536, encoded=MAX_NATIVE)
        raw, retained = None, False
        try:
            raw = await io(endpoint.baseline(), deadline)
            alive()
            check(type(raw) is bytes and len(raw) <= MAX_NATIVE, "sync_native_bytes")
            size = len(raw)
            cache.ledger.retain(raw, reservation=receive)
            retained = True
            candidate = cache.admit_baseline(raw)
        finally:
            receive.close()
            if retained:
                cache.ledger.release(raw)
            raw = None
        baselines += 1
        byte_count += size
        alive()
        return candidate

    try:
        with cache._lock, cache._material_entry():
            cache._check()
            root = cache.store.candidate if cache.store.candidate is not None else cache.store.current
            candidate = None if root is None else cache._mint(root)
        # Do not retain a root graph in a suspended coroutine frame.
        root = None
        if candidate is None:
            candidate = await baseline()
        while True:
            alive()
            challenge = cache._proof_request(candidate, deadline_ms=deadline)
            proof_deadline = min(deadline, cache._proof[2] + 2000)
            proofs += 1
            try:
                receive = cache.ledger.reserve(MAX_PROOF + 4096, encoded=MAX_PROOF)
                raw, retained = None, False
                try:
                    raw = await io(endpoint.proof(challenge), proof_deadline)
                    alive()
                    check(_now() < proof_deadline, "sync_proof_deadline")
                    check(type(raw) is bytes and len(raw) <= MAX_PROOF, "sync_proof_capacity")
                    cache.ledger.retain(raw, reservation=receive)
                    retained = True
                    proof_bytes += len(raw)
                    view = cache.confirm(candidate, raw, clock)
                finally:
                    receive.close()
                    if retained:
                        cache.ledger.release(raw)
                    raw = None
                alive()
                return AcquisitionResult(view, baselines, transactions, proofs, moved, byte_count, proof_bytes)
            except MovedHead as change:
                # No body work is performed in the two-second operation. The
                # known move revokes authority before any separate catch-up.
                cache.revoke("head_moved")
                with cache._lock:
                    cache._observe_head(change.tag)
                target = change.tag
                moved += 1
            check(moved <= 1, "sync_head_moved_again")
            alive()
            base = candidate.tag
            receive = cache.ledger.reserve(8 * 1024 * 1024 + 65536, encoded=8 * 1024 * 1024)
            chain, retained = None, False
            try:
                chain = await io(endpoint.changes(base.native, target=target, max_transactions=4,
                                                  max_bytes=8 * 1024 * 1024), deadline)
                alive()
                needs_baseline = type(chain) is ResyncRequired
                if not needs_baseline:
                    check(type(chain) is tuple and 0 < len(chain) <= 4 and
                          all(type(raw) is bytes for raw in chain) and sum(map(len, chain)) <= 8 * 1024 * 1024,
                          "sync_catchup_capacity")
                    cache.ledger.retain(chain, reservation=receive)
                    retained = True
                    candidate = cache.stage_batch(base, chain)
                    check(candidate.tag.native == target, "sync_catchup_target")
                    transactions += len(chain)
                    byte_count += sum(map(len, chain))
            finally:
                receive.close()
                if retained:
                    cache.ledger.release(chain)
                chain = None
            if needs_baseline:
                candidate = await baseline()
            alive()
    except BaseException:
        cache.disconnect()
        raise
    finally:
        with cache._lock:
            if cache._acquisition == token:
                cache._acquisition = None
