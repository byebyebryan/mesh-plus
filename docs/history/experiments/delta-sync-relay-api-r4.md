# A1 consolidated relay interface, revision 4

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **one intended Mesh candidate for exact Observer/RLCD signoff**.
This standalone document replaces the earlier candidate API packet set for the
next review; it is not implemented transport, A1 closure or G1/G2 acceptance.
It incorporates r2 SHA256
`8616bfba7c05dcf8982e431309bcd0bdf354c91bc023fdf0fcf85dcbe4c7abdd`
and r3 SHA256
`eb5c217c544bbe10766c7c0f32d574294412c6f6230c7ad6b95a2a57483c0c9f`,
which remain immutable historical inputs. No reviewer needs to resolve
conflicting old signatures to apply this revision.

RLCD A1 revision 2 is commit
`665f6caaed99740a755de9467c7ae53322f7e720`, SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`.
The original packet SHA256 `05e5a9be...` review and the later r2+r3 review remain
separate evidence. Observer's exact r2+r3 owning review at `b6c40f9` finds their
role/source/clock/lifecycle direction compatible and asks for the public
HeaderRef completion included below. This revision also makes scoped revocation,
live-only tracking, independent metadata credit and physical-copy rules explicit.
Mesh agrees to those completions as candidate contract bytes; counterpart
same-byte agreement and the coordinator's separate A1 record remain required.

Frozen G0 appendix SHA256
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`
and the agreed common cache-input contract SHA256
`7f7751ecd9df93277a3e7110ca72ebfda343d38fa629cd0212ec40b3a8f1d124`
remain unchanged. Common-contract agreement does not itself cover the separate
relay owner/factory below. This candidate introduces no profile, material cache,
admission reuse, wire ID/schema allocation, budget/deadline relaxation or change
to the old material-publisher role. No dependent relay implementation begins
before exact joint agreement and the coordinator's A1 record. Existing private
storage work is independent. No artifact, service selection or rollout occurs.

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

SyncRelay.bridge_id: str                       # immutable, factory minted
SyncRelay.open_channel(
    channel: LineChannel, request_binding: FrozenValue, *,
    setup_deadline_ms: int,
) -> awaitable[RelayChannel]
SyncRelay.aclose() -> awaitable[None]

RelayChannel.input_owner() -> RelayInputOwner
RelayChannel.begin_acquisition(*, deadline_ms: int) -> RelayAcquisition
RelayChannel.watch(cursor: Cursor, *, startup_deadline_ms: int)
    -> awaitable[RelayWatch]
RelayChannel.aclose() -> awaitable[None]

RelayAcquisition.baseline() -> awaitable[None]
RelayAcquisition.changes(
    base: NativeTag, *, target: NativeTag,
    max_transactions: int = 4, max_bytes: int = 8388608,
) -> awaitable[None]
RelayAcquisition.head_after_nonce(challenge: FrozenValue) -> awaitable[None]
RelayAcquisition.aclose() -> awaitable[None]
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
Two configured aliases have separately minted exact-binding handles and their
own control metadata; this fact alone does not describe or charge a payload
copy. Charge each actual immutable allocation once in each applicable aggregate
ledger, retain that credit through all zero-copy pins, and charge every actual
independent copy before allocation. Equality of bytes is not physical sharing.
This first public input protocol does not mint cross-alias shared-payload
ownership: one raw allocation is exclusively transferred by one seal, and a
second alias cannot reseal that borrowed allocation or spend its credit. A
source needing both aliases creates and prepays an actual independent buffer
for the second seal. Internal same-owner read/write pins do not manufacture
another payload copy/credit. A future cross-alias shared-allocation capability
would require its own exact ownership review; it is not inferred from a shared
native socket/root. Both Readers admit independently.

## Scoped retirement and bounded live ownership

The transport input owner is channel-scoped. Each source session, watch and
acquisition operation has its own logical lifetime within that owner. Their
source-local guards/wrappers use the public reserve/resize/seal/ref-close
protocol; they do not need a new mandatory generic child-scope API. Before each
reserve, resize or seal, the adapter checks its parent/session and applicable
operation/watch lifetime as well as the input-owner lifetime. An owner still
being live cannot authorize use from a retired child. A retired receive lease
retains its physical-buffer credit for cleanup but rejects resize or seal,
including after awaited I/O returns late. Idempotent close remains allowed.
Credit-size queries may describe still-held cleanup storage; they confer no use.

