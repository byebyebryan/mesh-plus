# Private controller and stamped carrier source checkpoint

This implements the separately reviewed control plane in
[controller R2](delta-sync-controller-proposal-r2.md), with the
[completion R3 clarification](delta-sync-controller-completion-r3.md).
Observer's same-byte owning agreement is `d6364d1c3441b07436ca1e32789994aa2448be85`;
the coordinator's R2+R3 record is `92b97d825cc2c1f8c3bbd1ad17b046e328e3eec9`.
Those are contract reviews. This checkpoint supplies source implementation and
bounded tests; it does not accept a configured route or consumer adoption.

## Public entry points

```python
from mesh_plus.sync import (
    StampedControlFrame, SyncControlCarrier,
    control_carrier_from_ipc, control_carrier_from_stdio, serve_sync_relay,
)

carrier = control_carrier_from_ipc(connected_unix_socket, ledger=relay.ledger)
# Or: carrier = control_carrier_from_stdio(read_fd, write_fd, ledger=relay.ledger)
await serve_sync_relay(relay, carrier, setup_deadline_ms=absolute_boottime_ms)
```

Factories take an unread connected Unix stream socket, or unread fixed stdio
file descriptors. They own those descriptors after argument validation; failures
after that point close only those descriptors. The trusted caller authenticates
the endpoint, selects the existing source/descriptor/structural codec, supplies
the shared ledger and original setup deadline, and ensures no earlier application
reader or buffered bytes. Arbitrary `StreamReader`, `LineChannel`, caller DTOs and
caller timestamps cannot mint an ingress frame. No listener, SSH launcher,
authentication policy, selected Reader adapter or route is installed here.

`serve_sync_relay` requires the exact minted carrier and relay on the same ledger.
After validation it owns that carrier and its controller/channel cleanup, while
the relay factory and source retain their existing ownership. Closing one
connection preserves siblings and the shared ledger. Factory close joins its
controllers, including pending hellos, before releasing its own source/credit.

The carrier also exposes `receive_control(maximum_bytes=..., deadline_ms=...)`
and `output_channel`. A minted frame has revocable `start`, `stop`,
`first_byte_ms` and `header`, plus idempotent `close()`. Header access provides
`materialization_bytes` and `materialize() -> dict`; the caller independently
prepays and retains the advertised detached-copy credit. Its lifetime can extend
beyond the frame. Direct reads through `output_channel.receive()` reject, so
there is exactly one input reader.

`RelayAcquisition.head_after_nonce(challenge, *, not_after_ms=None)` adds the
accepted restrictive deadline argument. Omission retains the previous bound;
the argument can only reduce it. Public operation return values stay unchanged.

## Ingress and ownership

A 65,536-byte ring receives directly with nonblocking `os.readv`, in chunks at
most 4,096 bytes. BOOTTIME is sampled immediately before each actual read with
no intervening suspension or callback. Absolute offsets and 256 prepaid range
slots retain the conservative floor. Coalescing takes the minimum floor before
slot pressure; dequeue, fragmentation, paused reading and output waits cannot
make a floor newer. Clock-scope change, regression or offset exhaustion retires
the connection. Kernel buffering is not presented as an application timestamp.

There are at most two live minted frames. The strict two-pass parser scans the
ring without copying a raw frame. It rejects duplicate keys (including escaped
equivalents), invalid UTF-8/surrogates, raw CR/internal LF, BOM, noninteger numbers,
negative zero, over-depth/over-node trees and oversized strings/containers before
publishing a header. Limits are depth 8, 512 nodes, 32 members per container and
4,096 decoded characters per string. Hello is at most 65,536 bytes including LF;
open, commands and results are at most 8,192 bytes including LF.

