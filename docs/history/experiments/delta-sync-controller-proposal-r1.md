# Relay network controller proposal, revision 1

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

Status: **proposed contract, not runtime or interface acceptance**. This packet
fills the network-dispatch gap in the closed [A1 R4 API](delta-sync-relay-api-r4.md).
The Python relay, actual owned source and completed-batch path already execute;
their [source-to-relay evidence](delta-sync-completed-relay-g1.md) does not execute
this dispatcher. Exact owning/coordinator review of these bytes precedes its
implementation. This is a concrete contract review under existing G1 authority,
not another general role or user-permission request.

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
    channel: LineChannel,
    *,
    setup_deadline_ms: int,
) -> awaitable[None]
```

The trusted caller selects the configured relay and authenticated IPC/fixed-SSH
channel. The factory already binds host/source/profile/descriptor/encoding and
structural callbacks; requests cannot choose any of them, an import, command,
socket, UID or authentication method. There is no profile/cache/admission hook
in this entry point. The owning caller keeps the factory alive and closes it
separately; serving one connection never closes a shared factory/source/ledger.

Before creating or enabling a carrier's userspace receive buffers, its owning
server/connector prepays their actual capacity, pending tails and metadata on the
same relay ledger. Passing an already unaccounted `StreamReader` to this function
does not qualify that boundary. This entry point additionally reserves its own
bounded parser, command, reply and task storage before receive/copy/parse. It
takes ownership of the valid channel after exact argument validation. It always
awaits that channel's source, operations, watch and physical transport cleanup.
Invalid arguments leave the channel with its caller. Valid setup failure retires
only this connection, without closing siblings or the native owner service.

The setup bound is an exact local BOOTTIME integer, strictly in the future and
no more than 15,000 ms after function entry. It covers hello, open parsing,
source-session opening and setup output. No phase gets a new 15-second grant.

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

Each accepted command has one proposed closed control-plane result:

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
after its cleanup, then `ok/none` for the cancel command. Replies may be out of
client-command order when a valid busy request is rejected during another
operation; command ID, request and through make each association explicit.

Malformed framing/binding/state-ID replay closes without success. Valid busy
rejection preserves the active capsule/watch. Source/protocol/output failures
use the existing affected-channel retirement rules. A result is optional on
failure if safe bounded output is no longer possible. Error text/tracebacks/native
payload are never put in result codes. No success/result may be written after
its owning command/capsule deadline or revocation; expired operations can close
without a failure reply. Reader EOF/timeout is failure, never an implicit ack.

## Original deadlines through the dispatcher

The controller records the first-byte timestamp before bounded receive finishes.
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

The [reference model](../../evidence/2026-10-16-delta-sync/reproduce_controller_contract_r1.py)
and [toy vectors](../../evidence/2026-10-16-delta-sync/controller-r1-vectors.json)
check command shapes, command counters/IDs and deadline arithmetic only. They
import neither Mesh nor Observer and provide no server, native validator,
admission, ownership/resource or actual-clock/transport evidence. Bootstrap,
result parsing/serialization, scheduling, busy replies, expiry-task cleanup and
real cancellation concurrency are specified here but are not implemented by the
synchronous toy model.

After exact review, implementation must qualify actual authenticated hello/open/
setup, same/different-factory reconnect and old-channel replies, strict variants/
duplicate keys and at-limit refusal before receive/copy, no work queue growth,
watch/head interleaving, original 2s/15s boundary and synchronous scanner overrun,
cancel/end barriers and partial output, actual CompletedChanges drain/Reader
admission, source ref tracking, held-error/GC-disabled physical teardown and
full/active sibling isolation. Include all controller/carrier bytes and CPU in
cold/recovery and aggregate peaks. Separate populated IPC/fixed SSH, 2,000-row
delivery/recovery, dense CPU/bytes/RSS and immutable installed-pair gates remain;
no route/artifact/schema/encoding allocation or consumer rollout follows this
planning packet. Earlier evidence keeps its original source provenance.
