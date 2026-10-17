# A1 exact relay interface packet, revision 2

Status: **Mesh candidate for same-byte Observer and RLCD review**. This is a
planning API, not an implemented or frozen transport. It refines the unchanged
[first packet](delta-sync-relay-api-proposal.md), SHA256
`05e5a9bef61d0235d6d82c326e630209dac610a122f581117bdb65beaa36183d`.
The concrete role amendment is RLCD A1 revision 2, commit
`665f6caaed99740a755de9467c7ae53322f7e720`, SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`.
It is distinct from the original G0 material publisher. Frozen G0 appendix
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`
and all old lock/schema bytes remain unchanged.

The cache-backed input contract SHA256
`7f7751ecd9df93277a3e7110ca72ebfda343d38fa629cd0212ec40b3a8f1d124`
has Observer common-contract agreement at `7a1d666`. That agreement does not
cover the relay factory below. This packet gives the relay a separate transport
owner and consumer rather than extending the cache-minted input capability.
No dependent relay implementation begins before joint exact-interface agreement
and the coordinator's A1 acceptance record. Compact codec agreement and resource,
correctness, performance and installed transport qualification remain separate.

## Exact public factory and channel signatures

All names below are proposed Python APIs. Constructors of minted ownership,
channel and ticket types are private. All async signatures return awaitables;
`open_channel` is async because it performs setup and opens a source session.
`FrozenValue` is the strict immutable integer-only JSON subset from G0.

```python
create_sync_relay(
    source: CachedSyncSource,
    descriptor: SyncDescriptor,
    source_binding: FrozenValue,
    *,
    native_codec: NativeTransportCodec,
    budgets: SyncBudgets,
    ledger: AllocationLedger,
    owns_source: bool = True,
) -> SyncRelay

SyncRelay.open_channel(
    channel: LineChannel,
    request_binding: FrozenValue,
    *,
    acquisition_deadline_ms: int,
) -> awaitable[RelayChannel]
SyncRelay.aclose() -> awaitable[None]

RelayChannel.input_owner() -> RelayInputOwner
RelayChannel.baseline() -> awaitable[None]
RelayChannel.changes(
    base: NativeTag, *, target: NativeTag,
    max_transactions: int = 4, max_bytes: int = 8388608,
) -> awaitable[None]
RelayChannel.head_after_nonce(challenge: FrozenValue) -> awaitable[None]
RelayChannel.watch(cursor: Cursor) -> awaitable[RelayWatch]
RelayChannel.aclose() -> awaitable[None]
RelayWatch.wait_closed() -> awaitable[None]
RelayWatch.aclose() -> awaitable[None]
```

The factory requires the aggregate ledger explicitly. `budgets` may lower its
limits; it cannot create another allowance or raise 64/32 MiB. Full/active aliases
and all channels in one owning service use that same aggregate ledger. The relay
captures exact source, descriptor, codec specification and scanner callback
identities. Mutation/replacement closes affected channels; it never rebinds live
handles. `owns_source` is an exact bool. No `SyncProfile`, profile callbacks,
`OwnedSyncCache`, material index or semantic facade is accepted or constructed.

The source is already configured for exact native hostScope, expected UID,
socket/service, full/active selector and descriptor. Local IPC verifies its
expected peer credentials. Fixed SSH uses the authenticated configured host and
fixed new sync route. Request data cannot choose imports, executables, sockets,
native selectors, profiles, source factories or authentication policy.

`open_channel` verifies the complete exact request binding, explicit role and
encoding, and opens `source.open_session(relay_channel.input_owner())` internally.
The supplied LineChannel is one already authenticated, bounded connection;
no connection is opened by a wire-supplied command. After valid argument/type
checks, the call takes ownership of that channel, including failed setup cleanup.
An invalid argument rejects before ownership transfer. A successful RelayChannel
owns the connection and its one source session, never the native owner service.
The synchronous `input_owner()` accessor returns that channel's stable active
owner; it does not open another session or allocate another budget.

The operation methods acquire, structurally inspect and **send** their results.
They return no raw payload, semantic view, admitted candidate, material validation
memo or authority. In particular `head_after_nonce` sends the proof below; it
does not return an admitted proof. There is no public arbitrary raw-forward,
byte-export or admitted-material reuse method. This is the public consuming
boundary for a relay source adapter: the source transfers returned refs to the
operation; the operation owns them through structural checking and output drain.

