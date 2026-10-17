# G1 owned input contract for joint review

Status: **experimental Mesh source; Observer agreement and API freeze pending**.
This is the intake-ownership response to RLCD `e-5fe416a8`, independent of A1
relay role acceptance. The G0 appendix/schema lock stays unchanged. The separate
[A1 packet](delta-sync-relay-api-proposal.md) remains its original review bytes;
this document refines the common byte-ownership seam without approving relay
transport or any admission bypass.

## Public Mesh signatures

```text
OwnedSyncCache.input_owner() -> InputOwner
InputOwner.buffer_heap(nbytes: int) -> int
InputOwner.reserve(heap_bytes: int, *, encoded_bytes: int = 0)
    -> InputReservation
InputOwner.close() -> None

InputReservation.heap_bytes: int
InputReservation.encoded_bytes: int
InputReservation.resize(heap_bytes: int, *, encoded_bytes: int = 0) -> None
InputReservation.seal(raw: bytes) -> OwnedInputRef
InputReservation.close() -> None
InputReservation.__enter__() / __exit__(...)

OwnedInputRef.nbytes: int
OwnedInputRef.close() -> None

OwnedSyncCache.admit_baseline(raw: bytes | OwnedInputRef) -> CandidateRef
OwnedSyncCache.stage(raw: bytes | OwnedInputRef) -> CandidateRef
OwnedSyncCache.stage_batch(base: SourceTag,
    frames: tuple[bytes | OwnedInputRef, ...]) -> CandidateRef
OwnedSyncCache.confirm(candidate: CandidateRef, proof: bytes | OwnedInputRef,
    clock: ReaderClock) -> ViewRef
```

The three input types are exported by `mesh_plus.sync`; their constructors are
not public factories. The cache mints one active InputOwner per intake epoch.
It is tied to that exact cache's profile/callback identities, immutable source,
descriptor and request binding. Descriptor/callback mutation invokes the normal
cache rejection/close path. Disconnect retires the owner; later `input_owner()`
mints a distinct epoch. Neither equal descriptors nor a shared ledger permit
cross-cache/alias consumption. Native owner/context and currentness are still
independently checked during material/proof admission; sealing makes no native
identity assertion and cannot replace those checks.

InputOwner.close is a cache/owning-reader lifecycle operation. A source session
does not close a shared InputOwner: it closes its own reservations and refs.
The input API provides no byte export, parsed-state memo, semantic view or
admission reuse token. A relay's future unadmitted transport owner must be a
separate factory/capability accepted under A1; this cache factory is not such a
relay factory. Reservation/sealing is byte ownership only in either role.

## Proposed additive Observer source ABI

The adapter is explicitly opt-in. Existing plain-byte acquisition retains its
strict parser, return types and ownership contract. The following adapter is
pending Observer owning agreement/implementation; Mesh has not edited it:

```text
CachedSyncSource.open_session(inputs: InputOwner) -> OwnedSourceSession
OwnedSourceSession.baseline() -> OwnedBaselineTicket | OwnedSyncControl
OwnedSourceSession.changes(base: NativeTag, *, target: NativeTag,
    max_transactions: int = 4, max_bytes: int = 8388608)
    -> tuple[OwnedInputRef, ...] | OwnedResyncRequired
OwnedSourceSession.watch(cursor: Cursor) -> OwnedSourceWatch
OwnedSourceSession.head_after_nonce(challenge: FrozenValue) -> OwnedInputRef
OwnedSourceSession.aclose() -> awaitable[None]
OwnedSourceWatch.__aiter__() / __aenter__() / __aexit__(...) / aclose()

OwnedBaselineTicket.data: OwnedInputRef
OwnedBaselineTicket.tag: NativeTag
OwnedBaselineTicket.cursor: Cursor
OwnedBaselineTicket.close() -> None
OwnedSyncControl.data: OwnedInputRef
OwnedSyncControl.status, reason, tag, cursor
OwnedSyncControl.close() -> None
```

