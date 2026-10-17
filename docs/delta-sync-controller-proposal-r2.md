# Relay network controller proposal, revision 2

Status: **proposed contract, not runtime or interface acceptance**. This packet
fills the network-dispatch gap in the closed [A1 R4 API](delta-sync-relay-api-r4.md).
The Python relay, actual owned source and completed-batch path already execute;
their [source-to-relay evidence](delta-sync-completed-relay-g1.md) does not execute
this dispatcher. Exact owning/coordinator review of these bytes precedes its
implementation. This is a concrete contract review under existing G1 authority,
not another general role or user-permission request. This standalone revision
supersedes [R1](delta-sync-controller-proposal-r1.md), whose immutable SHA-256 is
`18e8f7f97462613a72353e00e2ffa579b452fdf7855a91443198dca00d51900e`.
It resolves coordinator `02071bd`'s two controller-only findings: cleanup receipt
authorization after intentional work retirement, and timestamp provenance for
prebuffered/fragmented commands. Neither finding is a measured runtime failure.

The proposed `open`, `command` and `command-result` records below are additional
control-plane grammar. In particular `command-result` is a new proposed record
kind, not an existing R4 native control or delivery variant. An implementation
must explicitly support this grammar; existing peers must reject it. R4 hello,
setup, delivery, native material/control/head, descriptor, encoding, request
binding and SourceRoot bytes stay unchanged. This packet allocates no schema,
encoding, native contract, CLI route or package identity and edits no lock.

## Entry point and configured ownership

Proposed public generic entry point:

```python
serve_sync_relay(
    relay: SyncRelay,
    carrier: SyncControlCarrier,
    *,
    setup_deadline_ms: int,
) -> awaitable[None]
```

The trusted caller selects the configured relay and authenticated IPC/fixed-SSH
carrier. The factory already binds host/source/profile/descriptor/encoding and
structural callbacks; requests cannot choose any of them, an import, command,
socket, UID or authentication method. There is no profile/cache/admission hook
in this entry point. The owning caller keeps the factory alive and closes it
separately; serving one connection never closes a shared factory/source/ledger.

Before creating or enabling a carrier's userspace receive buffers, its owning
server/connector prepays their actual capacity, pending tails and metadata on the
same relay ledger. The exact minted ingress/range handoff below is required;
an ordinary `LineChannel` or already prebuffered `StreamReader` cannot be wrapped
by assigning a timestamp at dequeue. This entry point additionally reserves its own
bounded parser, command, reply and task storage before receive/copy/parse. It
takes ownership of the valid channel after exact argument validation. It always
awaits that channel's source, operations, watch and physical transport cleanup.
Invalid arguments leave the carrier with its caller. Valid setup failure retires
only this connection, without closing siblings or the native owner service.

The setup bound is an exact local BOOTTIME integer, strictly in the future and
no more than 15,000 ms after function entry. It covers hello, open parsing,
source-session opening and setup output. No phase gets a new 15-second grant.

## Exact prepaid carrier and timestamp handoff

The following proposed public generic factories own only a configured transport
connection. Constructors of the resulting carrier/frame types are private:

```python
control_carrier_from_ipc(sock: socket.socket, *, ledger: AllocationLedger)
    -> SyncControlCarrier
control_carrier_from_stdio(read_fd: int, write_fd: int, *, ledger: AllocationLedger)
    -> SyncControlCarrier

SyncControlCarrier.output_channel: LineChannel
SyncControlCarrier.receive_control(*, maximum_bytes: int, deadline_ms: int)
    -> awaitable[StampedControlFrame]
SyncControlCarrier.aclose() -> awaitable[None]

StampedControlFrame.start: int           # absolute first byte offset
StampedControlFrame.stop: int            # exclusive end, including LF
StampedControlFrame.first_byte_ms: int   # conservative local ingress bound
StampedControlFrame.header: HeaderRef
StampedControlFrame.close() -> None
HeaderRef.materialization_bytes: int
HeaderRef.materialize() -> dict
```

