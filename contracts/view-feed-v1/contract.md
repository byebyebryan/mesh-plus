# Complete-view change feed v1

This additive application protocol implements the decisions in
[`docs/view-change-feed-design.md`](../../docs/view-change-feed-design.md).
It is explicitly selected and negotiated. The frozen state Delivery v1 wire,
capabilities, full snapshot and nonce proof formats remain unchanged. The old
semantic delta engine remains dark. This contract does not advertise native
event replay, durable resume, action authority or a selected deployment.

## Setup and binding

Only `ViewFeedBridge`/`view-feed-serve`/`view-feed-bridge` serve this feature.
`ViewFeedClient.connect` uses an ordinary snapshot request whose sole parameter
is `viewFeed`: protocol `mesh-plus.view-change-feed.v1`, fresh lowercase
32-hex `nonce`, configured JSON `selector`, and exact `FeedLimits` fields.
The reply has exactly protocol, kind=`ready`, nonce, hostId, sourceId, profile,
contractDigest, selector and limits. All identities and the nonce must match.
Each limit is a positive exact integer, never bool, and may only narrow the
configured limit. The exchange is connection-scoped, must precede watch, and
does not read the native source. Unsupported endpoints fail setup without
trying a different wire or falling back to an ordinary watch.

The initial carrier is an owned IPC or stdio `LineChannel`. Remote configuration
uses the existing authenticated catalog policy and fixed SSH command
`mesh-plus view-feed-bridge --source <id> --stdio`; reached-marker and route
reporting rules remain the existing ones. No WSS feed support is advertised.
The publisher's configured selector is captured at setup; no client can change
it by supplying a different JSON selector. Source factory configuration remains
the publisher's responsibility.

## Packets and atomic reconstruction

`packet.schema.json` is the closed structural grammar. Exact Python scalar
checks supplement JSON Schema: identity components are strings or integers,
never bool/float, and revisions are exact positive integers through 2^53-1.
Typed identity arrays have 1..16 components; no string component exceeds 16384
characters. The SDK profile supplies the complete record identity, including
birth/incarnation when required. Hashes use the existing canonical JSON digest.

Each subscription has a fresh streamId and monotonically increasing revision.
The binding contains host/source/profile/contract, exact selector, native
publisher and clock incarnation, and bridge incarnation. A changed binding or
stream requires a replacement; a delta cannot change any binding field.
`owner` always replaces the entire `NativeState.owner`, including frame-local
support tables. `envelope` replaces all Bridge metadata except ownerFrame.
Every packet is a candidate, with null nonce/error: it can never be a proof.

A replacement has null base, full ordered records, empty upserts/removals and
the exact identity order. A delta has the exact prior revision+digest as base,
target revision=base+1, whole-record upserts, removals, and either the exact new
order or null when the old order is still exact. Duplicate or overlapping keys,
unknown removals, record/key disagreement and incomplete/duplicate order reject.
Empty views, metadata-only changes and pure reorders are valid. Missing records
are never interpreted as a partial patch. Reuse of a record ID under a new birth
is a removal plus a new record, according to the profile's identity.

The encoder decomposes only a complete validated full Bridge candidate. It
constructs a provisional target from its proposed operations and checks the
restored native digest against the complete current native frame before making
any packet observable. The receiver independently reconstructs, restores the
native frame, verifies the digest and performs the ordinary profile/Bridge
validation before atomically changing its baseline. Failure exposes no prefix
or partially changed metadata. Transport gap invalidates the baseline; only a
replacement repairs it. Coalescing sends an explicit Delivery gap followed by a
replacement for the exact pinned queued target, even if the source has advanced
again. Reconnect starts a new setup and baseline; there is no persisted cursor.

The default comparison hashes complete canonical records. Optional trusted
`token(record)` plus `token_scheme` may avoid a record hash when a token matches.
Tokens are bounded strings (at most 128 JSON bytes) or integers (at most 256
bits), with an explicit bounded scheme name. Tokens do not replace whole-target
verification. A false unchanged token disables that encoder's optimization and
emits a checked replacement; a callback error rejects the operation. Full
replacement is also valid when a delta is larger or explicitly forced.

## Public surfaces and authority

`FeedEncoder.encode(candidate)` returns a `FeedMessage` or no message;
`FeedReceiver.apply(packet)` returns `FeedApplied`. Their borrowed JSON
containers reject ordinary mutation, retain their credit while borrowed, and
can be copied to plain JSON by the caller. Handles close idempotently.
`FeedMessage.replacement()` retains its exact historical target and works while
the message is live, including after the encoder closes. It must never reset to
some newer target implicitly. `FeedApplied.candidate` is the full original
Bridge candidate reconstructed from the packet.

`ViewFeedClient.subscribe()` returns normal Delivery data/control frames with a
validated full candidate in payload, so the ordinary `Reader` can consume it.
`ViewFeedClient.changes()` exposes owned `ViewFeedChange` objects with kind,
revision, upserts, removals, order and candidate, interleaved with explicit
Delivery controls. This API still retains an SDK baseline; it is not a stateless
event consumer. Callers close change handles and the iterator deterministically.
Application copies belong to the caller and need a caller resource policy.

Ordinary snapshot and nonce proof requests remain full native replies. The
ordinary Reader still obtains fresh full evidence through its existing path;
watch candidates are wakeups, not authority. Native currentness, receipt
attenuation and source-clock continuity remain the existing profile/facade
responsibility. A replacement, delta, change event, setup reply, gap or heartbeat
does not confirm a view or refresh a receipt budget.

## Resource and lifetime boundary

`FeedLimits` defaults are 32 MiB encoded, 64 MiB heap, 4096 records and the
existing Delivery frame maximum. One `FeedBudget` is shared across a connection's
subscriptions, queued parse trees, encoder/receiver state and serialization.
Limits cannot be enlarged at negotiation. Capacity failure refuses the operation;
there is no approximate target, truncated view or weaker admission route.

At `LineChannel` handoff, the feed prepays bounded raw/read/write overlap before
its first read/parse/operation. Opening the caller-supplied channel and any
pre-handoff buffering remain caller-owned; this is not a pre-connect allocation
guarantee. Capacity refusal closes that channel without source IO. Decode
lexically bounds depth/nodes and reserves parsed JSON/workspace before parsing.
Queued frame/payload aliases share credit. State copies, indexes, comparison
workspace, packet construction and retained outputs are charged separately;
credits survive active pins, retained errors and borrowed containers. Close
revokes further use immediately and joins owned IO/cancellation cleanup before
dropping carrier storage. Closing one subscription/client never closes siblings.
Budget peaks are reservation peaks, not RSS or unique physical allocation.

The boundary excludes caller-owned source input, profile/validator code and
caller copies. The existing source, ordinary Reader, owner cache and process
runtime still need their own accounting. These feed ledgers do not establish an
inclusive producer+source+relay+Reader 32/64 MiB or physical/RSS qualification.
Complete source reads, canonical target verification, native restoration and
ordinary proof traffic remain O(N). This feature makes sparse wire traffic
possible; it does not claim to solve the prior producer CPU/capacity failures.

## Freeze and qualification

This directory's separate LOCK pins its own contract/schema/reference vectors.
It cannot change the root accepted contract inventory or old packaged schemas.
The stdlib reference model intentionally imports neither runtime nor publisher;
it checks exact packet reconstruction vectors, not native semantics. Runtime
tests separately cover native validation and actual Delivery/Reader composition.
Source correctness, wheel importability, actual provider cost/RSS, populated
native/fixed SSH, immutable installed pairs and deployment are separate gates.
