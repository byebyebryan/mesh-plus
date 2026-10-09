# Discovery and monitoring state push

Date: 2026-10-09. Active design refinement following the user's decision to
defer native notification integration. This supersedes the scheduling of the
[native occurrence-event plan](state-and-events-execution-plan.md), whose
research remains useful but whose implementation is deferred. The
[review](state-push-design-review.md), [validation report](evidence/2026-10-09-state-push-refinement/REPORT.md)
and [following work](state-push-execution-plan.md) describe this narrower pass.

## Goal and existing implementation

Give read clients an initial discovery/monitoring view and current replacement
views as observations change. Reuse API 2, snapshot wire 4 and local Service 2.
The normal a11 service already supplies this product; the task is to refine its
meaning, client consumption and validation rather than build a new event bus.

The engine accepts passive provider samples and owns reconciliation, independent
runtime/history receipts, uncertainty and finite unsaved-row retention. The
service hosts collection helpers, optional native refresh hints, periodic
fallback reads and bounded subscriber delivery. Read clients consume normalized
facts without native provider, process or attachment queries. mesh-plus owns
network delivery in its separate repository/thread.

Native hints are scheduling inputs only. Deferring native occurrence/notification
work does not disable existing Codex daemon or Claude file refresh hints. The
service still polls/reconciles when hints are unavailable. Optional hooks and
Kitty/D-Bus sender/title/body/Open integration are outside this pass.

## What a state update means

The public unit is a **complete bounded view**, including source health, coverage,
limitations and exact scoped rows. Complete view means a replacement of this
publisher's current inventory under its declared bounds; it is not a complete
native census when a provider/source declares partial coverage.

| Meaning clients can observe | Interpretation |
| --- | --- |
| Row first appears | This identity became visible in the observation view; it need not be a newly created session |
| Runtime value changes | Current native evidence now reports running, parked or unknown, within source scope |
| Phase value changes | A running session is now observed working, blocked, waiting or unknown |
| Metadata changes | Title, recorded cwd/project, kind or conversation activity changed according to its own evidence |
| Row is omitted | The current view no longer retains it; omission supplies no stopped/parked/deleted assertion |
| Source health/coverage changes | Observation confidence or scope changed; this is distinct from native work phase |

These are conceptual meanings of comparing views, **not new public event names
or callback commands**. No session-created/stopped, permission-resolved,
turn-completed or task-success occurrence is manufactured from them. Working to
waiting can follow several native outcomes; the sampled phase is its own fact.
An unavailable observation is never recast as waiting or parked.

Receipt refresh can publish a new revision without changing a session value.
`viewRevision` orders service projections, not native episodes. New sample clocks,
delivery clocks and revisions must not trigger repeated UI actions. Age is
computed from original conversation activity and display time; poll/heartbeat
arrival never makes an old conversation recent.

## Publication and recovery contract

Keep the existing newline-framed Service 2 endpoint and operations. Cached pull
and watch use the same reconciled view, potentially at different instants.
Subscribers cannot force refresh, choose stores/cadence, start providers or ask
for actions. Starting another reader does not start a collector per client.

| Frame | Read-client behavior |
| --- | --- |
| Initial view | Validate scope/order/leases and replace the cache; establish a baseline |
| Warming status with null snapshot | No complete roster yet; do not substitute an empty discovery result |
| Later view | Validate, replace atomically, update timers and optionally compare semantic values with a still-valid baseline |
| Heartbeat | Transport liveness only; no snapshot and no cached-evidence renewal |
| Gap | Stop current claims until the required full resync; retain last-known display separately if useful |
| Resync | Replace the cache and establish a new baseline; no backfilled transitions or notification burst |
| Error / EOF / receive timeout | Invalidate delivery/current claims; reconnect explicitly with a new guard |

After reconnect, the first complete view replaces everything for that host/source
selection. Per-connection sequence starts at one. Publisher identity, boot/time
scope and configured source binding cannot change within a valid connection.
No persisted cursor, historical replay or separate event protocol is required.