IPC takes one already authenticated, accepted, not-yet-userspace-read socket.
Stdio takes the fixed server process's unread input/output descriptors, selected
by its trusted entry point; request fields cannot choose descriptors or commands.
Exact nonnegative integer fd arguments reject bool. Authentication/peer UID and
fixed SSH route stay owning prerequisites, not something these factories infer.
After argument validation the factory takes connection/fd ownership, including
failed construction cleanup, and prepays before making buffers/protocol objects
or enabling input. A failed argument check takes no ownership. Stdio is a
library server entry, not a selected launcher or new SSH command allocation.

Both adapters implement the same ingress algorithm. They retain at most 65,536
physical encoded ingress bytes, at most 256 timestamp ranges and two live frame
handles, all within the one supplied shared ledger. The whole ring/pages, unused
capacity, transport scratch, range slots, frame/header/decoder metadata, pins and
fixed reader/writer controls are prepaid, not charged only by live payload size.
A single nonblocking read transfers at most 4,096 bytes into prepaid application
capacity; any additional library read/copy capacity is independently prepaid.
Capacity refusal pauses before the read/copy, not after materializing a chunk.
The two-handle bound is on parsed/minted frames; any further undecoded raw tail
stays only in that prepaid byte ring. Once active and pending slots are occupied,
input pauses rather than creating a queue of parsed commands or work tasks.

Immediately **before each nonblocking transfer into the application's first
userspace buffer**, the adapter samples local CLOCK_BOOTTIME into `floorMs`.
It then performs that one nonblocking read without suspension, parser callback
or dispatcher reentry between sample and transfer. EAGAIN transfers no bytes
and records no range; a later readiness attempt samples again. A successful read
of n bytes appends `[nextOffset,nextOffset+n,floorMs]` before exposing or parsing
them. Every userspace byte must have provenance from its first admission,
including bytes held by any lower carrier buffer. It is insufficient to stamp
only when copying an older buffer into this ring. No read-ready callback using
an ordinary prebuffered StreamReader qualifies this algorithm.

Absolute offsets start at zero per authenticated connection, advance once per
actual byte, never wrap uint64 and have no overlap/gap. Timestamp samples are
exact nonnegative local integers and cannot regress in that local clock scope.
The factory captures the controller's local boot/time-namespace clock scope;
scope replacement or sample regression retires the carrier. These are local
ingress timestamps, never compared directly with a remote host's BOOTTIME.
All spans are minted/bound to the exact carrier/connection epoch/ledger; callers
cannot supply replacement offsets, floors or raw frame DTOs. `receive_control`
extracts exactly the next complete LF frame, records its original offsets and
the floor of the range containing its **first** byte, and validates strict
framing/bounded JSON. It never substitutes receive-call, dequeue, parse-complete
or dispatch time. Source/native payloads do not enter this control reader.

One read may contain multiple frames plus a partial tail: every byte initially
shares that read's floor. Removing a completed frame leaves the tail's original
range/floor. A fragmented frame keeps the floor of its first fragment even when
later fragments arrive much later. Pausing reading does not change existing
ranges. Bytes still solely in kernel buffers are first admitted on the later
actual application read; the independent Reader end-to-end clock still includes
network/kernel/paused time. No foreign timestamp subtraction is introduced.

Ranges for dropped input leave promptly. Before a read would need a new range
at the 256-slot limit, the adapter may coalesce adjacent ranges in place using
their minimum/earlier floor, without a 257th slot or another allocation; it may
never move a floor forward. Coalescing can conservatively
reject a command sooner, and that cost counts in actual latency/recovery gates.
An already minted frame keeps its immutable original floor; coalescing affects
only later frame extraction and never rewrites a captured command deadline.
If any bytes lack a trustworthy floor or connection provenance, it fails closed
`sync_control_provenance` before command dispatch. There is no `now()` fallback,
ordinary-LineChannel fallback, inspection of private StreamReader buffers or
inference from an empty application queue. An adapter migration could use an
older proved lower bound, but this revision exposes no migration/import API;
unproved prebuffered channels are unsupported and closed by their owner.