Source-session close marks that session retired before its first await. It
revokes only that session's outstanding refs/tickets, cancels and awaits its
operations/watches and drops its pending/rest/parser/batch/header storage before
closing their leases. A watch or failed operation retires only its own scope.
An acquisition capsule cancels and awaits its own source calls and closes all
returned refs/tickets it has taken. It does not close an unrelated watch,
source session, shared InputOwner, shared ledger, parent source or sibling.
A source session never calls `InputOwner.close()` as a shortcut. Channel close
owns its source session and input owner; relay close owns its channels and owns
the parent source only when `owns_source=True`. No cleanup stops the native
service, provider or old/material route.

All ownership registries track bounded live allocations, never append consumed
history. The generic owner removes terminal sealed refs from its live registry;
a revoked consuming record remains only as a charged in-flight cleanup pin
until actual I/O/raw aliases retire. Source tracking is bounded at 64 data refs,
64 live tickets and 64 source-local leases, additionally constrained by the
owner's 64 combined lease/sealed/pinned controls and shared byte caps. These are
upper bounds, not separately granted allowances. Consumed/closed entries leave
the live registry promptly; transfers, resumes, allocation/capacity decisions
and close cannot retain an accumulating terminal-reference history. Public
`nbytes` rejects on an unavailable ref; that rejection alone is not evidence
that a consuming raw/I/O pin has physically retired. In-flight cleanup pins
remain tracked and charged by their actual owner until unwind completes. A ticket
whose data has been consumed may remain live solely for its separately charged
metadata. Neither that ticket nor a liveness probe resurrects its data ref.

Revocation is distinct from refund. Calling a ref's close revokes any ongoing
consumer's publication immediately; its raw pin and write/transport copies
remain charged until their owners unwind and drop them. A late successful
scanner, I/O completion, seal attempt or send cannot publish after its scope
retires. The consumer checks the exact owner/scope/request epochs around every
await and before output completion. Failed/error paths retire private callback
and parser frames before credit is returned, including caller-held exceptions
with cyclic GC disabled. A malformed or foreign ref never refunds hidden
sibling storage; the existing supplied-valid-handle cleanup rule affects only
that handle, not the target's other records.

BaselineTicket/SyncControl DTOs and NativeTransportTicket headers keep explicit
independent control/metadata leases. Consuming or closing `ticket.data` releases
only that data buffer/control's credit. It cannot release a live ticket/header,
request, pending tail, batch container or detached header copy. Ticket close
drops its own metadata before closing that metadata lease and closes any still
owned data ref idempotently. Ref records cannot silently own metadata allocated
under a lease they will refund at consume. Copies and raw/header overlap are
included in the same aggregate heap/encoded peaks.

Repeated cancellation/close joins the same owned cleanup; it cannot launch
unbounded cleanup jobs or create a new timeout budget. Actual shutdown remains
bounded by the existing transport/deadline policies. No successful close or
zero-allocation claim is returned while physical storage/I/O remains live. If
bounded retirement fails, report failure with the affected owner quarantined
and its unresolved pins still charged; it is a failed qualification, not a
released resource or permission for detached work/late publication. Siblings
remain usable only when the affected underlying connection is still valid.

## Bounded native structural codec

```python
NativeTransportCodec.encoding: FrozenValue  # EncodingBinding below
NativeTransportCodec.header(raw: bytes, budget: BudgetProtocol)
    -> NativeTransportTicket
NativeTransportCodec.head(raw: bytes, budget: BudgetProtocol)
    -> NativeTransportTicket
NativeTransportTicket.header: HeaderRef
HeaderRef.materialization_bytes: int
HeaderRef.materialize() -> dict
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

`HeaderRef.materialization_bytes` is an exact nonnegative heap bound for a
complete independent detached structural dictionary. Reading the bound and
calling `materialize()` both reject after ticket retirement, even if the HeaderRef
object is retained. Generic code uses its own same-ledger adapter to reserve
that bound **before** calling materialize and keeps that independent copy credit
until the dictionary and any retained child references retire. Ticket close
cannot refund that copy's storage. Any additional encoded serialization/copy
needs its own prior encoded/heap reservation; the heap bound does not grant
encoded credit. Raw/payload bytes are never reachable through this API.

For the current expanded-native structural projection, a baseline dictionary
has the native closed header and all eight named table arrays empty except its
bounded original `receipts`; a transaction has the closed native header with
all eight operation arrays empty. These empty projections are scan metadata,
never an admitted empty table or a replacement body plan. Head/control returns
only its native closed bounded head/control fields and preserves explicit kind/
status, optional fields and failure. A compact encoding's corresponding bounded
projection must be defined by its separately agreed codec; this packet does not
invent a compact body plan. The source's borrowed `AcquisitionHeader.document`
is not implicitly the generic HeaderRef. A supported facade must implement the
public methods and revocation/copy bounds above without private graph access.

The generic usage pattern is explicit:

```python
copy_credit = ledger_adapter.reserve(ticket.header.materialization_bytes)
document = None
try:
    document = ticket.header.materialize()
    # Read bounded structural fields while the copy remains charged.