An owned watch yields an input ref or owned control. Baseline/control projection
fields remain unadmitted claims derived from those exact bytes. They and their
DTO/container storage retain prepaid leases until ticket close. Source code can
use the structural InputOwner protocol without importing Mesh. A header parser
whose budget calls `reserve(amount, encoded=0)` can use this public adapter:

```python
class ParserBudget:
    def __init__(self, inputs):
        self.inputs = inputs

    def reserve(self, amount, *, encoded=0):
        return self.inputs.reserve(amount, encoded_bytes=encoded)
```

This adapter grants the same aggregate credit, not a second budget. The source
reserves bounded scanner/header scratch before parsing; the returned header
ticket keeps its decoded lease. It validates the complete JSON grammar and
closed decoded structural header (including duplicate header keys), without a
full opaque body/operation DTO. All deferred duplicate opaque-key, domain,
schema and commitment checks remain mandatory at Mesh admission. Limits are
enforced and errors reject; there is no truncation or parser fallback.

## Physical ownership and transfer

Reserve before recv, growing pending/rest storage, slicing/copying, immutable
conversion, header parsing, or creating a retained batch/ticket. Budget all live
physical copies, mutable capacity/slack, DTOs, containers, parser scratch and
queued/paused references. The native/multiplex framing implementation must keep
these leases across suspension. A prior transaction retained in a four-item
batch remains charged while subsequent transactions are received. Head/control
results follow the same rule. Input accounting is part of the shared cache/
Reader/service totals and peaks; transport buffers are not an exclusion.

`buffer_heap(n)` returns the credit seal transfers for the exact immutable bytes
plus its private handle/bookkeeping. Before conversion, reserve that credit AND
all still-live mutable/chunk/DTO storage. Encoded credit counts each simultaneously
live encoded copy. A physical copy never inherits another still-live buffer's
credit. First-version handles do not share physical storage/credit across
aliases: each seal has its own charge; closing one cannot refund another.

Seal moves only `buffer_heap(len(raw))` heap credit and `len(raw)` encoded credit
from the existing reservation to the new ref. Aggregate counters do not drop or
temporarily double-count that transferred credit. The reservation remains open
with all other credit, including its separate control overhead. The producer
transfers the immutable raw exclusively, clears its raw alias before suspension,
and keeps framing/header/container credit until those allocations retire. A
bytes subclass, bare-byte return, or remembered validation result transfers no
ownership. The ref grants no semantic or current authority.

Cache consumption pins the same buffer without copying or reserving a second
raw buffer. Complete existing admission runs; the cache retains its normal
prepaid decoder/stage allocations in addition to the intake pin. Streaming
adapters borrowing the raw input retire before its pin refunds. The input ref
cannot be consumed twice, exported or rebound. A valid bounded batch transfers
all supplied handles, including members not reached after an earlier failure.
An invalid container, more than four members, or unsupported member type rejects
before ownership transfer; the caller still closes its handles.

Disconnect immediately revokes all handles/publication. An in-progress consumer
retains its pin/credit until unwinding, and cannot publish a surviving view.
An unsealed receive reservation remains charged after owner retirement until its
source cancels/awaits I/O, drops physical buffers and explicitly closes it. A
timeout, parser error, failed setup or repeated cancellation has the same owned
cleanup obligation. Saved failure tracebacks cannot retain private input/stage
graphs. Source-session close cancels/awaits its own work, drops rest/batch/header
storage and closes its refs/leases; it leaves sibling sessions and the parent
service usable. Close is idempotent. No source/provider/service lifecycle action
is a cleanup operation.

## Ownership states