Slow readers can receive gap/resync or be disconnected. The service does not
need to retain every obsolete view to provide current state. A client cannot
silently use its old cache as a new authoritative observation after loss.

## Freshness while the client is idle

A validated frame is current at receipt, not forever. Clients retain the
**receipts belonging to the accepted complete view** and run a local expiry
timer even when no new view arrives. A later heartbeat does not extend those
cached deadlines. Transport silence and evidence expiry are independent limits.

For the existing public granularity, conservatively invalidate a source at the
earliest expiry of its current/partial components until a newly projected view
is accepted. Already stale/unavailable components add no new current deadline.
Do not expire unrelated providers merely because one source fails or expires.
Retain last-known values/clocks visibly as stale where useful; never turn source
loss into parked. A new view may independently retain current runtime while
history/workspace/activity is stale, according to producer projection.

Consumers can calculate human age between frames without changing evidence.
Delayed parse/delivery can expire a frame before acceptance; reject that current
claim. Local clients validate UID/socket peer, kernel boot and time namespace.
Forwarding clients must preserve source clocks and apply their own conservative
age accounting; raw BOOTTIME cannot be compared across hosts or on a device.

## Shared read consumption and optional differences

Use the pure public/service parsers and `StreamGuard`, plus the explicit local
read transport where applicable. A small future reusable client cache can own
baseline/replacement/gap/timer bookkeeping. It must remain provider independent
and import no collecting, action, terminal or alert implementation. This study
does not introduce that helper as an accepted API.

Client differences use full `hostScope/provider/namespace/nativeIdKind/nativeId`
keys, never array positions, title, cwd or PID. Track value/health changes
separately from lease renewal. Baseline, resync, invalid-to-current recovery and
filter/order changes must not be treated as native transitions. Default child
filtering and urgency/activity ordering remain client presentation policy.

The machine-facing producer stream contains all retained rows. The CLI watch
applies presentation filters, excluding positively classified children by
default. For a complete producer comparison use `service watch --include-children`,
or the unfiltered local transport / `service snapshot`. A caller choosing
`--provider` or child filters must retain that selection context; excluded rows
are not negative evidence. Changing selection establishes a new client baseline.

A future helper can expose observed added/changed/omitted keys for rendering,
but no new delta wire or server filter is needed to establish this state product.
Do not duplicate comparison policy in core simply to decide desktop alerts.

## Full views, deltas and constrained clients

Retain full replacement views initially. They avoid delta-base tracking,
retained history, patch ordering and partial-application recovery. Measure cost
on actual ordinary inventories rather than adding a new protocol speculatively.
Transport memory and queues stay bounded under the existing frame limits.

Agent Plus and host-side readers can consume the general metadata view. ESP32
devices may require a host-side bridge to produce a smaller display projection
with selected rows/fields, original identity and conservative freshness. That
bridge is a read consumer; the core does not acquire device-specific framing,
icons, hardware limits or board time synchronization. Its implementation/native
device acceptance is separate. A compact format is not implied by the 349 request.

If measured traffic/latency later makes full views unacceptable, separately
review identity-keyed state deltas with explicit base revision, atomic updates
and unconditional full resync. Session-array indices are not stable identity.
No delta/replay implementation is justified by this design pass alone.

## Scope and settled decisions

Settled: current-state push, shared polling/reconciliation plus existing hints,
complete replacement views, explicit baseline/gap/resync, independent evidence
expiry and source faults, full identity, original activity clocks, client-side
presentation, and current API/wire/service versions.

Deferred: native occurrence normalization/emitters, completion/attention event
protocol/replay, provider hook wiring, Kitty/D-Bus/desktop notification replacement,
349 notification sender/title/Open and physical acceptance. Existing ordinary
native notification behavior stays independent. Optional read-cache ergonomics,
compact device projections and mesh integration retain separate scoped gates.

No ordinary provider/service restart, changed cadence, managed deployment,
frontend edit or attachment implementation is required to adopt this design.
