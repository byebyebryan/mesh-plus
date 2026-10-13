# Mesh Plus state contract freeze

The state delivery boundary is frozen for independent implementation against
`contracts/LOCK.json`. It supports cached polling and pushed state over local IPC
and persistent SSH stdio, with optional native WSS as defined by the
[WSS addendum](../contracts/wss-v1/contract.md). This is an experimental implementation freeze, not a
published Observer API, selected desktop artifact or operational fleet release.

## Authority and compatibility

The normative inputs are this freeze, the [Read contract](../contracts/mesh-read-v1/contract.md),
the [Delivery contract](../contracts/mesh-delivery-v1/contract.md), and the schemas
listed in the lock. The freeze restricts otherwise reserved features in those
documents. Architecture, studies and historical sketches supply context; they
do not expand the accepted capability set. Schema validity is necessary but
does not replace the semantic lifecycle, domain and receipt checks.

The fixed identifiers remain `meshProtocol: 1`, delivery
`mesh-plus.delivery-candidate.v1` / version 1, and domain profiles
`tmux-observer.mesh-candidate.v1` and `agent-observer.mesh-candidate.v1`.
Local and fleet reads use identical envelopes and pure domain validation.
Existing published Observer clients continue using their existing interfaces
until explicitly migrated. No parser discovers support merely from extra fields.

Outer objects are closed unless a listed schema explicitly permits extensions.
Diagnostic extensions remain bounded and grant no authority or new validity.
Changes to required fields, types, interpretation, authority or guarantees need
a reviewed lock revision and, when incompatible, a new negotiated protocol or
profile. Workers must not independently rewrite the lock or regenerate its
digests to approve their own changes. Compatible implementation fixes need no
wire rename. A producer schema change requires a separate profile review.

## Boundaries that workers can implement

| Boundary | Input | Output and responsibility |
| --- | --- | --- |
| Fleet read SDK | Read 1 request, resolved immutable endpoints | `Reader.execute(request)` async iterator: one snapshot or replacement watch frames, at most one terminal base error |
| Reader endpoint | `Endpoint(host, local, route_token, connect)` | Owned connected `Client` with a profile-bound pure codec; Reader controls lifetime and closes it |
| Delivery client | Validated Channel, host/source/profile and required capabilities | `Client.connect`, `request`, `subscribe`, `Subscription.close`, `Client.close`; independently ordered directional frames |
| Channel carrier | Already authorized local address or configured route | `send(frame)`, `receive() -> (frame, encoded_bytes)`, `close()`; bounded framing and owned resource cleanup |
| Host publisher bridge | Fixed configured cached source and domain adapter | State `snapshot`, nonce-bound `proof`, and `subscribe`; no arbitrary executable, path or host selected from payload data |
| Pure consumer | Profile, request ID, optional expected ordered host IDs | `ReadGuard.accept(frame)` and `current(now_ms, clock)`; validated replacement state and conservative current rows |
| Catalog authority | Host Mesh v1 config/revision and route outcomes | Existing catalog, immutable route binding tokens and revision-checked health updates; no provider facts or picker history |

`selection.mode` is `local`, `fleet` or `hosts`; `hostIds` is empty for local/fleet
and nonempty, ordered and unique for hosts. Resolve admission before dispatch.
A snapshot failure is a host outcome whenever scope remains valid, preserving
healthy siblings. Invalid request/profile/scope admission uses the bounded base
error envelope, preserving a valid request ID. CLI options select configured
reads; the CLI is not a new stdin fleet wire server.

The supported product is `state`; the advertised adapter capabilities are
exactly `snapshot`, `proof`, `subscribe`. A requested unavailable capability is
a setup rejection, with no implicit downgrade to polling. A well-formed hello
rejected before channel establishment receives the nonce-bound `setup-error`
frame. Malformed input may close without a reply. Established-channel errors
remain distinct from setup errors and per-host fleet outcomes.

The current native inputs are Tmux observation/service v1 and Agent API v2,
snapshot v4, service v2. Source commits and schema hashes are recorded in the
lock. Native records, source identities, partial/unknown states and original
receipts stay attributable to their producer. Configured Observer source
selectors use `[a-z][a-z0-9_]{0,127}`; these are not Agent provider/namespace
receipt IDs. A transport/backend worker cannot normalize native semantics.

## Polling and pushed state

Polling and subscription both traverse Mesh. A pushed candidate is notification
of changed cached state; a fresh checked native reply and nonce proof establish
remote positive validity. One proof at a time per Reader-owned host channel is
the Reader policy, not a limit on generic Delivery multiplexing. Polling a cache,
heartbeats and subscription credit never renew source evidence.

Reader sequences and material revisions are scoped to reader incarnation plus
request ID. Concurrent reads cannot consume a watch sequence. Delivery channel
sequence, subscription sequence, adapter wrapper sequence, native owner sequence
and source incarnation have separate scopes. Adapter sequences may skip for an
individual client. Full views replace the previous view; a gap or source/channel
recovery requires resync before positives can resume.