The header has the same bounded/revocable copy convention as R4 HeaderRef,
applied to generic command JSON: the caller prepays and retains any detached
dict copy before materialize; closing the frame cannot refund a retained copy.
All frame metadata/header access rejects after frame close. Actual ingress spans
stay charged while parser/frame/raw aliases are pinned; no early ring reuse or
credit return. Held errors are sanitized before refund. Frame/header close is
idempotent. Carrier close revokes its input/frames and joins its own reader,
writer and physical cleanup; only after aliases/I/O retire are their leases
released. It never closes the shared ledger or another connection.

`output_channel` is the exact writer/lock view passed to existing relay
`open_channel`; it is bound to this carrier's coordinated close. The controller
only reads through `receive_control`; a direct `LineChannel.receive()` on this
view rejects `sync_control_provenance`. One owner coordinates process/stdio
discard and shutdown so legacy LineChannel cleanup cannot create an uncharged
second input reader. The existing direct Python relay API and old transport
paths are unchanged. This carrier is proposed, not present in current runtime.

For the coordinator fixture, bytes admitted at 1,000 with 2,000 ms remaining
have deadline 3,000. Dequeue at 3,500 rejects before work or success receipt;
neither a blocked busy result nor a coalesced/fragmented tail can mint 5,500.

## Framing, bootstrap and limits

All records are strict single UTF-8 JSON lines with exactly one terminal LF.
Reject BOM, raw CR/internal LF, truncation, duplicate keys at any depth, invalid
Unicode, floats/nonfinite values and negative zero. Object variants are closed;
absent and null are distinct. Every numeric field below is an exact integer;
bool is never an integer. These are new control-plane rules, not a change to
opaque native body parsing or old protocol framing.

Hello and server setup retain R4's complete 65,536-byte bound including LF.
Client open and all command/results are at most **8,192 bytes including LF**,
within that existing control ceiling. Parsing enforces depth <=8, <=512 total
JSON nodes, <=32 members per object/array, and <=4,096 decoded characters per
string before constructing an unbounded DTO. A streaming syntax/shape preflight
must use bounded scratch before ordinary decoding; post-decode checks alone do
not prepay a hostile tree. Canonical request binding remains <=4 KiB. Accepted
wire whitespace need not be canonical; digests always use existing canonical C.

On one authenticated connection:

1. Reader sends the exact R4 `{protocol,kind:"hello",nonce}`. Server returns the
   exact R4 offer with fresh nonce echo, factory bridgeId and fixed configuration.
2. Reader verifies nonce/configuration/limits and mints a fresh channelEpoch. It
   sends the following closed new `open` value:

   ```text
   {protocol:"mesh.state-sync/1", kind:"open", controllerVersion:1,
    requestBinding:<complete nine-field R4 binding>, remainingMs}
   ```

3. Server requires exact version 1 and the configured binding, uses the smaller
   of its original setup deadline and `openFirstByteMs + remainingMs`, and calls
   the existing `relay.open_channel`. The reply is the exact R4 `setup`, without
   an extra invented native control or changed feature list. Receiving setup in
   response to this strictly closed open is the controller-version agreement.

`remainingMs` is in 1..15,000. It is a relay-local work restriction, not trusted
authority. The Reader starts its own absolute acquisition deadline before cold
connection/setup and rejects at or after that original deadline. Wire duration
never transfers a foreign BOOTTIME timestamp or renews that deadline. Parse,
queue and write time after first byte is subtracted, never added back. Hello or
open replay on another channel cannot preserve the old channelEpoch/nonce.

## Closed command variants

Every command has the following common fields and exactly the additional fields
listed in the table:

```text
{protocol:"mesh.state-sync/1", kind:"command",
 request:SHA256(C(completeRequestBinding)), sequence, operation, ...}
```

