# A1 relay and owned acquisition API review packet

Status: **Mesh proposal; counterpart agreement and coordinator A1 record pending**.
This document specifies the proposed API, not implemented transport or accepted
schemas. It is paired with RLCD amendment A1 revision 2, commit
`665f6caaed99740a755de9467c7ae53322f7e720`, document SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`.
The frozen G0 appendix remains SHA256
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`.
Later revisions need new byte-bound review. No dependent relay implementation
starts before Mesh, Observer and RLCD record agreement on these exact inputs.

## Explicit role and setup

Keep `create_sync_publisher(source, profile, source_binding, budgets,
owns_source=True)` as the G0 material-admitting factory. Its semantics remain.
Add a separate trusted factory:

```text
create_sync_relay(source: CachedSyncSource, descriptor: SyncDescriptor,
                  source_binding: SourceBinding, budgets: SyncBudgets,
                  owns_source: bool = True) -> SyncRelay
SyncRelay.aclose() -> awaitable[None]
```

The relay accepts no `SyncProfile`, exports no semantic query or admission
capability and creates no `OwnedSyncCache`. Its descriptor and source binding
are exact trusted configuration. The source factory fixes expected native
hostScope, UID, socket/service, native descriptor, selector and clock binding.
No request can change that configuration or select a module, command or source.

New sync setup explicitly declares `role = "material-publisher"` or
`"transport-relay"`, the complete descriptor, the exact native encoding digest,
source binding, baseline/transaction/watch/head-after-nonce features and limits.
The Reader's trusted configuration requires one exact role and encoding; setup
must echo them exactly. Missing, unknown or different values are unsupported.
There is no automatic role change, profile substitution or old-route fallback.
The compact encoding/schema identifiers remain subject to the separate codec
review; A1 allocates no such identifier or schema digest.

The per-host RequestBinding contains `readerEpoch`, `requestId`,
`catalogRevision`, ordered `hosts`, selected `route`, `channelEpoch`, `bridgeId`,
`role` and `encodingDigest`. The first eight preserve the existing aggregate
request shape. Epoch/incarnation fields are fresh local 128-bit values encoded
as 32 lowercase hex characters; request IDs retain their accepted bounded string
form. The canonical complete binding is <=4 KiB. Limits remain bounded by both
endpoints and never exceed G0. The challenge's request digest commits this
complete binding, including role and encoding. Neither role nor encoding is
added to NativeBinding or SourceRoot: descriptor/source commitments keep the
accepted G0 framing, while request binding prevents a role/encoding substitution.
Concrete closed setup/delivery schemas are still a G1 freeze gate.

## Owned source session and input transfer

Keep the existing plain-byte source methods and ticket fields unchanged. Add
an explicitly requested owned session; an unsupported source fails setup.
The Observer implementation uses structural protocols and needs no Mesh import.

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
OwnedSyncControl.status, reason, tag, cursor       # bounded structural claims
OwnedSyncControl.close() -> None

OwnedSyncCache.input_owner() -> InputOwner
InputOwner.reserve(heap_bytes: int, *, encoded_bytes: int) -> InputReservation
InputReservation.resize(heap_bytes: int, *, encoded_bytes: int) -> None
InputReservation.seal(exact_immutable_bytes: bytes) -> OwnedInputRef
InputReservation.close() -> None
OwnedInputRef.nbytes: int
OwnedInputRef.close() -> None
```

An owned watch yields an `OwnedInputRef` or `OwnedSyncControl`. The relay mints
an InputOwner from its aggregate ledger and exact local configuration/request
binding; it need not construct a cache to obtain one. Its source session binds
that input owner. A Reader cache mints its own input owner. The public observer
source never constructs a Mesh admission capability or accesses private state.

InputOwner and all its refs are local, non-serializable, non-forgeable handles.
They bind one ledger, complete configured source/descriptor/codec identity and
request/channel epoch. A seal transfers existing credit without copying and
without parsing, validating or admitting the bytes. It fails if credit does not
cover the live bytes, object/control overhead and encoded storage. Resizing
grows before allocation; shrinking is allowed only after the corresponding
storage has actually retired. Raw buffers, mutable/immutable conversion overlap,
framing copies, queued output, parser scratch and ticket/control metadata all
remain charged. No bytes subclass or bare-byte return transfers that ownership.

Cache baseline/stage/confirmation inputs additionally accept an OwnedInputRef;
stage_batch accepts a tuple of such refs. These are consuming calls: success or
failure retires every supplied handle, including unprocessed batch members.
The underlying buffer stays charged until its last actual decoder/I/O pin
retires. The cache still independently performs its complete ordinary admission
or proof path. A foreign owner, role/configuration mismatch, retired epoch or
already consumed ref fails before admission. There is no validation memo on a
byte-ownership ref, and the relay cannot mint an admitted ref through sealing.

Source sessions own only their requests and watches. Session close cancels and
awaits those operations, retires their refs/reservations and leaves the parent
client usable. Closing the parent closes its sessions, never the owner service.
Relay close always closes its session; `owns_source=True` additionally closes
the parent source client. Two aliases may use separate sessions on one externally
owned client. This first packet requires separately minted/charged handles for
each alias; physical backing-store sharing is not a public v1 capability.
Each alias is independently admitted/proved at its Reader.

Owner/handle retirement immediately forbids use or publication. In-flight I/O
keeps its storage pins and charges until cancellation cleanup finishes. Repeated
cancellation cannot skip this awaited cleanup. Late completions cannot reseal
or publish into a retired request. Close is idempotent on every ownership type.
Saved exceptions must not retain private buffers, tickets, stages or reservations.

## Structural forwarding and chain checks

The approved source adapter scans the entire bounded native JSON grammar with
bounded scratch and validates its closed structural envelope/decoded header.
It checks descriptor, tag/cursor shape and binding, native owner/context/clock
fields, operation kind, limits and sequence. Its ticket metadata is derived from
those same bytes, remains charged and grants no semantic authority. Opaque body,
entry, old-value, domain, membership, seal and root validation remains mandatory
at the Reader. The independently configured native codec supplies the matching
bounded structural scanner for a compact encoding; the relay never invokes its
semantic profile callbacks or expands the whole material into DTOs.

Baseline atomically captures tag/cursor under the native publication barrier.
Changes return exactly the contiguous requested base-to-target chain, <=4
transactions AND <=8 MiB; completion must identify that exact pair. Watch begins
strictly after its cursor or signals baseline-required. Subscription sequence
is separate from native cursor/generation and advances for each delivered frame,
including controls. A sequence gap, unknown cursor, conflicting duplicate,
descriptor/context replacement or overflow revokes the affected stream and
requires explicit recovery. No incomplete chain is relabeled as complete.

An exact native transaction duplicate may be forwarded as an unadmitted frame;
Reader duplicate recognition remains bounded to its retained exact tokens and
cannot renew authority. The relay neither semantically composes nor repairs
transactions, and does not infer absence or currentness from transport controls.
Heartbeat is transport health only. Keep G0 limits: combined 16 native clients,
8 subscriptions/8 pending per channel, 5-second heartbeat and 15-second blocked
client policy, bounded journal and aggregate heap/encoded/pin ownership.

Native payload bytes are forwarded verbatim. A JSON delivery encoder may splice
the validated native JSON value into its envelope, separating only the verified
terminal framing delimiter; it must not parse/re-serialize the payload, quote it
or base64-expand it. Every copy/overlap and outer envelope counts at its boundary.
Transport forwarding does not solve the currently failing compact native wire
or dense decoded-storage gates.

## Fresh proof wrapper and attenuation

Use the current Mesh source-proof shape, with role/encoding in RequestBinding:

```text
{protocol: "mesh.state-sync/1", kind: "proof", descriptor,
 sourceBinding, sourceTag, requestBinding, challenge,
 bridgeId, bridgeClock, head, remaining}