Only one baseline/changes/head operation may be active on a channel. There is
at most one watch on this relay delivery channel; baseline/changes require that
watch to close first, while nonce head may run beside it. This lower stream
bound does not change the native source's shared maximum of eight subscriptions
and eight pending requests per native channel. A conflicting operation rejects
before acquiring another ticket. Source multiplexing remains bounded. Native
client count stays sixteen combined. Each watch owns its output task, starts strictly after its cursor,
and stops before `wait_closed`/`aclose` completes. Every queued output item and
blocked write stays charged. Cancellation cannot detach a writer.

`acquisition_deadline_ms` is an absolute exact nonnegative integer in the
relay's CLOCK_BOOTTIME domain, supplied by its trusted local controller, at most
15 seconds after local acquisition start. The Reader separately owns the
original end-to-end 15-second deadline; this relay bound never restarts or
extends it. Local IPC or SSH startup, cold admission, baseline recovery and
fresh proof all count at the Reader. Per-proof relay and Reader bounds are two
seconds, including queueing, native work, scanning, wrapping, write and checks.

## Relay byte ownership and exact source transfer

```python
RelayInputOwner.buffer_heap(nbytes: int) -> int
RelayInputOwner.reserve(heap_bytes: int, *, encoded_bytes: int = 0)
    -> RelayInputReservation
RelayInputOwner.close() -> None

RelayInputReservation.heap_bytes: int
RelayInputReservation.encoded_bytes: int
RelayInputReservation.resize(heap_bytes: int, *, encoded_bytes: int = 0) -> None
RelayInputReservation.seal(raw: bytes) -> RelayInputRef
RelayInputReservation.close() -> None
RelayInputReservation.__enter__() / __exit__(...)
RelayInputRef.nbytes: int
RelayInputRef.close() -> None
```

These are **separate types** from cache `InputOwner`, `InputReservation` and
`OwnedInputRef`. Their public reserve/resize/seal/close protocol and physical
transfer rules are identical to the reviewed cache input contract. Source code
uses a structural `AcquisitionInputs[RefT]` protocol without Mesh imports; the
return ref type is supplied by that owner's `seal`. Thus the same source
`open_session(inputs)` can serve either independently selected owner type,
without interpreting the ref or selecting an admission role.

```text
CachedSyncSource.open_session(inputs: AcquisitionInputs[RefT]) -> SourceSession[RefT]
SourceSession.baseline() -> awaitable[BaselineTicket[RefT] | SyncControl[RefT]]
SourceSession.changes(base, *, target, max_transactions=4, max_bytes=8388608)
    -> awaitable[tuple[RefT, ...] | SyncControl[RefT]]
SourceSession.head_after_nonce(challenge) -> awaitable[RefT]
SourceSession.watch(cursor) -> owned async-context-manager/iterator[RefT | SyncControl[RefT]]
SourceSession.aclose() -> awaitable[None]
BaselineTicket.data: RefT
BaselineTicket.tag: NativeTag
BaselineTicket.cursor: Cursor
BaselineTicket.close() -> None
SyncControl.data: RefT
SyncControl.status, reason, tag, cursor
SyncControl.close() -> None
```

This is a type-parameter clarification of the agreed opt-in source methods,
not a change to ordinary byte-returning methods. The existing proposed
OwnedResyncRequired is the `baseline_required` variant of SyncControl and owns
its exact control ref/metadata lease. Optional structural tag/cursor fields
follow the native control schema, not invented success values. No bare byte
return, byte subclass, repeated validation success or source DTO transfers
ownership to these operation methods. Unsupported owned sessions fail setup.

The factory prepays relay controls. `open_channel` prepays the input owner before
constructing it; owner base is 2 KiB, each lease is 1 KiB and each sealed raw
buffer is actual bytes-object size plus 1.5 KiB bookkeeping, as in the cache
contract. Each owner has at most 64 combined leases/sealed/pinned refs. All
counts are exact integers; bool is rejected. Ref state is single-consume and
revocable, with no public byte accessor. Close is bounded and idempotent.