Client command sequence is contiguous 1..2^64-1 on this channel. It is separate
from R4 outbound delivery sequence and native generation/cursor. Duplicate, gap,
overflow, wrong request digest, unknown operation/version/field or wrong variant
type closes this connection before source work. No replay history is retained:
the next command counter, current capsule ID and bounded live operation slots
are sufficient. Equality of a digest on a different connection cannot rebind it.

| operation | Additional fields | Dispatch and constraints |
| --- | --- | --- |
| `begin` | `remainingMs` | No live capsule; call `begin_acquisition(deadline_ms=firstByteMs+remainingMs)` after checking that this bound remains in the future. New capsule ID is this command's sequence. |
| `baseline` | `acquisition` | Exact live capsule ID; existing capsule baseline, no watch. |
| `changes` | `acquisition,base,target,maxTransactions,maxBytes` | Exact live capsule; existing completed-changes path, no watch; exact tags, 1..4 transactions and 1..8,388,608 bytes, no extra terminal-control allowance. |
| `head` | `acquisition,challenge,remainingMs` | Exact live capsule; strict original challenge, 1..2,000 ms further restriction; may run beside a watch. |
| `watch` | `acquisition,cursor` | Exact live capsule; no active material/head operation or existing watch; startup fits unchanged capsule deadline. Watch ID is this command's sequence. |
| `stop-watch` | `acquisition,watch` | Exact live capsule and watch ID; revoke/watch-close and await physical cleanup; time counts in that capsule. |
| `end` | `acquisition` | Exact live capsule; no active operation; close capsule only, preserving an unrelated established watch. |
| `cancel` | `acquisition,command` | Exact live capsule and currently active baseline/changes/head command; synchronously revoke capsule/its publication, then cancel and await only that operation/capsule. Established watch survives if its underlying channel remains valid. |

All IDs are exact positive uint64 integers. Tags are R4 NativeTag arrays
`[bindingDigest,generation,root]`; generation is an exact uint64, both digests
64 lowercase hex. Cursor is `[ownerEpoch,generation,root]` with exact original
epoch (nonempty <=256 characters), uint64 generation and 64-hex root. Challenge
is exactly the three 64-hex `nonce,target,request` fields from R4. These fields
are structurally checked, not admitted native/context/root evidence. Base/target
binding, chain/cursor/epoch and native descriptor comparison still happen in the
existing relay/source, followed by independent full Reader admission.

`begin.remainingMs` is 1..15,000 and captures a new logical acquisition's one
relay-local deadline at its first command byte. A capsule ID cannot be revived,
extended or reused after end/cancel/deadline. A subsequent begin is only a new
read, not a way to finish an old failed acquisition. Reader recovery/reconnect
keeps its existing logical read's original deadline and one moved-head retry.
The server cannot infer that policy from an untrusted new command ID; independent
Reader enforcement remains mandatory.

Each live capsule has one prepaid deadline task. At expiry it revokes and awaits
that capsule's operations, clears its live ID after physical cleanup, and leaves
an unrelated established watch alone. A genuinely later independent read may
begin on that healthy connection after cleanup; its bound is not the expired
initial setup timer. A cold/recovery Reader still includes setup in its own
unchanged acquisition deadline.

At most one active material/head command and one pending dispatch/control frame
are retained. There is no general work queue. While an operation runs, the one
reader can accept its matching cancel into that control slot. Another valid work
command gets a bounded `busy` result with no source/ref acquisition; while that
result/control slot is blocked, reading pauses within already prepaid transport
capacity. It cannot keep parsing an unbounded stream of busy replies/cancels.
Repeated local cancellation/close joins the same bounded cleanup task; no
cancellation task history is stored. Wire commands are not retransmitted: a
duplicate sequence or new cancel naming a no-longer-live operation rejects,
rather than reviving a consumed command. A disconnected caller retires this
channel, not the factory.

