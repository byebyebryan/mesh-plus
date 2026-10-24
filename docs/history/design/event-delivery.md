# Agent event delivery and the Mesh boundary

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

## Current and proposed products

Agent Observer's `bca4c26` documentation checkpoint adds a reviewed
[local native event design](../../../reference/agent-observer/docs/state-and-events-design.md).
Its API 2, state snapshot/watch wire 4 and service protocol 2 remain unchanged.
The event wire, endpoint and concrete schemas are proposed and have their own
producer implementation gates. Mesh Read 1 can therefore proceed against the
current state API without waiting for event publication.

The subsequent `8776cc6` checkpoint explicitly prioritizes
[discovery/monitoring state push](../../../reference/agent-observer/docs/state-push-design.md)
and defers native occurrence-event normalization, emitters and replay. It is a
documentation/study refinement; accepted production read wires are unchanged.
This Mesh event section remains a future compatibility boundary, not a dependency
of polling or state subscriptions.

Mesh Plus's reusable catalog, delivery sessions, transport backends, scope/incarnation guards,
deadlines and bounded subscriber hosting apply to both products. Their delivery
semantics differ. An adapter descriptor must declare its product and delivery
model; it cannot silently feed events into a replacement-view coordinator.

The [delivery candidate](../../../contracts/mesh-delivery-v1/contract.md) now defines
first-class subscriptions, start barriers, cancellation, credit and typed stream
termination independent of SSH. Its opaque event payload/cursor fields require
the producer's accepted validators. Synthetic admission-cursor examples do not
allocate Agent's future event wire or infer Tmux native events from state diffs.

| State product | Native event product |
| --- | --- |
| Full snapshots replace older views | Ordered admitted records retain their identity |
| Coalescing uses gap and full resync | Loss requires an explicit cursor/retention gap |
| Source leases bound current assertions | Receipt clocks describe original admission, not current session facts |
| Recovery restores a current view | A state snapshot cannot reconstruct missed occurrences |
| View revision is material publication order | Per-host admission sequence and publisher epoch order delivery |

## Future event networking contract

After the producer freezes its separate event contract, define a distinct Mesh
event profile with the same local/fleet rule: one host and many hosts use the same
shape, and native event records keep their existing host-qualified identity,
event ID, meaning, actor/correlation and immutable metadata context. Common host
delivery outcomes can reuse Mesh scope/status definitions; the Mesh Read 1 watch
replacement algorithm cannot carry an ordered event history.

An event fleet cursor is a bounded map of owning host/source/publisher epoch to
the producer's native cursor. There is no fleet-global native chronology and no
cross-host timestamp sort that establishes causality. A host failure affects its
cursor/coverage without stopping healthy event channels. Reader checkpoints must
include progress past filtered records, not just records displayed by a client.

Subscribe with explicit live, retained or after-cursor semantics. Preserve the
producer's replay barrier, loss floor, source epochs, retention bounds and typed
restart/gap outcomes. Never silently advance an expired cursor or repair event
loss with a state snapshot. Replay-ID suppression, alert coalescing and long-term
notification history belong to clients, not Mesh transport.

Network delivery cannot imply native completeness, exactly-once callback
identity, successful work or current phase. A replayed event can remain useful
after its session disappears, without authorizing Resume or Open. Original
receipt clocks remain in their owning clock domain. If a client requires a
remote age bound, prove it through a correlated owner-side response; receipt
arrival or reconnect cannot reset event time. Unlike state, an event does not
expire into an inferred session lifecycle state.

This is a compatibility boundary and following design gate, not an allocated
Mesh event wire or selected source. Final request/frame schemas, aggregate replay
limits and fair scheduling need the producer's E0 contract. Existing base state
tests claim no event replay acceptance.

A local Mesh service can share a live event tail only after independently
satisfying each reader's replay interest. Different after-cursors initially use
distinct channels or independent replay barriers; a late join is never silently
changed to live-only. The service has bounded transient delivery queues, not a
durable journal or a new event retention authority.