| State or allocation | Owner and retirement |
| --- | --- |
| Unread ring, unused capacity, range slots and transport metadata | Carrier prepays 196,608 heap / 65,536 encoded bytes before construction; retained until read/write jobs unwind. |
| Decoder scratch, bounded DTO and frame/header | Carrier prepays `40 * frameBytes + 131072` heap before parsing; frame close clears its DTO and returns this credit. |
| Detached command/header copy | Caller prepays advertised `24 * frameBytes + 65536` heap before copy; transfer keeps one owner until the command is retired. |
| Controller, tasks and bounded ownership metadata | Controller prepays 131,072 heap / 8,192 encoded bytes before input; counts pending hello against the existing 16-client total. |
| Active operation and one pending control/terminal permit | Each record independently prepays 32,768 heap / 8,192 encoded bytes; no history or work queue. |
| Hello serialization and reply output | Independent 524,288 heap / 131,072 encoded scratch before offer; result output has independent 32,768 heap / 8,192 encoded scratch. Borrowed output survives only while its existing credit remains held. |

These are conservative implementation reservations, not aggregate physical-heap,
RSS or plateau qualification. Existing relay/source/scanner/copy/pin allocations
remain independently charged to the same ledger, under the original 32 MiB
encoded / 64 MiB heap limits. Copying never shares another copy's credit.

## Dispatch and terminal receipts

The implemented closed grammar is exactly R2 plus R3: hello/open, contiguous
command IDs, exact request digest and capsule/watch IDs, begin/baseline/changes/
head/watch/stop-watch/end/cancel, and separately typed command results. Unknown,
ambiguous, replayed or stale commands retire the affected connection.

There is one active operation and one pending control slot. Valid conflicting
work gets `failed/busy` without source acquisition; blocked replies pause further
reads within prepaid ring capacity. An established watch survives capsule end
and expiry. A later capsule can perform a bounded head beside that watch or stop
that exact watch. No capsule, receipt or heartbeat refreshes the Reader budget.

Every head carries the original minimum of capsule deadline, stamped first byte
plus requested remaining time, and stamped first byte plus 2 seconds through the
source, scanner, copy, both output locks, every pre-write check and drain. Setup
uses its original bound through output-lock waits. Results sample `through`
under the same output serialization; they never advance delivery sequence or
provide current authority. Physical read/write byte counters include partial
traffic even if no complete record follows.

End/cancel cleanup receipts have separate bounded authorization after work
retirement, with original immutable IDs/deadlines. Cancel latches the original
outcome before revocation, awaits owned cleanup, and may send the original
`cancelled` followed by cancel `ok`; an expired receipt is suppressed. No receipt
revives work. Partial output retires the connection before scratch refund.

Changes requires the supported `changes_with_completion` method, with no legacy
fallback. It preserves every transaction and exact native completion, and sends
`ok` only after all drain. Original recovery control drains before `failed/source`.
`maxTransactions` is capacity 1..4, result count 0..capacity, zero only exact
base==target with correlated original complete. `maxBytes` bounds transaction
frames including LF only, at most 8,388,608 bytes. Agent native completion remains
at most 16,384 bytes; the complete nested Mesh control remains at most 65,536
including envelope/LF. Both stay charged under the same shared caps.

Errors remain bounded: malformed/provenance/deadline/capacity/retirement failures
clear their traceback captures before returning credit. Close/cancel waits for
owned physical I/O, preserves independent native/source pins until their unwind,
and does not collect old material inside compact confirmation.

## Evidence boundary

The [dated evidence](evidence/2026-10-17-controller/README.md) binds the exact
source checkpoint, dual-Python focused checks, canonical gate and 24 small
actual synthetic Observer Runtime/source/controller/Reader scenarios over Unix
IPC and real pipe stdio. It also retains draft harness errors separately.

Populated native providers, fixed SSH, authentication/ordinary selected Reader
integration, compact watch/cancellation stress with actual sources, aggregate
32/64 accounting, RSS, whole-pipeline CPU, dense 2,000-row delivery and recovery,
immutable installed pairs and consumer adoption remain unqualified. Existing
producer CPU failures are preserved. The accepted a7/a23 selection, schemas,
LOCK, material publisher and Reader independent full admission are unchanged.