finally:
    document = None  # including all retained child aliases/error frames
    copy_credit.close()
    ticket.close()  # its separate metadata/raw credit, not copy credit
```

The supported scanner/facade prepays its returned ticket and header before
construction. It retains neither the callback budget capability nor an opaque
input alias. No method on HeaderRef grants material admission, a root query,
byte forwarding or proof authority.

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

RequestBinding is a closed new-sync object with exactly nine fields. Its seven
binding fields are `readerEpoch`, `requestId`, `catalogRevision`, ordered `hosts`,
selected `route`, `channelEpoch` and `bridgeId`; the two additional fields are
`role` and `encodingDigest`. Epoch/incarnation fields are 32 lowercase hex;
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

## Channel lifetime and acquisition lifetime

A RelayChannel is a transport/session lifetime. It can carry a watch longer
than fifteen seconds. It does not represent one perpetual acquisition and has
no renewable acquisition deadline. Its watch/connection remains subject to the
unchanged five-second heartbeat, fifteen-second blocked-client policy, bounded
queues/pins and disconnect cleanup. A delivery/heartbeat never renews evidence.
The Reader independently expires claims at their original proved lease limits.

Each cold read, warm read or recovery attempt has a separate bounded acquisition
capsule. Closing or timing out a capsule cancels and awaits **its** requests and
retires **its** tickets/refs. It leaves an unrelated watch, channel, shared
InputOwner, parent source and siblings usable after successful cleanup. An
underlying connection/protocol failure still closes the affected channel. The
capsule is not a material/authority capability and has no query or byte export.

The public signatures are the single factory/channel/capsule block above.
RelayChannel exposes no channel-wide baseline/changes/head alternative.
Constructors of RelayAcquisition and all ownership types are private. At most
one live capsule exists per channel; another begin rejects before allocating a
capsule or acquiring a source ticket. Control storage is prepaid on the same
ledger. The capsule is exact channel/request/input-epoch bound, single-use on
close, and cannot be rebound, reset or extended. Repeated close is safe.

`deadline_ms` is an exact nonnegative integer in the relay's CLOCK_BOOTTIME
domain. The relay records local begin time and requires
`begin <= deadline_ms <= begin + 15000`. All capsule baseline/changes, waiting,
scans, writes, retries and cleanup initiation retain **that same deadline**.
An operation cannot take a replacement deadline. A caller cannot begin another
capsule to finish or publish the failed logical acquisition. A truly separate
subsequent logical read is allowed only after retirement of the previous capsule
and still needs independently admitted material and a fresh Reader nonce.

The Reader owns the authoritative original absolute fifteen-second deadline,
started before connection/setup for a cold read and before acquisition work
for a warm read. Different hosts' boottime clocks are never compared directly.
A trusted local transport controller maps its allowed remaining operation budget
to a relay-local deadline; this does not replace, restart or extend the Reader
deadline. The Reader rejects any completion at/after its original deadline,
even if the relay's local bound has time left. Baseline fallback and all recovery
CPU/bytes remain part of the same logical acquisition and original budget.

`setup_deadline_ms` bounds the relay-local setup, including its source-session
opening; it is at most fifteen seconds after local setup start. Watch startup
has its own at-most-fifteen-second relay-local `startup_deadline_ms`. If setup or
watch startup belongs to an acquisition, it additionally fits that acquisition's
remaining **original** Reader/controller deadline. These separate lifetimes are
not serial grants of extra acquisition time. Successful watch startup retires
its startup timer; the ongoing stream uses heartbeat/blocked/disconnect rules.

A capsule may request a head while a watch exists. Material baseline/changes
still require stopping that channel's watch first; the stop/wait time counts in
the same acquisition deadline. Output remains serialized and charged; watch
backlog cannot grant extra proof time. Each head call consumes a fresh challenge
and has its own compact **two-second** bound, capped by the unchanged capsule
and Reader deadlines. No body catch-up/staging or old-generation retirement is
performed inside that proof. A known moved head revokes current Reader claims;
separate <=4 transactions AND <=8 MiB catch-up plus at most one fresh proof retry
must fit the original fifteen seconds. A second move or exhaustion fails.

Boundary fixtures for future runtime qualification:

| Situation | Required result |
| --- | --- |
| Watch is alive after the initial acquisition's fifteenth second | Stream may continue; old receipt/lease is not renewed |
| A new independent read on that healthy channel | New capsule/deadline and fresh nonce; existing material stays unconfirmed until ordinary proof succeeds |
| Proof RTT is 101 ms but completes one ms after the original acquisition deadline | Reject; short proof RTT cannot override the acquisition deadline |
| Known moved head and baseline fallback | Revoke immediately; all stop/catch-up/baseline/admission/proof work uses the existing acquisition budget |
| Caller tries to reset or reuse a timed-out capsule | Reject; no output or authority from that capsule |
| Capsule closes while a separate watch is paused | Its own requests/refs retire; unrelated watch refs remain charged/live |
| Watch write blocks during fresh proof | Both deadlines remain; failure/cancellation drains owned pins, without late proof publication |

The capsule itself exposes no material or authority, so the relay cannot decide
that a caller's later read replaces prior authority. Reader/controller checks
remain mandatory; a local deadline is only an additional resource/work bound.

## bridgeId mint, bootstrap and reconnect

`bridgeId` is minted by `create_sync_relay` using 128 fresh random bits, encoded
as 32 lowercase hex characters. It is immutable for that **relay factory
instance**, returned by readonly `SyncRelay.bridge_id`, and prepaid with factory
control storage. It is not chosen by the Reader, a source, request or native
owner. New factory/process incarnation always mints a new value. The native
ownerEpoch, native binding/root and source alias are independent identities.

An explicit bounded transport bootstrap precedes the complete RequestBinding
and setup. On the same authenticated connection:

```text
Reader -> {protocol:"mesh.state-sync/1", kind:"hello", nonce}
Relay  -> {protocol:"mesh.state-sync/1", kind:"hello", nonce, bridgeId,
           role, descriptor, sourceBinding, encoding, features, limits}