## Results and output ordering

Each admitted command has at most one proposed closed control-plane result,
with the eligibility and suppression rules below:

```text
{protocol:"mesh.state-sync/1", kind:"command-result", request,
 command:<client sequence>, operation, status, code, through}
status = "ok" | "failed" | "cancelled"
code = "none" | "busy" | "deadline" | "source" | "capacity" | "output"
```

`ok` requires `none`; `cancelled` requires `none`; `failed` requires another
listed code. Through is an exact uint64: the last fully drained R4 delivery
sequence before this result on the same output stream, zero before any delivery.
It is sampled under the same output serialization as the write. A later watch
frame may follow it. A command result does not advance R4 delivery sequence and
does not claim any material generation, complete chain, evidence/currentness or
lease. The Reader strictly dispatches this new kind separately from existing
delivery/native control/proof; it never passes a result to cache admission or
confirmation. Unknown/ambiguous result kinds close rather than being ignored.

Native transaction completion remains the **original** source-owned control,
within its codec's bound (Agent 16,384 bytes), and its whole nested Mesh control
is <=65,536 bytes including LF. A changes `ok` is sent only after all original
transactions and terminal control drain. It cannot replace a missing native
complete, a recovery control, or prove a chain; Reader validates the native
chain and target independently. Native recovery is forwarded exactly, followed
by `failed/source`; no synthesized complete. Baseline/head `ok` similarly means
output drain only; only the ordinary independent Reader proof can grant current.

Watch `ok` means source watch startup and handle creation finished; its watch ID
is the watch command ID, with no new JSON field. It does not mean the first
native watch frame has arrived or that the cursor/currentness is proved. Stop/end
`ok` is a cleanup barrier. Cancel sends `cancelled/none` for the original command
after its cleanup, then `ok/none` for the cancel command **if each remains
individually eligible before its original deadline**. Replies may be out of
client-command order when a valid busy request is rejected during another
operation; command ID, request and through make each association explicit.

Malformed framing/binding/state-ID replay closes without success. Valid busy
rejection preserves the active capsule/watch. Source/protocol/output failures
use the existing affected-channel retirement rules. A result is optional on
failure if safe bounded output is no longer possible. Error text/tracebacks/native
payload are never put in result codes. Work revocation forbids subsequent
material/proof/work success; the narrow terminal-receipt permits below remain
separate. No receipt may be written at/after its own original deadline or after
connection/request retirement. Reader EOF/timeout is failure, never an implicit
ack, even if a later cancel receipt confirms cleanup.

## Terminal receipt authorization after work retirement

Before admitting any command, the controller prepays one bounded receipt record.
It captures immutable carrier/connection epoch, complete request digest, command
ID, operation, applicable capsule/watch/target-command IDs and **original**
deadline. The active-operation slot and one pending/control slot own at most
two records total. Cancel uses the original record plus its one control record;
it does not allocate receipt history. No constructor or arbitrary send method
exports these internal permits to wire callers or sources.

The permit authorizes only one `command-result` matching those captured IDs and
one latched terminal outcome. It exposes no raw/material/proof forwarding,
intake, cache, source callback, graph or currentness capability. Revoking the
capsule stops work immediately but need not destroy a narrowly eligible cleanup
receipt. Closing/replacing the channel/request/carrier invalidates **all**
receipts immediately, including end/cancel receipts. Repeated local cancellation
joins the same cleanup; it cannot rearm a receipt or mint another deadline.

Receipt deadlines are fixed as follows; none starts at cleanup or result time:

| Record | Captured receipt deadline |
| --- | --- |
| `begin` | `beginFirstByteMs + remainingMs`, exactly its new capsule deadline |
| `head` | Original `min(capsuleDeadline,headFirstByteMs+remainingMs,headFirstByteMs+2000)` |
| Other command naming a live capsule | That capsule's unchanged deadline |
| Typed busy `begin` | `min(existingCapsuleDeadline,beginFirstByteMs+remainingMs)` |
| Typed busy `head` | The same original restricted head bound above |
| Other typed busy command | The named live capsule's deadline |

