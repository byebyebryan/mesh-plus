# A1 relay lifecycle clarification, revision 3

Status: **candidate for exact Observer/RLCD review**. This answers the two
concrete lifecycle questions returned by root's review of Mesh `e68b264`.
Root verified r2's byte-only role and twelve framing/arithmetic plus four
rejection fixtures; that is not exact API acceptance or A1 closure.

The complete proposed contract is the unchanged
[`delta-sync-relay-api-r2.md`](delta-sync-relay-api-r2.md), SHA256
`8616bfba7c05dcf8982e431309bcd0bdf354c91bc023fdf0fcf85dcbe4c7abdd`,
**plus this clarification**. This document supersedes only r2's channel-wide
acquisition deadline/operation signatures and adds the explicit bridge identity
bootstrap below. All role, codec, structural source/ref, ownership, proof,
Reader-validation and resource requirements remain. A later edit needs another
announced same-byte review; r2 is not silently edited.

The role reference is root A1rev2 `665f6ca` / SHA256
`6eaa408376f91bb7c5e4276812927fd2bfce2445412fb02a211bea22a5e52aef`.
Frozen G0 `a376bc84...`, old schemas/lock, a7/a23 and deployment remain unchanged.
No relay implementation begins before joint exact review and root's A1 record.

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

The exact revised public signatures are:

```python
# Factory parameters/semantics remain exactly r2.
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

The r2 `RelayChannel.baseline/changes/head_after_nonce` methods are replaced by
the capsule methods above; they are not alternative unbounded entry points.
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
and r2 setup. On the same authenticated connection:

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
that verified offer. The r2 setup echoes that exact binding on the same
connection. `open_channel` independently requires its request.bridgeId to equal
`SyncRelay.bridge_id`; it never accepts a caller-specified replacement bridge
identity. A missing/mismatching hello or setup closes/rejects; no fallback.
Hello/setup establish transport binding only, never current material or leases.

The complete nine-field RequestBinding and its challenge-request digest remain
exactly r2. A fresh authority nonce is generated separately for every compact
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
The existing r2 arithmetic fixtures remain unchanged; these lifecycle cases
require actual agreed API implementation and independent qualification.

## Remaining gate

Root's conceptual role/arithmetic review does not close this amended API.
Observer must review the exact r2+r3 tuple for source, head, identity/context,
clock and ownership compatibility; root records A1 agreement after both owning
reviews. Compact codec agreement, actual owned source/controller integration,
dense/cold/packed recovery, complete resource/RSS and installed IPC/SSH/end-to-end
gates remain open. No budgets, authority checks, old/material roles, package or
normal service pins change in this planning clarification. No rollout.