Every relay ref binds the exact aggregate ledger, relay and channel/input epochs,
configured source, complete descriptor/encoding/scanner identities and immutable
request binding, including role/encoding. It has **no profile-callback identity
or material proof** because the relay has none. Cache refs retain their separate
exact profile/callback/cache binding. Neither kind can be consumed by the other
kind's consumer or by an equal-configured sibling/alias. Failure retires only
the supplied valid handle's own credit. A relay ref presented to a cache rejects
as wrong ownership before material admission; it cannot become an admission
reuse capability. The source cannot mint refs directly or alter their binding.

Reserve before receive, mutable growth, slicing/copying, conversion, parser/DTO
construction and retention of pending/rest/batch/watch/control/header objects.
`seal` transfers only raw-plus-handle heap and raw encoded credit, atomically,
leaving other live allocations charged to the original lease. It neither scans
nor validates bytes. The producer clears its raw alias before suspension and
keeps other leases until their allocations retire. The consumer pins that same
buffer, scans it, and writes bounded envelope/native/delimiter segments without
a full reserialization or concatenation. A copy, including transport-library
write copies or overlapping conversion buffers, needs additional prepaid credit
before allocation; a zero-copy pin retains the existing credit instead.

When a source method returns a valid ticket/control or bounded tuple of refs,
the relay operation takes all returned data refs and retains them until sending
or failure cleanup. It closes ticket/control DTO leases after their last use.
A malformed return type/oversized tuple rejects before transfer and the source
session remains responsible for those refs; the operation closes the session.
A well-typed tuple of at most four refs transfers every member before content
checks, including unvisited members on an early failure. Size/chain failures
then retire the whole transferred batch. An invalid/foreign member cannot
refund a sibling's storage. Four transactions AND their exact <=8 MiB sum are
checked; no incomplete prefix is emitted as a successful complete chain.

Baseline/control ticket tag/cursor/status claims are compared with the scanned
bytes before forwarding and never trusted as material. Write completion means
all userspace and transport pins/copies are retired, not merely enqueue success.
Input charge persists across a paused watch, queue suspension or blocked write.
Source header scratch, decoded metadata, changes tuple and pending/rest remain
separately charged; input and output pins do not double-credit the same storage.
Two aliases have distinct handles and charges; cross-alias shared physical
storage is not a public v1 capability. Both receivers admit independently.

## Bounded native structural codec

```python
NativeTransportCodec.encoding: FrozenValue  # EncodingBinding below
NativeTransportCodec.header(raw: bytes, budget: BudgetProtocol)
    -> NativeTransportTicket
NativeTransportCodec.head(raw: bytes, budget: BudgetProtocol)
    -> NativeTransportTicket
NativeTransportTicket.header: HeaderRef
NativeTransportTicket.close() -> None
BudgetProtocol.reserve(amount: int, *, encoded: int = 0) -> closeable reservation
```

The supplied codec is a supported pure structural facade. Its methods are
synchronous; generic code pins the input for that bounded callback and retires
the callback's raw aliases/error frames before refund. The budget is the same
aggregate ledger adapter, not another allowance. HeaderRef is readonly,
ticket-bound and revocable. Raw aliases, temporary scratch/iterators and the
callback budget cannot survive callback return. The returned ticket/header may
outlive that return only under its own prepaid lease, until explicit close;
it cannot retain the opaque raw payload. After ticket close its views reject.
Saved exceptions must retire callback frames under the same held-exception/
GC-disabled tests as other sync callbacks, without refunding live allocations.

`header` scans complete strict UTF-8/integer-only JSON grammar using prepaid
bounded scratch, checks the closed native envelope and returns only structural
descriptor/kind/tag/cursor/base/result/binding/sequence/control data. It does not
allocate a body plan, normalize aliases/masks or materialize opaque table DTOs.
`head` is a separate <=49,152-byte path with only the bounded decoded head
fields: descriptor, nativeBindingDigest, tag, challenge, ownerClock,
originalReceipts, cohortHeads and attenuation. It never calls a material plan,
schema/domain callback, full export or semantic query. The relay uses no
`entries`, `operations`, `check_baseline`, `check_transaction`, `check_head` or
facade hooks. Structural scanning is not material admission or a schema memo.