Before accepting a cancellation the controller verifies its target is still the
active operation under that exact capsule. It latches that operation's cancelled
outcome before retiring work. A target already completed/failed/timed out cannot
be relabelled cancelled. `end` similarly captures its permit before intentionally
retiring its idle capsule. The complete allowed carve-out is:

| Outcome | May survive intentional work/capsule retirement? | Additional requirement |
| --- | --- | --- |
| Baseline/changes/head/begin/watch `ok/none` | No | Matching work/capsule remains live, operation/output complete, deadline live through drain |
| Stop-watch `ok/none` | Watch retirement only | Matching capsule live; that watch's physical cleanup complete |
| End `ok/none` | Yes, that exact end only | Idle capsule's own cleanup complete; no pending child work |
| Original target `cancelled/none` | Yes, that exact accepted cancel only | Target operation and capsule cleanup complete; original target receipt deadline still live |
| Cancel command `ok/none` | Yes, that exact cancel only | Same cleanup complete; cancel record's original capsule deadline still live |
| `failed/busy` | Yes as a denial, not work | Busy was latched at admission, no work/ref acquired; original denial deadline still live |
| Other `failed/<code>` | Yes as a failure only | Latched failure and affected operation cleanup complete; channel valid and original receipt deadline still live |

A cancelled head can have an earlier deadline than its cancel command. If head
cleanup ends at/after that head deadline, suppress the original cancelled receipt;
the cancel `ok` may still be sent before the capsule deadline after cleanup.
It proves cleanup only and cannot make the expired head successful. If either
record expires while waiting for output locks, no frame for that record begins.
At/after local command expiry, cleanup still proceeds with physical credit held,
but no `failed/deadline` or other late result gets a fresh output window. The code
remains available for an earlier reported deadline failure while the receipt's
own bound is still live. Successful cleanup never extends the original read.

Busy consumes its valid client command sequence and captures a denial record
in the one pending slot. It never acquires a new source ref or extends the busy
operation. A later idle/retired capsule cannot turn that denial into executable
work. On expiry discard/release that reply only after its storage aliases unwind;
resume reads only within prepaid capacity. Malformed or stale-ID commands still
close without creating a success permit.

Under the same output lock, after all previous delivery bytes drain, the writer
snapshots `through` and rechecks exact permit/channel/deadline before each write
and after drain. Through is latched once for that attempt and remains immutable
through its copies/pins; no retry refreshes it. Native frames cannot interleave inside the result. Only a fully
drained eligible result consumes its permit successfully; failure/expiry retires
it without reissue. If expiry/cancellation occurs after a partial write, retire
the affected connection and keep physical copy/pin credit until cleanup; no
completion/retry line is appended. Bytes already emitted before expiry are not
claimed retractable. The Reader independently rejects late/partial results at
its original deadline and never treats them as proof or native completion.

This is transport cleanup authorization, not a longer material/proof lifetime.
No end/cancel/busy result can call a source operation, restore a capsule ID,
renew evidence, finish an expired proof or catch up material inside the nonce
operation. At most two live receipt records retire promptly; no consumed-command
history is added.

## Original deadlines through the dispatcher

The controller receives the first-byte floor and exact offsets from its minted
carrier frame; it cannot manufacture them from bounded receive completion.
Before source work it rejects expired receive/parse/dispatch. `head` uses:

```text
headDeadline = min(capsuleDeadline, headFirstByteMs + remainingMs,
                   headFirstByteMs + 2000)
```

This exact restriction follows the operation through source, scanner/header
materialization, both output locks, each pre-write check, drain and result.
Waiting behind an independent watch grants no extra time. An outer async timeout
alone cannot prevent a synchronous callback from crossing the deadline and then
writing; the inner pre-write liveness check must receive this earlier bound.

