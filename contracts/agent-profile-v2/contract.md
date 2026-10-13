# Agent timing profile extension

Reviewed 2026-10-12 for Agent Observer's approved native timing delivery pass.
This addendum permits `agent-observer.mesh-candidate.v2` with native API 3,
snapshot/watch 5 and Service 3. It preserves Mesh SDK interface 1, Read 1,
Delivery 1, carriers and the existing Tmux and Agent v1 profile bytes. There is
no conversion between native versions and no implicit profile downgrade.

## Normative boundary

The packaged v2 profile embeds the exact Session shape of Observer source
`280ddab6e8f8a28fa92e08461a4888e0a504d4ca`. Frozen snapshot and Service 3 schemas
under `reference/agent-observer-timing` bind the producer input. Domain callbacks
must admit the complete native frame through its supported pure facade; generic
Mesh validation still independently checks scope, digest, chronology, nonce proof,
original component receipts and delivery lifetime. Timing metadata stays copied
and attributable. Mesh neither collects provider data nor changes native clocks.

The Observer owner validates `lastUpdated`, whole `latestTurn`, capabilities,
source observation time and component/sample/context binding. Current timing
cannot borrow an unrelated or replaced lease. Original native event times,
source-wall observation, source BOOTTIME and reader BOOTTIME remain different
clocks. A receipt proof authenticates freshness; it does not make a native
timestamp an exact phase-entry or lossless event clock.

## SDK selection

Existing `descriptor(domain)` defaults retain v1. The compatible optional
`profile_id` keyword selects this reviewed v2 descriptor for the Agent domain.
Unknown identifiers and domain/descriptor mismatches fail closed. Explicit pure
profiles supply the descriptor to Reader, CachedPublisher and ReadGuard. Their
aggregate protocol and packaged validator must follow that selected identifier,
including digest-cache separation. Default reference clients remain v1 and
cannot negotiate a v2 source by adding fields or retrying after rejection.

Tmux's independently selected factory/profile is unchanged. A shared launcher
may compose Agent v2 and Tmux v1 factories without changing generic delivery.
Each owner's native, immutable-package, carrier, resource and scoped operational
acceptance is independent. This addendum alone selects no artifact or endpoint.

## Required acceptance

Verify frozen v1/Tmux schema and native-input byte preservation, exact v2 schema
projection, strict old/new rejection, selected descriptor/digest/guard binding,
standalone core and historical v1 native gates. Agent Observer separately gates
its v2 owner callbacks and both-host IPC/SSH cached poll/push/proofs, source expiry,
recovery and sibling isolation against exact installed packages. WSS transport
promotion and physical dashboards retain their separate acceptance gates.