| State / operation | Ownership and credit after operation | Publication |
| --- | --- | --- |
| reserve succeeds | caller owns prepaid lease before receive/allocation | none |
| reserve/resize fails | original credit unchanged; forbidden allocation does not start | none |
| resize succeeds | grow prepays first; shrink follows actual retirement | none |
| seal succeeds | ref owns only sealed raw credit; producer retains remaining lease | none |
| seal fails | original lease/credit stays live for producer cleanup | none |
| source/watch/batch pauses | raw refs and every remaining physical buffer/DTO lease stay charged | none |
| consume begins | ref becomes single-consume; cache holds a synchronous raw pin | none |
| admission succeeds | raw aliases retire, input pin refunds; new material is still unconfirmed | none |
| fresh proof succeeds | pin refunds; existing independent proof path may publish | confirmed cache only |
| consume fails, including wrong owner | supplied handle retires its own charge; target/sibling credit is untouched | none from failed consume |
| disconnect/owner close | sealed refs revoked; consuming pins/unsealed receives keep credit through cleanup | revoked |
| source cleanup completes | buffers/DTOs retire, then their leases close; no detached cleanup | none |

## Limits and errors

All public counts are exact integers; bool is rejected. No deadline, client,
frame or aggregate-cap change accompanies this API.

| Limit or failure | Error / ownership result |
| --- | --- |
| 64 MiB decoded / 32 MiB encoded shared aggregate (or configured lower) | `sync_decoded_capacity` / `sync_encoded_capacity`, before allocation; existing credit unchanged |
| <=64 combined open leases and sealed/pinned refs per InputOwner | `sync_input_slots`, before new control allocation |
| raw must be exact immutable bytes, <=8,404,992 bytes | `sync_input_bytes`; lease remains owned |
| buffer_heap argument outside integer frame bound | `sync_input_capacity` |
| head/proof <=65,536 total; native head <=49,152 and envelope <=16,384 | normal independent proof rejection; supplied ref consumed |
| <=4 batch frames AND <=8 MiB exact encoded sum | `sync_catchup_capacity`; valid bounded input shape consumes all refs on size/admission failure |
| invalid reservation/resize integers | `sync_reservation`; original lease remains owned |
| insufficient prepaid credit at seal | `sync_input_credit`; no ref minted, original lease remains owned |
| foreign cache/alias | `sync_input_owner`; only the supplied valid handle retires |
| retired/consumed handle or retired owner | `sync_input_retired`; close remains safe |
| direct input-type construction | `sync_input_mint` |
| malformed/duplicate header, schema/domain/old-token/root failure | existing strict parser/admission error; owned cleanup remains mandatory |

Input controls are prepaid in addition to caller payload credit: owner base
2 KiB, each receive/parser reservation 1 KiB, and each sealed buffer's handle/
bookkeeping 1.5 KiB plus actual bytes object size. These conservative allowances
cover their bounded registries/controls; they are included in aggregate peaks.
`heap_bytes` reports caller credit excluding the reservation's private overhead;
`encoded_bytes` reports its remaining encoded credit. Resizing and sealing cannot
spend another ref's credit. These allowances are not a replacement for actual
source resource/RSS/plateau qualification.

## Qualification boundary

The Mesh tests exercise conservation through seal, baseline/proof consumption,
malformed/duplicate input, four transactions, failed batch, alias isolation,
disconnect with active receive credit, before-allocation rejection, GC-disabled
retirement and repeated cancellation. They are generic source tests, not native
Observer intake, actual full/active semantic pairing, installed IPC/SSH or
end-to-end CPU/resource acceptance. The existing source acquisition controller
has not yet been adapted to owned source sessions.

Before freeze, Observer must confirm these exact signatures and states, adopt
the public opt-in adapter and qualify paused baseline/transaction/watch, actual
full+active aliases, four-item batches, head/control, boundary/malformed/duplicate
headers, failed consume, disconnect and repeated cancellation. Capture intake,
pending/rest/parser/batch/ticket/output storage in aggregate peaks and count
source intake CPU in the same end-to-end totals. Run the canonical Mesh and
independent Observer gates on the same source/artifact bytes. Current dense
storage and expanded-wire failures remain blocking; these tests do not satisfy
those gates. No package/version allocation, schema freeze, installation or
normal-role/consumer/production action is implied.