The scanner checks closed header duplicate keys, descriptor, native host/UID/
incarnation/context shape and configured binding, exact tag/cursor shape and
sequence, field length/integer limits and malformed/truncated/trailing input.
Opaque value duplicate-key, native/schema/domain/cross-record, alias/mask,
expected-old, semantic field-token, table/seal/root checks remain mandatory at
the Reader. In particular a structurally well-formed but domain-invalid payload
may be relayed and must fail at independent Reader admission. A source header
scan cannot be promoted to material validation. Raw Reader admission stays strict.

EncodingBinding is the closed object:

```json
{"id":"<exact configured encoding ID>","schema":"<64 lowercase hex>","nativeDescriptor":"<64 lowercase hex>"}
```

`encodingDigest = SHA256(C(EncodingBinding))`, lowercase hex. The three values
must equal the matching explicit NativeCodec specification's encoding ID,
encoding schema digest and native descriptor digest. This is an exact binding
formula, not allocation of a compact ID or schema. Full/active native descriptors
remain distinct. Local scanner identities are separately captured and checked;
matching wire digests do not permit local callback replacement. Final compact
encoding, independent native join vectors and codec API agreement are still open.

## Explicit setup, delivery and operation limits

RequestBinding is a closed object with exactly `readerEpoch`, `requestId`,
`catalogRevision`, ordered `hosts`, selected `route`, `channelEpoch`, `bridgeId`,
`role`, `encodingDigest`. Epoch/incarnation fields are 32 lowercase hex;
`requestId` is a nonempty <=128-character string; catalogRevision is a nonempty
<=256-character string. There are 1..16 distinct nonempty <=256-character host
names in the configured order. Route is the exact trusted nonempty <=256-character
route string. Canonical binding is <=4 KiB. These are candidate new-sync fields,
not retroactive restrictions on legacy Delivery or prototype test bindings.

The closed setup value is:

```text
{protocol:"mesh.state-sync/1", kind:"setup", descriptor,
 sourceBinding, requestBinding, role, encoding, features, limits}
role = "transport-relay" | "material-publisher"
features = ["baseline","transactions","watch","head-after-nonce"]
limits = {nativeFrameBytes, messageBytes, nativeHeadBytes, proofBytes,
          transactions, transactionBytes, heapBytes, encodedBytes,
          nativeClients, subscriptionsPerChannel, pendingPerChannel,
          heartbeatMs, blockedMs}
```

Relay setup requires role `transport-relay` at every occurrence, exact descriptor,
SourceBinding and encoding, that exact ordered required feature set and limits
no larger than configured values. The trusted Reader requires one exact role
and encoding before sending; echo must match. A material publisher still uses
the G0 admitting factory/semantics. Missing/unknown/mismatched role/encoding or
unsupported feature rejects, with no fallback to material or old/full routes.
Closed setup is <=65,536 bytes and fully accounted before parsing/output.

Hard limits are respectively 8,404,992; 8,470,528; 49,152; 65,536; 4; 8,388,608;
67,108,864; 33,554,432; 16; 8; 8; 5,000; 15,000. Native source journal remains
<=4 generations AND 8 MiB inside the service totals; decoded current plus
predecessor plus one stage and all pins/controls remain within the same cap.
Fleet total remains <=16 MiB. Handshake/frame limits do not create extra credit.

Each post-setup delivery is the closed outer value:

```text
{protocol:"mesh.state-sync/1", kind:"delivery", requestBinding,
 sequence, payload}
```

Sequence is exact integer 1..2^64-1, contiguous per channel and advances for every
material, proof and control delivery, including heartbeats. It is distinct from
native generation/cursor. Overflow closes the channel; it never wraps. Payload
is exactly one of:

```text
{kind:"material", descriptor, sourceBinding, sourceTag, native:<exact native JSON>}
{kind:"control", descriptor, sourceBinding, native:<exact native control JSON>}
{protocol:"mesh.state-sync/1", kind:"proof", descriptor, sourceBinding,
 sourceTag, requestBinding, challenge, bridgeId, bridgeClock,
 head:<exact native head JSON>, remaining}
```

