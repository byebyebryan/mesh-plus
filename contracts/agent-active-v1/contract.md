# Agent active membership profile

This additive profile implements the separately authorized G1 following the
Mesh/Observer/RLCD G0 agreement. It does not select any operational role.

`agent-observer.mesh-active.v1` carries native
`agent-observer.active-feed` version 1 through SDK 1, Mesh Read 1 and Delivery 1.
The profile and exact native schema are locked separately from full Agent v3.
Existing full Agent v1/v2/v3, Tmux, generic Read/Delivery schema bytes, defaults
and proof semantics retain their meanings. The active profile is explicitly
configured and negotiated; unsupported service/profile/selector combinations
fail within existing bounds without full-roster fallback.

## Selection and replacement

The canonical fixed selector is Codex, user/unknown kind and current running
runtime. Phase is independent: loaded waiting/idle, blocked and errored threads
remain selected. Observer owns pure classification and native collection.
Every native frame binds the exact canonical selector/version/digest, original
service incarnation and source context, accepted generation, scope continuity,
domain decisions and original source receipts. No arbitrary wire predicates,
paths, imports or actions are added.

The owner-hosted cache projects each accepted engine generation once per fixed
selector before consumer IPC/SSH. Mesh receives complete projected replacements,
not deltas or an unprojected roster hidden in metadata. Generic records are only
selected unchanged API 4 bodies. Coverage and typed member-support, uncertain
and nonmember decisions live in projected owner metadata. Restoring owner plus
records must reproduce the complete projected native DTO exactly.

## Membership authority

Fresh complete coverage may retire absent selected identities only for its exact
host/provider/namespace/selector scope. Complete-empty requires the same proof.
Retain the full original daemon census predicate: loaded and saved census
completion with no unresolved native runtime status and no dropped/limited
classification. Completeness additionally requires exact original support for
every selected/nonselected decision used to classify that census. Missing kind,
runtime or saved-identity support makes coverage partial. An omitted loaded
identity alone is not parked. Positive parked and excluded-kind decisions need
their actual supporting samples and full five-part identity.

The producer captures transient runtime, kind, positive saved-identity, activity
and outcome support at acceptance and copies support with the actual value chosen
by reconciliation. Retention never binds old values to newer receipts. Original
support includes service/source context, component, accepted counter, sample and
expiry. Authority requires an exact match to the available original receipt map;
changed or absent support is context-only. The original census and union of the
actual classification dependencies independently bound complete scope validity.

Original positive validity, negative/completeness validity and consumer context
lifetime are separate. Expiry, pruning, gap or overflow never proves parked or
retirement. A valid prior retirement does not reverse when its evidence expires.
Partial reconnect and missed expired negatives may leave existing context
uncertain indefinitely under current consumer policy. Neither an identity query
nor a context timeout is added by this profile.

The recent-member ledger is limited to 4,096 tracked identities and 1 MiB of
canonical UTF-8 JSON for the whole ledger, including punctuation, identities,
supports, active/uncertain/nonmember entries and ordering watermarks. Full bodies
are separately charged against the existing frame capacity. Untouched dormant
history consumes no entries. Original last-positive horizons cannot slide on
cache reads, revisions, failures or reconnect. Capacity failure revokes only the
affected scope's continuity/current authority; it does not evict siblings or
pretend complete membership. Bounded failure metadata is reserved outside ledger
space. Recovery requires a fresh proved baseline, with changed continuity for
the failed/reset scope. Retain the existing 32-receipt per-host limit; no historic
receipt bank per ledger identity or dependency truncation is supported.

## Public read and delivery seam

Observer's pure active facade takes public `PreparedReadGuard.snapshot()` once
per accepted replacement to own only admitted selected bodies and their support.
Every query calls `current(now_ms, clock)` first, then `context()`. The facade
uses no private guard state and exports detached results. Current decisions and
individual fields require exact admitted support and all corresponding public
translated host receipts: matching accepted counters, current/partial health,
ready delivery, unexpired `expiresAtMs`, exact selector/incarnation/scope and
continuity. The minimum dependency deadline wins. Never subtract absolute remote
clocks. A raw retained header alone grants no current authority.

Zero-body complete coverage expires independently of body count. Conservative
generic whole-row expiry is not retirement: the facade masks each field against
its actual support while retaining its owned body as context. Gap, disconnect,
changed clock/incarnation or invalid admission revokes affected cache authority.
Consumer presentation context remains separate. Reconcile whole membership
before applying display or USB limits.

Snapshot/proof/subscribe retain existing negotiation and bounds. A proof admits
the unpredictable nonce before a fresh projected cached endpoint read. Watch
bytes alone are not proof. Mesh independently checks exact host/source/profile,
native digest, clock, receipt map, request/epoch and original remaining leases;
remote expiry retains whole RTT subtraction, margin and deadline. Reencoding,
heartbeat, reconnect and source cache lifetime cannot renew evidence or activity.
No digest-only proof, new capability, delta, replay or provider action is added.

## Acceptance and adoption

Lock revision 5 adds this profile/native reference without changing any prior
normative digest. The explicit descriptor binds SDK 1, native protocol/version,
profile-schema digest and the existing 8 MiB + 16 KiB Agent native frame cap.
The strict profile/native schema and codec bind the fixed selector and complete
projected DTO. Source/factory selection stays owned by Observer; Mesh admits
only the installed trusted factory's exact host/source/profile and capabilities.

Exact source and immutable wheel gates must qualify the public empty/partial/
field-expiry seam, mutation and proof failures, local IPC and fixed SSH,
restart/gap/reconnect/capacity cleanup, old full/Tmux compatibility and independent
producer admission. Controlled 100/500/2,000 dormant-row cases hold active work
fixed within byte limits. A 5,000-row single-host full inventory is a capacity
case. Attribute collector/cache, publisher, catalog, transport and consumer cost
separately. Runtime artifacts and independently selected collector/service,
publisher/read and consumer roles require later coordinated adoption and paired
rollback; source or wheel acceptance does not deploy them.