```

Both values are closed strict JSON, at most 65,536 bytes including framing.
Nonce is a fresh Reader-generated 64 lowercase hex string. This is a setup
correlator, not the compact authority-proof nonce. The trusted generic sync
server performs this exchange using the fixed factory's readonly bridge_id and
configuration before calling `open_channel` with the received complete binding.
All hello parsing/DTO/output buffers are prepaid and retained through drain.
Before `open_channel` takes valid-argument channel ownership, that server owns
the connection and cleans up a failed hello. No import/source/role is selected
by the incoming hello fields.

The Reader validates the echoed nonce, expected authenticated host/route, exact
configured role/descriptor/source/encoding and limits. It then creates its fresh
channelEpoch and the complete immutable RequestBinding, copying bridgeId from
that verified offer. The setup echoes that exact binding on the same
connection. `open_channel` independently requires its request.bridgeId to equal
`SyncRelay.bridge_id`; it never accepts a caller-specified replacement bridge
identity. A missing/mismatching hello or setup closes/rejects; no fallback.
Hello/setup establish transport binding only, never current material or leases.

The complete nine-field RequestBinding and its challenge-request digest are
exactly those specified above. A fresh authority nonce is generated for every compact
proof after material acquisition/admission. A request, channel, route, role,
encoding, source or bridge replacement invalidates the old binding and its
pending proofs/refs. No setup reply or reused hello authorizes an old proof.

| Identity | Owner and lifetime |
| --- | --- |
| readerEpoch | Reader instance; changes on Reader replacement |
| requestId | Reader's logical configured read/watch request; changes when that request is replaced |
| channelEpoch | Reader, fresh for every authenticated connection including reconnect to the same process |
| bridgeId | Relay factory incarnation; stable across channels of that live instance, changes on factory/process replacement |
| native ownerEpoch | Native owner incarnation; never minted/changed by Mesh setup |
| proof nonce | Reader, fresh/single-consume for each proof attempt, including the one allowed retry |

A reconnect to the same live relay may retain bridgeId but **must** change
channelEpoch, verify a new hello and bind a new request/channel. A fresh SSH
relay process/factory changes both. Source sockets/native roots may be identical;
that does not preserve old request/authority handles. Existing Reader cache refs
remain bound to their original request/channel. No admission-reuse capability
is introduced here: new-binding material requires its ordinary admission path
and a fresh proof within the acquisition budget. All such work counts in cold/
recovery/end-to-end totals. Two aliases may share one native owner/root but keep
their exact independent SourceBinding, channel/ref credit and Reader checks.

Required additional runtime cases are reconnect to same/different factory,
Reader-chosen/mismatched bridgeId rejection, cross-channel hello replay, old
challenge/ref rejection, fresh channel nonce and no native-root hash per alias.
The retained r2 arithmetic fixtures remain unchanged; these lifecycle cases
require actual agreed API implementation and independent qualification.

## Ownership, failure and close table

| Event | Storage/credit and effect |
| --- | --- |
| source scope retires | Its reserve/resize/seal and late publication reject; active physical buffers/pins retain credit until awaited cleanup |
| data ref consumed while ticket retained | Retire data only; separately leased header/control remains charged and revocable |
| header materialization | Prepay detached copy; ticket close cannot refund a surviving copy |
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

## Exact review and phase boundary

The retained stdlib oracle `scripts/reproduce-sync-relay-vectors.py` and
`docs/evidence/2026-10-16-delta-sync/relay-api-r2-vectors.json` specify unchanged
encoding/request/challenge hashes, two-alias SourceRoot wrappers and attenuation/
whole-RTT formulas. The twelve positive and four rejection fixtures use toy
unadmitted descriptors/roots. Their nested raw-fragment preservation is arithmetic
and splice evidence only. The toy fragment contains internal literal line feeds;
it is not accepted native newline-delimited runtime framing. Real single-line
frames, escaped newlines, strict delimiter/chunk handling, every nested size cap
and body-invalid Reader rejection remain mandatory runtime tests.

Observer's exact r2+r3 review and independent arithmetic support the direction;
this r4 document is the one proposed complete API for the next byte-bound
Mesh/Observer/coordinator agreement. It explicitly accepts the public HeaderRef
completion; no reviewer is asked to infer acceptance of older bytes or to first
implement a missing candidate class. The original cache-backed InputOwner.close
publication defect remains an independent implementation gate and is not fixed
or accepted by this distinct relay contract.

| Phase | Required record and work |
| --- | --- |
| A1 contract closure | Exact r4 bytes/hash; Mesh agreement, Observer source/native/identity/context/head/clock/lifetime agreement; coordinator records explicit amended-role/API closure |
| G1 dependent implementation | Only after A1 closure: implement the agreed relay factory/controller/source facade and ownership APIs; qualify source correctness, cleanup, unchanged resource caps and performance gates |
| G2 pair/transport qualification | Independently qualify immutable installed pair, actual populated IPC/fixed SSH, full/active/old/material roles, capacity, matched end-to-end CPU/bytes/RSS/latency and rollback; later artifact/consumer promotion remains separately owned |

Required G1 ownership cases include paused baseline/transaction/watch, full+active
aliases, four-transaction batches, head/control, capacity before receive/copy/
parse, malformed/duplicate header, failed/foreign/double consume, session/watch/
capsule retirement with active I/O, held data/header/copy references, late
resize/seal, metadata after data consumption, disconnect and repeated cancellation.
After many consume cycles, every registry must remain bounded by live controls,
not history. GC-disabled held exceptions and repeated close must retire all
actual owned graphs; unresolved storage cannot be hidden by zero counters.

Further cases include absent admission/semantic capabilities; corrupt and
self-consistent domain-invalid material at the Reader; roots/receipts/context/
clock/request/role/encoding/nonce replay; actual moved heads and one bounded
retry; baseline-required/gap/duplicate/overflow; reconnect to same/different
factory; capsule/watch/sibling isolation; strict native and nested framing.
Count source intake, callback/header/copy scratch, pending/rest/batches, staging,
all pins, queued transport output and owned descendants in shared peaks and CPU
scopes. Keep the unchanged 100/500/2000, one/four reads, 1/4/16 subscribers and
cold/dense/recovery matrix. Storage fit or arithmetic is not resource/performance
acceptance. Failed dense CPU and unqualified packed recovery remain open.

No normative old lock/schema is regenerated, no compact ID or new package is
allocated and no route, service/provider, sibling runtime or rollout changes.
