# Observer contract adaptations

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

## Shared profile shape

Both candidate read profiles return `{protocol, schemaVersion, mesh, sessions}`
for local and fleet access. Experimental IDs are
`tmux-observer.mesh-candidate.v1` and `agent-observer.mesh-candidate.v1`.
These do not allocate new published Observation, API or service versions.

The owner adapter validates its original snapshot and service envelope first.
It stores snapshot metadata other than `sessions` in `mesh.hosts[].owner.metadata`
and the service header without `snapshot` in `owner.service`. The profile exposes
the unchanged rows in the top-level array. Reconstruction is lossless, including
coverage, limitations and unknown bounded source extensions where permitted.

`owner.protocol` and `owner.version` describe the native snapshot contract.
Service versions remain explicit inside `owner.service`. Source payloads are
validated by the domain facade; passing base JSON Schema alone is insufficient.
Any owner/row scope disagreement excludes the offending host instead of
relabelling returned data to fit the request.

| Concern | Tmux profile | Agent profile |
| --- | --- | --- |
| Existing native read | Observation 1, Service 1 | API 2, snapshot 4, service 2 at researched baseline |
| Row identity | hostId, serverGeneration, sessionId, createdAt | hostScope, provider, namespace, nativeIdKind, nativeId |
| Owner metadata retained | source, clock, sample, generation, capabilities, protocol/version | host, collection ID/time, source health, sources, errors, limitations, snapshot version |
| Validity components | Native owner receipt; local associations stay separate | Each provider/namespace's runtime and history receipts |
| Meaning of missing rows | Source coverage determines removal; transport cannot | Producer retention and coverage determine memory removal; transport cannot |
| Desktop fields | Downstream prepared coordinator adds its existing domain extension | No terminal/attachment fields are added to Observer |
| Refresh | Existing bounded Tmux tickets retained behind separate capability | No refresh added to service 2 or base Mesh Read 1 |
| Writes | Separate Tmux action client | Independently selected Agent writer; read version gives no write compatibility |

## Tmux Observer and Plus

Both producers expose cached request and state subscription hooks through their
adapters. The [delivery session](../../../contracts/mesh-delivery-v1/contract.md) owns
transport/subscribe/cancel/credit; native collector schedules and source codecs
remain Observer-owned. IPC and remote backends consume those same hooks. The
optional event product needs its own accepted codec; current state push does
not depend on native callbacks, replay or a new producer event vocabulary.

The first extraction can reuse `tmux_observer_client.mesh`, `ssh`, `_remote_state`,
`_command` and clock/proof code, but their current imports are Tmux-specific.
Move generic mechanics behind configured adapters; do not copy a complete Tmux
state machine into Mesh Plus. `_remote_state` compares session facts and desktop
inputs, which remain in the Tmux coordinator.

Native owner service and Observation 1 stay accepted interfaces while the new
mesh-aware profile is introduced explicitly. The same new profile is available
from a local owner adapter and a fleet reader. This satisfies local/fleet client
equivalence without changing old direct-read defaults.

Tmux's current Fleet 1 is already fleet-aware, but includes desktop context,
viewers, bindings and refresh tickets. Keep it as a compatibility projection
over the new networking input during migration. Desktop scan inputs retain
their separate owner association receipts and context epochs. Owner receipt
renewal does not force another scan when its relevant facts are unchanged.

Tmux Plus's artifact check binds runtime modules and package roots, not merely
schema versions. Packaging Mesh Plus must update that accepted tuple explicitly.
A module move alone must not be represented as installed byte parity. Preserve
Tmux Session v1 inventory/lifecycle, explicit fresh inventory, prepared cached
reads, frozen confirmations and exact-reference action revalidation.

Tmux profile expiry makes positive attachment counts unavailable to selectors;
historical names may remain visible. `Open` remains a desktop join and `Attached`
a current native fact. Neither grants provider or close authority. Source errors
and unsupported desktop support remain independent.

## Agent Observer and deferred Agent Plus

Agent Observer is actively developed. Its current producer contract and
`observation-boundaries.md` are the semantic baseline; old Agent Plus behavior
cannot impose backward classifiers, provider topology or retention policy.
Freeze an explicit API/schema/service tuple for each adapter review and recheck
it before implementation. The design's source manifest makes drift detectable.

Do not rewrite API 2 snapshot 4 in place to accept aggregate hosts. It has one
top-level host, closed field/state validation and strict host-scoped sources.
The new profile needs its own public descriptor and pure parser, or an explicitly
versioned successor agreed by the producer. Session identity/state records can
remain unchanged. Existing local CLI/service users continue to use API 2 until
they opt into that successor.

The Mesh bridge reads the configured local service with `service_client.frames`
or an independently equivalent implementation. For inventory it uses snapshot
or unfiltered service frames, preserving confirmed children in the canonical
view. Default CLI watch filtering is not a complete producer inventory.

Each provider/namespace gets distinct runtime/history receipts. An Agent source
may have partial Claude coverage with valid positive row facts. Successful
networking does not upgrade that coverage. At source expiry, use existing pure
uncertainty semantics; do not perform a PID census or provider query in Mesh.
Until a public field-to-component dependency map exists, invalidate all current
claims for the affected provider at its earliest active component expiry.
Other providers retain independently current evidence.

The current unsaved-runtime retention deadline is owned by the producer and
not fully encoded as a per-row receipt. Mesh must not invent a new sliding
retention window. The initial projection removes unsaved historical rows when
their source loses current authority, retaining saved metadata as historical.
This is a conservative presentation restriction, not a native ended event.
Exact producer retention parity would require a separately reviewed public
retention receipt; it is not assumed here.

The owner-side bridge can prove cached service-2 validity without a nonce change
to Agent's service. It reads after receiving the bridge nonce and computes
remaining validity from original component expiry on the same host/time domain.
Owner and bridge incarnation/scope checks are still mandatory. No subscriber
refresh, native hint installation or provider restart is introduced.

Agent Plus may later adopt the new pure profile facade and shared Mesh transport
directly, rebuilding its obsolete cache in one explicit migration. It should
not first port its old networking/classifiers as an interim authority. Parser,
cache, UI, writes and terminal entry are independently accepted checkpoints.
The selected writer may differ from the selected reader; read delivery cannot
authorize changing that selection.

## Client compatibility acceptance

For each profile, the same validation/selection function must accept a one-host
local view and a multiple-host view. Tests compare reconstruction with the
original producer fixtures, preserving row values and order. Native samples
from different times need not match byte-for-byte; synthetic projection should.

Unknown Mesh diagnostic codes remain tolerated, while known state enums and
contract versions stay strict. Unsupported domain versions produce per-host
incompatibility. Provider failures, unavailable hosts, complete-empty owners,
warming services, expired receipts and namespace collisions each need independent
examples. Current and historical selection must use the pure effective facade,
not raw row values.