The proof payload preserves the existing candidate cache-confirmation shape.
The generic transport checks outer binding/sequence before handing that payload
to ordinary independent cache confirmation. Material sourceTag is the **claimed**
native tag wrapped by the O(1) G0 SourceRoot formula; it is never an admitted tag.
SourceBinding is exactly `{host,source,profile,profileSchema,nativeDescriptor}`
from trusted configuration. Aliases may share one native socket/root while
having distinct SourceBinding/SourceRoot and independent Reader admission.

Native JSON is spliced verbatim, excluding only its verified terminal framing
delimiter, with one output delimiter added. No quote/base64/thaw/reserialization
of native material/head is permitted. Maxima include **all** nested wrappers:
material native <=8,404,992 plus outer bytes <=65,536, total <=8,470,528;
proof native <=49,152 plus every envelope byte <=16,384, total <=65,536.
Controls and operation requests are <=65,536 total. Native control reason/status
is preserved as a structural claim, not converted into positive currentness.

Baseline captures native tag/cursor atomically. Changes requests name exact
base and target; all headers form a contiguous chain and completion control
names the exact target/cursor. The operation does not send `complete` until
all accepted chain frames have drained. Native baseline-required, gap, overflow,
unknown cursor, conflicting duplicate, descriptor/context replacement or output
failure produces an explicit failure/control and retires affected stream state.
An exact duplicate may be forwarded unadmitted; only retained exact Reader
tokens can recognize it, without renewal. No semantic composition or repair.
No heartbeat, delivery or control creates currentness.

## Fresh proof and authority responsibilities

```text
challenge = {nonce, target:SHA256(C(requestedSourceTag)),
             request:SHA256(C(completeRequestBinding))}
bridgeClock = {bootId, timeNamespace, boottimeMs}
```

Nonce is the Reader's fresh 64 lowercase hex, target/request are lowercase
64-hex digests, and the entire strict challenge is <=4 KiB. The relay checks
its complete request digest, remembers the exact challenge only for this
bounded operation, and invokes the live source's `head_after_nonce` after
receiving it. Neither a cached source ticket nor pipe liveness is a proof.
Each native reply must echo the entire challenge exactly. The relay never
substitutes another requested target or proves a retained older generation.

For a within-binding moved head, the relay wraps and sends the **actual fresh**
native tag/root, even when its digest differs from challenge.target. For a
native binding/incarnation/context change it reports source-changed/failure;
it never wraps the old binding as the new one. Either outcome immediately
revokes affected Reader claims, including last-confirmed claims. Catch-up is
separate <=4 transactions AND <=8 MiB, followed by at most one fresh nonce retry
inside the original absolute 15-second acquisition. A failed chain may need
explicit baseline recovery; all recovery CPU/bytes/time count. A second move,
eviction, exhaustion or deadline gives bounded failure, never old-target/legacy
fallback authority. No body acquisition or stage retirement inside proof.

The native head includes the unchanged original receipt/cohort heads. The relay
preserves their exact bytes/keys and native attenuation pairs. It structurally
rejects duplicate keys, bool/negative/noninteger attenuation or clock values,
wrong challenge/tag/binding, native clock regression in the same host/UID/
owner/boot/time scope, and mismatched native clock identity. It samples bridge
CLOCK_BOOTTIME after native head receipt in the same boot/time namespace:
`bridgeClock.bootId = ownerClock.bootId`,
`bridgeClock.timeNamespace = ownerClock.clockDomain` with only the accepted
`time:[digits]` -> `time:digits` representation conversion. UID/host/owner context
remain checked against configured native binding, not put into bridgeClock.

For `d = bridge.boottimeMs - owner.boottimeMs >= 0`, forward each pair as
`remaining(key) = max(0, nativeAttenuation(key) - d)`, preserving exact coverage.
This is pure non-renewing attenuation; the relay does not interpret provider
FactSupport or derive eligibility/expiry. The Reader independently checks the
native/source/table/cohort roots, exact original receipts, material/schema/domain
constraints, expected-old tokens, identity/context/UID/clock, challenge/request,
bridge incarnation, monotonic clocks, whole RTT/margin and its pure restrictive
head callback. Relay structural success cannot skip any of these checks.

## Ownership, failure and close table