Cancellation and terminal races are directional. The server may accept a valid
cancel or cumulative credit already in flight for a known ended handle, without
reopening it or sending a second terminal. Unknown handles, regressive credit,
invalid windows and post-terminal data remain protocol failures. A finite stream
can drain previously queued data after `ended`; no additional credit is issued.
Closing a subscription wakes blocked consumers and preserves independent work.

The bridge emits idle subscription heartbeats within five seconds and ends a
subscriber blocked on data credit after fifteen seconds. Controls have their own
bounded queue ceiling and cannot renew data credit or source leases. Coalescing
emits a delivery gap. The Reader emits replacement views and correlated terminal
errors; aggregate heartbeat/gap controls are supported by the consumer contract
but are not required emissions of this Reader implementation.

## Lifetime and resource rules

Absolute BOOTTIME deadlines include admission queue, setup, write and validation.
At most four host setups run concurrently per Reader, including simultaneous
requests. Snapshot acquisition and each watch setup have a fifteen second
budget; each remote proof has a two second budget. Cleanup follows cancellation
and may take its bounded owned-resource shutdown time; a deadline is not a
promise that all cleanup completes at that exact millisecond.

Watch endpoints and catalog revision are immutable. A fleet watch requires a
catalog-check callback before it can dispatch. Checks begin at most five seconds
apart when idle and have a five second budget. An observed revision change or
failed check terminates the whole watch, cancels its children, and requires fresh
scope resolution. Route-health changes alone do not change the config revision.
This is bounded observation of authority changes, not instantaneous revocation
or independent physical-machine attestation.

`ReadGuard` owns one validated view. Heartbeats cannot extend its receipt expiry;
gap/error clears its current view. Its transport adapter must call `disconnect()`
on EOF, frame/domain validation failure or transport liveness failure, and create a new guard on
reconnect. A cached object alone cannot detect an external socket failure.

Limits remain sixteen hosts, sixteen MiB aggregate response, sixty-four KiB
common metadata, and the stricter native profile frame limits. Delivery's
ninety-six MiB queue limit and sixty-four KiB control ceiling are per client.
A shared fleet-wide memory pool is not implemented or promised by this freeze.
IPC enforces same-user private endpoints; SSH owns a noninteractive authenticated
stdio process. SSH marks wrapper reachability separately from domain success,
uses the marker's original observation timestamp for route reports, and treats
an observed duplicate nonce marker as invalid. Authentication/host-key policy
failures never justify route demotion or fallback.

## Independent work packages and acceptance

| Work package | Owns | Gate before integration |
| --- | --- | --- |
| Mesh transport and core | Channel, Delivery lifecycle, deadlines, queues, authenticated route setup | Core tests, delivery oracle, schema/lock parity, cancellation and malformed-peer cases; no domain reinterpretation |
| Tmux producer adapter and desktop coordinator | Cached native service adapter and existing coordinator's Mesh binding | Frozen Tmux schema parity, native owned publisher checks, receipt/expiry and action-authority separation; paired artifact and UI acceptance remain separate |
| Agent producer adapter | Current pure API/service codec and cached state delivery | API 2 / wire 4 / service 2 fixture parity, partial/provider expiry and native-service acceptance; provider collection remains producer-owned |
| Consumer facade and UI | `ReadGuard` plus domain display projection | Local/fleet same parser, independent request sequencing, resync and disconnect expiry tests; no SSH, custom lease renewal or inferred idle state |
| SSH Plus compatibility | Optional shared authority selection | Existing Host Mesh bundle and config/history behavior, explicit selection/no fallback, legacy standalone and selected Mesh tests |
| Packaging and operations | Reproducible tuple, carrier recovery and resource evidence | Standalone wheel plus native dependency wheels; later scoped live selection/rollback, fleet costs and physical suspend/GUI acceptance |

Mesh core, the two producer adapters and pure consumer work can proceed in
parallel against these boundaries. Tmux coordinator migration is a paired
integration gate. Agent Plus remains deliberately deferred until it adopts the
current producer contract; its older backend is not the Agent profile authority.
SSH Plus already has the optional shared-authority facade; changing its default
or selecting live artifacts belongs to the paired operational gate.

Ordered native events, event replay/status, digest-proof,
shared fleet broker/pool, refresh/actions and command
idempotence are outside this freeze. Their schemas and synthetic studies are
reserved design material, not advertised production capability. Teams may
research them independently, but need producer and transport acceptance before
adding them to the supported lock.

## Reproduce the acceptance gates

Run `scripts/check-contract-lock.py`, the Read and Delivery design checkers,
`scripts/check-runtime.py --core-only`, and lint without Observer dependencies.
Run the full runtime suite separately with the exact producer dependencies.
The checked-in evidence records source/wheel inputs and exclusions. A passing
oracle, editable source, built wheel, CI and selected live artifact are separate
forms of evidence; only the first four are part of this review pass.

## Reviewed Agent timing extension

The [Agent v2 addendum](../contracts/agent-profile-v2/contract.md) permits an
explicit successor profile with native wire 5/Service 3 through SDK 1. Lock
revision 3 preserves every preceding schema and native-input byte. Existing
Agent v1/Tmux v1 defaults and transport contracts remain frozen; only an explicit
v2 owner profile selects the new packaged schema. Its independent acceptance
does not select a deployment.