challenge = {nonce, target: SHA256(C(requestedSourceTag)),
             request: SHA256(C(requestBinding))}
```

The Reader generates the fresh nonce and starts the whole proof timer before
sending. After receiving that nonce, the relay invokes the live owner's
`head_after_nonce(challenge)`. It cannot use a cached reply, retained old target,
pipe liveness, full export, collection or catch-up. A relay always wraps the
owner's actual fresh tag, even when it differs from the Reader's requested tag.
It computes SourceRoot from that native root and the exact configured binding
using the unchanged G0 two-layer formula and vectors. The complete original
receipt/cohort heads and echoed challenge are forwarded without semantic edits.

BridgeClock uses the same authenticated host/boot/time namespace as the native
head and is sampled after it. With `d = bridge.boottimeMs-owner.boottimeMs >= 0`,
for each structurally valid native attenuation pair `(key,a)` emit
`remaining(key) = max(0,a-d)`. Preserve exact key coverage and reject duplicates
or invalid integers. This requires no provider receipt interpretation. The
Reader independently matches original receipts and cohorts to its admitted
material, obtains semantic receipt expiry/health through its pure profile and
enforces both native and bridge limits. No relay-derived lease can extend them.

All existing Reader checks remain: exact descriptor/source/request/challenge,
native/source roots and owner/context incarnation; UID/clock/time namespace,
monotonic owner/bridge clocks and whole RTT/margin; independently admitted
material/indexes/body/schema/domain/cross-record constraints; and bounded
restrictive check_head. Proof is <=49,152 native +16,384 envelope =65,536 bytes.
It carries no body or transaction. A known move or source failure immediately
revokes affected host authority, including previously confirmed claims.

Proof queue/transport/native/check work stays inside 2 seconds. Catch-up is a
separate operation, followed by at most one fresh nonce retry under the original
absolute 15-second acquisition deadline. Further movement, eviction, exhausted
credit or limits yield explicit bounded baseline recovery/failure. No late proof
may publish. Material publishers retain their independent pre-proof admission.

Arithmetic review fixture: native time 10000, bridge time 10015, attenuation
500 gives bridge remaining 485. Reader sent/received 20000/20060 with margin
100 yields remote expiry 20385 under the unchanged `remote_expiry` rule. Zero
attenuation or elapsed >=attenuation yields remaining 0; bridge time before
native, changed key coverage or negative/boolean values rejects. These are
specified outcomes, not executed end-to-end relay tests.

## Acceptance still required

Observer must confirm this same-byte packet's source-session/input-ownership
shape, structural native scanner, fresh-head operation and context/identity
compatibility. Mesh must implement and test the agreed API, then both owners
agree the exact schemas/codec/input lifetimes; RLCD records A1 acceptance before
dependent relay transport implementation. Pending codec/dense-storage review
continues separately. None of this packet accepts current source capacity.

Qualification includes domain-invalid yet self-consistent material, corruption,
roots/receipts/binding replay, owner/clock changes, moved head during cold work,
gap/overflow/duplicate conflict, absent relay admission/query capabilities and
repeated cancellation with zero leaked ownership. Preserve old/material routes.
Run real local IPC/fixed SSH 100/500/2000 cold/recovery and full/active steady
acquisition with startup, Reader admission, fresh proof and all descendants.
All G0 CPU/byte/latency/RSS/plateau, 64/32 MiB aggregate and frame/client/deadline
gates remain unchanged. No new package allocation, installation or rollout is
authorized by this planning packet.