Proposed additive generic restriction (no Observer source/scanner change):

```python
RelayAcquisition.head_after_nonce(challenge, *, not_after_ms: int | None = None)
    -> awaitable[None]
```

Omission retains the accepted R4 public-call two-second behavior. An explicit
exact local integer only reduces `min(capsuleDeadline, callStart+2000)`; an expired
value rejects before source I/O. It cannot replace/extend the capsule or original
Reader proof deadline. The dispatcher passes `headDeadline` here. This signature
is proposed for same-byte review, not implemented by this packet.

The Reader generates a fresh authority nonce only after material admission,
records its own original two-second proof start before enqueue/write, sends only
its remaining proof budget, and rejects completion at either original deadline.
No body catch-up, stage/old-root reclamation or material admission occurs inside
the compact head operation. A moved head revokes claims immediately; separate
<=4/8MiB catch-up plus one fresh proof retry stays within the original 15 seconds.

## Accounting, failure and required execution

The controller has no independent cap. All parser scratch, raw read capacity,
DTOs/containers/decoded strings, active and pending command copies, reply bytes,
watch state, task/cleanup captures and transport copies use the same <=32 MiB
encoded and <=64 MiB heap ledgers as full/active aliases and the relay/source.
Capacity is reserved before allocation, including failure replies; copying one
command while its raw storage survives charges both. A reply's `through` snapshot
does not refund pending native/output pins or prepaid incoming data. Control
bounds grant no additional allowance. Pending tail, paused watch and blocked
writer storage remain charged. The carrier prerequisite above must be measured,
not excluded by calling its bytes preexisting.

Closed command-shape bounds permit a fixed small preflight stack; exact scratch
and DTO charges must be established by implementation and at-limit tests, not
guessed into acceptance by this document. One accepted socket cannot bypass
the existing 16-client total or native 8 pending/8 subscription bounds. Closing
one alias/controller never shuts down a sibling/shared ledger. All cancel/close
paths revoke before awaiting and join the same owned physical cleanup with GC
disabled and caller-held errors; a failed cleanup retains charged quarantined
storage and fails qualification.

The unchanged [R1 reference](evidence/2026-10-16-delta-sync/reproduce_controller_contract_r1.py)
and [R1 vectors](evidence/2026-10-16-delta-sync/controller-r1-vectors.json)
check command shapes, command counters/IDs and deadline arithmetic. The new
[R2 reference](evidence/2026-10-16-delta-sync/reproduce_controller_contract_r2.py)
and [R2 vectors](evidence/2026-10-16-delta-sync/controller-r2-vectors.json)
add range/first-byte and terminal-receipt state/arithmetic cases only. They
import neither Mesh nor Observer and provide no server, native validator,
admission, ownership/resource or actual-clock/transport evidence. Bootstrap,
result parsing/serialization, real buffer ownership/reads/copies, scheduling,
expiry-task cleanup and actual cancellation concurrency are specified here but
are not implemented by the synchronous toy models.

After exact review, implementation must qualify actual authenticated hello/open/
setup, same/different-factory reconnect and old-channel replies, strict variants/
duplicate keys and at-limit refusal before receive/copy, no work queue growth,
watch/head interleaving, original 2s/15s boundary and synchronous scanner overrun,
cancel/end barriers and partial output, actual CompletedChanges drain/Reader
admission, source ref tracking, held-error/GC-disabled physical teardown and
full/active sibling isolation. Add real timestamped ingress with coalesced tails,
fragmented commands, paused/blocked reads, unavailable provenance, range pressure,
offset/clock errors and receipt expiry before/inside locked output. Include all controller/carrier bytes and CPU in
cold/recovery and aggregate peaks. Separate populated IPC/fixed SSH, 2,000-row
delivery/recovery, dense CPU/bytes/RSS and immutable installed-pair gates remain;
no route/artifact/schema/encoding allocation or consumer rollout follows this
planning packet. Earlier evidence keeps its original source provenance.
