# Mesh SDK interface v1

SDK 1 is the supported pure networking interface, independently versioned from
package releases, native profiles and Read/Delivery wire 1. Current full Agent
clients select explicit Agent v3 (snapshot 6 / Service 4); working-set uses its
own profile. Legacy default Agent v1 and explicit timing v2 remain different
bindings, not automatic negotiation. See [handoff](handoff.md).

The frozen [lock](../contracts/LOCK.json) and profile contracts define exact
native bindings. Standalone Agent active-only support is withdrawn despite
retained historical schema inputs. Optional preparation, owned admission and
selected reads are additive interfaces; see [prepared consumers](prepared-consumer-api.md)
and [owned admission](cpu-admission-api.md).

Import supported networking entry points from `mesh_plus.api`. Its
`SDK_INTERFACE_VERSION = 1` is independent of Mesh wire 1, profile v1, and native
Tmux observation/service 1 or Agent snapshot 4/service 2. Existing module imports,
domain-string constructors, CLI and reference adapter names remain supported.

The a14 source/private-wheel candidate adds a separate optional
[`mesh_plus.wss.configured_reader`](wss.md) factory under the
[WSS addendum](../contracts/wss-v1/contract.md). It accepts the same pure profile
and returns a Reader with unchanged Read/Delivery semantics. Existing API exports,
signatures and defaults remain SDK v1. WSS adoption is an explicit networking
selection, independent of producer collection or desktop/client behavior.

The a15 release adds the [Observer-owned publisher helper and trusted CLI
factory seam](publisher-api.md). These are additive SDK v1 exports; existing
exports/signatures, source descriptors and remote command stay unchanged.

## Pure profile interface

The exact structural signatures and immutable DTO constructors are in
[`state.py`](../src/mesh_plus/state.py). `StateProfile` exposes `descriptor`,
`bind(host, source)`, `validate_response(response)`,
`restore_native(owner, records)`, `record_host(record)`,
`record_identity(record)`, `record_receipts(record, state)` and
`record_eligible(record, state)`. `BoundStateCodec` exposes `host`, `source`,
`profile_id`, `validate_bridge(payload)` and `inspect_native(frame)`.
Implementations need no inheritance or bound-method validators.

`ProfileDescriptor(sdk_version, profile_id, native_protocol, native_version,
contract_digest, frame_bytes)` must equal `descriptor("tmux")` or
`descriptor("agent")`. The digest binds the packaged profile schema; all native
dependencies remain bound by the existing contract lock. Frame limits are the
reviewed native ceilings, 1,064,960 and 8,404,992 bytes respectively. No plugin
discovery, arbitrary new profile registration or remote code selection occurs.

`NativeState(owner, records, clock, publisher, emitted_ms, receipts)` is a
lossless local projection. `owner` retains protocol/version/metadata/service;
records retain their order and complete identities. Receipts retain opaque
`sourceId`, `component`, `accepted`, `health`, `expiry` facts. Warming/nonpositive
receipts can have no expiry. These DTOs do not add transmitted fields, deeply
freeze nested JSON, or certify domain semantics by themselves.

Profile code is trusted installed pure code. It must validate native payloads,
preserve reconstruction exactly and avoid collection, filesystem/network I/O,
actions and desktop policy. `record_identity` returns a nonempty tuple of string
or integer components. `record_receipts` returns a nonempty frozen set of
`(sourceId, component)` pairs, or `None` when evidence is insufficient. An empty
set grants nothing. `record_eligible` supplies native eligibility only.

Mesh always checks packaged schemas, JSON and byte limits, host/source/profile
binding, scope/order/identity uniqueness, lossless projection, proof nonce and
digest, clock chronology, original receipt attribution, health and lease bounds.
Domain callbacks cannot waive those checks. Effective rows additionally require
ready delivery and every required receipt current/partial and unexpired. Gap,
EOF/disconnect, terminal and incarnation barriers remain compulsory. Retaining
raw records never retains positive authority.

