# Projected active profile and supported Mesh seams

The opt-in `agent-observer.mesh-active.v1` profile binds native
`agent-observer.active-feed` version 1. It uses SDK 1, preparation/admission 1,
Mesh Read 1, Delivery 1 and lock 5. Source/private package a23 is distinct from
the accepted a22 full-feed tuple and later deployment selections.

The [normative addendum](../contracts/agent-active-v1/contract.md), profile schema
and vendored native input are explicit new lock entries. Previous schemas and
their 29 normative digests are retained. The native source pin is
`4ffd376441fcb556cbe291d55d983e0814c20551`; that pins schemas, not Observer runtime
or its future wheel. `scripts/check-contract-lock.py` checks 33 locked inputs and
25 identical packaged schemas, including exact selected-body equivalence to v3.

## Profile and factory binding

`descriptor("agent", profile_id="agent-observer.mesh-active.v1")` returns SDK 1,
native protocol/version above, Agent frame cap 8,404,992 bytes, and the SHA-256 of
the packaged `read-agent-active.profile.schema.json`. Native frame schema hash
and fixed canonical selector digest are also bound into that schema. Runtime
admission validates the complete projected native DTO and its exact round trip;
generic Mesh independently validates envelopes, receipts, proofs and ownership.

The pure implementation belongs to Observer's `mesh_active_profile` module.
Existing `AgentProfile()` continues selecting full v3. A caller must explicitly
construct `ActiveAgentProfile()` and use it consistently for endpoints, Reader,
codec, preparation and facade. Old parsers and default resolution do not discover
support through extra fields. An unsupported selector/profile/native request
fails explicitly; there is no automatic full-feed acquisition fallback.

The trusted factory signature remains `(host, source, native_socket) -> adapter`.
Observer's `make_publisher(..., *, profile_id=FULL_PROFILE_ID)` retains its full
three-argument default. An owned active-only launcher can pass
`functools.partial(make_publisher, profile_id="agent-observer.mesh-active.v1")`
as the Agent entry in `mesh_plus.cli.main(publisher_factories=...)`. A shared
launcher instead explicitly maps trusted configured source IDs to full/active
profiles inside its installed Agent dispatcher. Mesh does not guess source names,
add profile fields to the existing source config or select a callable from wire
data. The independently owned Tmux factory remains separate.

Adapters must exactly bind configured host/source/profile and advertise only the
existing snapshot/proof/subscribe capabilities. The active route uses complete
projected replacements and full nonce-bound replies. Source `snapshot()` performs
a fresh cached projected endpoint read after nonce admission. No native provider
collection occurs per reader/proof. Reserved digest-proof and identity-query
syntax are not promoted.

## Public prepared authority

Selected unchanged API 4 bodies are generic records; owner metadata carries
typed scope coverage, member support, uncertainty and positive nonmember facts.
Owner service metadata carries the new native header. It contains no hidden
full snapshot. Restore owner plus records to recover the entire projected DTO.

Observer's `PreparedActiveAgentWatch` owns one public `snapshot()` export per
accepted replacement. Each `read(now_ms, reader_clock)` calls public
`current(now_ms, reader_clock)` first and then `context()`. It validates exact
original sample/support binding, current/partial translated host receipts,
expiry, ready delivery, selector, native/source context and scope continuity.
It masks fields independently; whole-row expiry is not a retirement decision.
Exported headers/bodies are detached. There is no private guard access or new
generic expiry API.

A zero-body complete scope expires when its own original dependencies expire.
Raw headers and successful delivery alone grant no completeness. Partial/unknown
omissions, pruning, expiry and overflow do not become parked or removal facts.
Current complete scope or exact positive decisions reconcile whole identity sets
before display limits. Existing uncertain presentation context may survive
partial reconnect and missed expired negatives; this profile adds no query or
timeout policy. Original clocks, evidence TTL and activity ages never renew from
encoding, cache/proof reads, heartbeat or reconnect. The existing 32-receipt cap
applies; no historical receipt bank is added.

## Catalog selection

The existing opt-in API is `LibraryMeshAuthority()` with
`configured_reader(..., authority=authority, report_routes=False)`. The caller
owns `authority.close()`. It uses the imported package's canonical parsers and
fresh full loads for every check. Process authority remains the default and
route-report writer; config revision and route health remain separate. Reads
can create/chmod canonical health locks/directories; they do not write config,
health or picker-history content. Four-MiB regular-source limits are explicit
library policy, not new Host Mesh wire limits.

`scripts/qualify-library-authority.py` independently compares the actual selected
process facade under disposable XDG inputs, including missing/invalid/recovery,
health-only change and same-size/same-mtime replacement. Configured-watch tests
prove terminal invalidation and cleanup without route reporting. Check starts
retain the existing five-second idle cadence and five-second read budget; this
does not promise unconditional five-second end-to-end detection under a stall.

## Independent verification and adoption

`scripts/qualify-active-owner.py` qualifies actual installed Observer ServiceState,
collect-disabled Runtime, active cached source, codec/profile and pure facade
through owned IPC and fixed localhost SSH. It verifies member/complete-empty,
original expiry, shared projection generations, full defaults and cleanup with
zero provider workers. A development flag explicitly distinguishes source screens.

`scripts/measure-active-transport.py` compares full/active owned IPC watches with
actual pure producer facades at fixed active membership and 100/500/2,000 parked
rows. It records selected-body parity, all transport bytes, total publisher/
Reader/facade CPU, latency and cleanup. Fixture/projection/collector/service work
is excluded and must be qualified separately. Instrumented allocation samples
are separate from CPU timing; RSS includes setup and is labeled accordingly.

Independent exact-wheel, source, native, performance and operational evidence
remain distinct. Later adoption must coordinate Observer collector/service,
publisher/read, Mesh and consumer selections and retain paired rollback/full
diagnostics. No source refactor or private wheel selects those roles.