| Event | Storage/credit and effect |
| --- | --- |
| reserve/resize fails | No forbidden receive/copy/parse starts; old credit unchanged |
| seal succeeds | Ref owns only transferred raw/handle credit; remaining lease stays live; no admission |
| source result returned | Valid ticket/batch refs transfer to operation; header/container leases remain separate |
| scan/send begins | Ref becomes single-consume; actual raw pins and every output copy remain charged |
| drain succeeds | Drop scan/raw/write aliases before refund; close DTO/ticket leases after their own retirement |
| scanner/copy/write/consume fails | Consume transferred refs; retire unwound private error frames, pins and remaining batch; no success/authority |
| foreign/retired/duplicate consume | Reject; retire only supplied valid handle's own credit; no cross-alias over-release |
| source/watch/channel close starts | Immediately revoke its sealed refs/use/publication, then cancel and await its own I/O and writer |
| consuming pin/unsealed receive at close | Keep credit until real storage and I/O retire; then explicitly close its leases |
| channel cleanup completes | Close its source session/connection; parent source and sibling sessions usable |
| relay close | Close all channels; additionally close parent source iff owns_source=True; never close owner service |
| repeated close/cancellation | Idempotent revocation; shield/await same bounded cleanup; no detached cleanup or late reseal/output |

Only the relay/channel owner closes RelayInputOwner; a source session closes
its own refs/reservations, never that shared owner or sibling cache/relay.
After input-owner retirement, reserve/resize/seal/nbytes/consume reject, while
idempotent close remains valid. Unsealed receive leases and consuming I/O pins
are not falsely refunded. The existing accepted 15-second blocked-client policy
and channel shutdown ensure bounded cleanup; failure is reported if actual
transport cleanup cannot complete, rather than declaring released live storage.

Capacity errors preserve `sync_decoded_capacity`, `sync_encoded_capacity`,
`sync_input_slots`, `sync_input_bytes`, `sync_input_credit`,
`sync_input_retired`, `sync_input_owner` and `sync_catchup_capacity` meanings.
Candidate local relay rejection categories are `sync_relay_role`,
`sync_relay_setup`, `sync_relay_busy`, `sync_codec_identity`,
`sync_relay_header`, `sync_relay_chain` and `sync_relay_output`.
These names specify review behavior, not allocated old wire error enums.
Malformed/truncated/duplicate headers, failed consume, timeout and repeated
cancellation retain the same deterministic ownership cleanup obligation.

## Byte-bound review and remaining qualification

The companion stdlib oracle `scripts/reproduce-sync-relay-vectors.py` and
`docs/evidence/2026-10-16-delta-sync/relay-api-r2-vectors.json` specify encoding,
request/challenge, two-alias wrapper and lease arithmetic fixtures. They use
fixture descriptors and unverified native roots, not accepted Agent payloads.
They demonstrate formulas/byte preservation only, not semantic or transport
acceptance. Actual domain extraction/codec vectors must remain equal after
descriptor/body/token recomputation when encoding is frozen.

Observer is asked to confirm these exact source-session/ref protocol, scanner,
identity/context/head/clock and close bytes, and identify a concrete incompatible
signature if any. Mesh accepts the A1rev2 role boundary and independently retains
all Reader checks; this candidate packet still needs counterpart agreement and
RLCD's acceptance record. Neither conceptual agreement nor arithmetic permits
dependent relay transport implementation on its own.

After agreement, tests must cover paused baseline/transactions/watch, actual
full+active aliases, four-item batches, head/control, allocation boundaries,
malformed/duplicate headers, failed consume, disconnect and repeated cancellation;
GC-disabled saved errors; absent semantic/admission capabilities; corrupt and
self-consistent domain-invalid material; wrong roots/receipts/bindings/replay/
owner/clocks; moved heads, gaps, duplicates, overflow and old/material routes.
Count all source intake, staging, pins, transport/queued output and descendants
in shared memory peaks and CPU totals. Real IPC/fixed SSH 100/500/2000 cold,
recovery and full/active steady tests plus installed same-byte independent gates
remain required. Dense source +126.82% and six baseline-required retirements at
Observer `100637b` remain failures; timestamp target evidence and packed-layout
frame-size feasibility do not close them. No package allocation or rollout.