## Binding poll and push

```python
from mesh_plus.api import configured_reader, ReadGuard

reader = await configured_reader(
    "agent", source="agent", socket=owned_socket,
    scope="fleet", authority=selected_authority, profile=reviewed_profile,
)
response = await reader.snapshot()
guard = ReadGuard("agent", request_id, profile=reviewed_profile)
stream = reader.watch(request_id=request_id)
try:
    async for frame in stream:
        guard.accept(frame)
finally:
    guard.disconnect()
    await stream.aclose()
```

Use that same explicit `profile=` with `validate_response`, `current_sessions`
and `reconstructed`. The configured path binds once per endpoint, threads the
codec through IPC and SSH factories, and checks hello binding before native
requests/subscriptions. Catalog revision monitoring and route reporting retain
their existing defaults; reporting requires explicit opt-in.

Direct bindings use `Endpoint(host, local, route_token, connect, codec)` and
`Reader(domain, endpoints, local_host=..., profile=profile, ...)`. The factory
connects an owned `Client` using that codec's validator and identical
host/source/profile. Binding must not mutate after resolution. Reader captures
the binding and rejects changes. Reader closes every returned client.

The four-argument legacy `Endpoint` still accepts the reviewed
`ObserverCodec.validate` / `ObserverAdapter.validate` compatibility path. A plain
callback alone supplies Delivery semantics, not a profile; it requires an
explicit endpoint codec for fleet composition. The generic Client stays usable
with ordinary callbacks. Default calls select a lazy `ReferenceProfile`, which
uses only supported pure Observer facades when native data is admitted.

`Bridge` retains the fixed-source publisher surface: `host`, `source`, `profile`,
`capabilities`, `validate(payload)`, async `snapshot(parameters)`,
`proof(parameters)`, and `watch()` yielding `Publication(payload, epoch, barrier)`.
Publishers must produce a checked cached native reply after the proof nonce
arrives, preserve original receipts, and close their owned iterators on
cancellation. Heartbeats or retained watch data cannot renew a lease or replace
that proof. Events/replay, refresh/actions and shared brokers remain deferred. Optional WSS
is separately accepted under its addendum; publisher ownership uses the same
transport-neutral interface.

## Independent gates and compatibility

The canonical core gate includes an external fixture profile with native imports
blocked, covering configured poll/push, route binding, guards and adversarial
proof/receipt/expiry admission. It requires no sibling checkout. Native gates
select pinned Observer wheels and check reference semantics separately.
`--check-sources` remains historical provenance, not the normal development gate.

SSH Plus is the direct authority client. Its aliases/model identity, config,
health writer, history ownership and authority source bytes are unchanged.
The original literal-extraction gate still rejects the reviewed bounded-read
seam. Current acceptance explicitly selects that separately reviewed baseline:

```sh
rtk proxy .venv/bin/python scripts/check-authority-compat.py \
  --ssh-plus /path/to/rofi-ssh-plus --backend mesh-plus --baseline bounded-read-v1
```

That gate checks both exact reviewed authority hashes before running model and
subprocess regressions. Changing either baseline requires review, not a drift
waiver. It does not deploy a new SDK root or write picker history.

Mesh can advance transport under these guarantees independently. Each Observer
can implement its pure profile against this interface and pinned packages without
moving its whole adapter or waiting for the other Observer. Native semantic or
wire changes still require explicit contract review. Plus clients, provider
collection, desktop presentation and live artifact selection remain owner work.
Project docs, scripts and evidence live in the owning repository; chezmoi holds
only deployment configuration that actually needs management.

## Additive opt-in consumer preparation

The [prepared consumer interface 1](prepared-consumer-api.md) is an explicit
local Python extension through SDK 1. Existing export signatures, legacy
mutable-view/later-callback checks, profile defaults and wire bytes stay intact.
PreparedReadGuard admits watch generations once and requires a separately
reviewed StatePreparation promising static rules. Existing profile-only
consumers remain independent; no native facade is automatically opted in.
