# Projected active feed: Mesh G0 proposal

Status: G0 planning agreement closed by RLCD coordinator, 2026-10-16 UTC.
No implementation, normative acceptance, identifier/version allocation, package
installation, publisher selection or rollout is authorized by this document.
Observer's final planning confirmation reports no remaining semantic discrepancy,
including the public prepared seam, exact provenance and existing receipt bound.
RLCD has closed G0 and recorded agreement in its owning plan. Planning agreement
is separate from normative review and runtime acceptance; strict new schemas,
profile addendum/lock review and implementation remain future G1 work requiring
separate authorization. No further G0 implementation or rollout work is opened.

## Inputs and present boundary

This review starts from Mesh runtime `f1ced05` / acceptance `f773154`, private
a22, and the unchanged [state freeze](contract-freeze.md), lock revision 4.
RLCD's owning plan is
`/home/bryan/code/esp32-rlcd/projects/agent-dashboard/docs/active-feed-plan.md`.
Its private counts/scripts are under
`/home/bryan/code/esp32-rlcd/.cache/cpu-investigation/20261016T042557Z/`.

That separate timed reader received 9,798,780 bytes in sixty seconds for 498
current identities and ten selected bodies; composition/admission used 57.45%
of its Python CPU. Visible presentation used 0.22%. The catalog experiment
averaged 44.9715 ms child CPU per call, equivalent to 0.89943% of one core at
five-second intervals. These are diagnostic inputs, not a stable inventory,
causal performance comparison or projected-feed saving.

Full Agent v3 is a lossless projection of the original native frame. Returning
fewer rows with its existing owner metadata would change its meaning. Existing
consumer selection reduces local work after transport; it does not establish a
producer-side projection protocol. Full-feed Agent and Tmux remain independent.

## Proposed first interface

Choose one separately configured projected source and one separately reviewed
Agent projected profile for the first pass. A proposed source label such as
`agent_active` is illustrative, not reserved. Do not add arbitrary predicates,
module names, executable arguments or user expressions to wire requests.

The first selector is fixed installed policy: provider Codex; kind user/unknown;
runtime value running with current runtime health. Phase does not determine
membership: waiting/idle, working, blocked and errored loaded threads remain
eligible. Observer owns the exact normalization and meaning of these predicates.
Future selector combinations require explicit negotiation/review; they are not
implicitly supported by this first source.

The selector must have a canonical, versioned descriptor with sorted, deduplicated
sets and an exact digest. The projected DTO carries that descriptor/digest, and
the installed profile validates it against the expected fixed selector. Binding
only a human source label is insufficient. For this fixed first selector, the
existing hello's source/profile binding can negotiate the complete meaning;
no new generic Delivery capability is needed solely to say "projected."

| Seam | Proposed choice | Owner |
| --- | --- | --- |
| Authoritative domain format | New projected native DTO with selected rows, scoped membership authority and original receipt provenance | Observer |
| Projection placement | Observer-owned cached endpoint/source, published before consumer Mesh IPC/SSH | Observer |
| Preparation | Project once per accepted native generation and fixed selector; share an owned immutable result, without native collection per reader | Observer |
| Mesh publisher | Existing `CachedSource.snapshot()/watch()` and `CachedPublisher(..., profile=...)`, extended only for the reviewed projected profile | Mesh / Observer adapter |
| Wire delivery | Complete projected replacements and full projected nonce proofs using existing state Delivery | Mesh |
| Consumer authority | Pure Observer projected-read facade, then RLCD presentation; no inference from omitted raw rows | Observer / RLCD |
| Diagnostics/rollback | Explicit retained full source/profile and matched previous tuple | RLCD / owner operations |

Observer core/local-service code stays free of Mesh imports. Its projected
endpoint may introduce a reviewed native request/DTO contract. Mesh imports only
the supported pure codec/source facade. A sidecar that downloads and filters
the full native roster for every subscriber or nonce does not meet the cache
placement goal. The preferred endpoint answers a new cached projected read
after nonce admission, without another full-roster serialization or collection.
Projection and underlying full-native validation costs still belong in producer
measurements; caching must not hide them.

Observer proposes an explicit projected request on the protected local service
socket, alongside unchanged Service 4 requests. The review names
`agent-observer.active-feed` version 1 / `activeFeedProtocol: 1` and Mesh profile
`agent-observer.mesh-active.v1` are suitable distinct bindings, not allocated
identifiers. An older service must report unsupported capability within bounds;
it cannot answer with a filtered Service 4 frame or silently switch routes.

The new Mesh profile restores the complete **projected DTO**, not the omitted
original native inventory. Selected row meanings and their original activity,
source clocks, runtime/phase/error/retry facts remain unchanged. Do not embed a
full original snapshot in metadata or an extension as a shortcut to validation.
If the projected cache has a separate lifetime, it must expose original native
incarnation and observed source loss as well as its own incarnation. A live cache
process cannot conceal a disconnected/lost native owner or renew its retained
positives. Prefer an owner-hosted endpoint that avoids introducing this extra
continuity boundary; Observer must specify the exact liveness behavior.

## Membership is a producer contract, not a Mesh filter

Use complete replacement snapshots, without deltas/replay in the first pass.
"Replacement" describes the transmitted projected state; it does not by itself
assert complete knowledge of active membership.

Observer must define per-host/provider/namespace coverage for the selector, with
an attributable original receipt dependency for each positive, negative and
completeness claim. Complete-empty is distinct from partial, warming, stale,
unknown and unavailable. Delivery `ready` / aggregate `complete` do not supply
domain membership completeness.

Mesh can enforce this boundary:

1. Only an unexpired, producer-proved complete membership statement may make
   absence retire previously selected rows for that exact covered scope.
2. On partial/unknown coverage, an omitted prior row cannot become parked or an
   authoritative exclusion. Observer/RLCD retain bounded uncertain context;
   no previous positive outlives its original dependencies. Expiry of that
   positive does not itself delete previously retained presentation context.
3. Positively parked or newly confirmed excluded-kind identities may need compact
   explicit retirement facts when other rows in the scope are uncertain. Those
   facts need the full five-part identity, incarnation/order and original receipt
   dependencies. Loaded-list absence alone is insufficient evidence.
4. Never send all dormant identities just to preserve current summary behavior.
   Neither an ever-growing ever-active set nor a display-prefix-only negative
   list satisfies the scaling/completeness requirement.

Three lifetimes must be specified separately:

| Lifetime | What expiry means | What it does not prove |
| --- | --- | --- |
| Positive native row facts | Revoke current/running/phase claims dependent on those receipts | Parked, excluded or safe deletion of prior display context |
| Negative/completeness evidence | No longer usable as fresh authority for a new reconciliation decision | A previously valid retirement reverses, or missing replacement facts are negative |
| Presentation context | Existing uncertain-context retention, or a separately agreed bounded eviction policy | Native parked membership or complete-empty coverage |

Current RLCD retains prior rows as uncertain context after their positive lease
expires. Preserve that behavior until an explicit product policy changes it.
Administrative eviction/expiration of bookkeeping can discard context only under
that declared policy; it must not manufacture a parked fact or a complete active
inventory. No new context timeout or display-prefix cap is selected here.

During partial coverage, either retain uncertain context without exact retirement
or supply current exact-identity retirement evidence. Bounded, expiring facts in
every replacement need a retention horizon and overflow/gap policy, but their
expiry cannot guarantee a disconnected consumer ever received them. After partial
reconnect or a missed/aged-out retirement fact, absence still means unknown.
A fresh proved complete selected baseline can reconcile all prior identities for
that covered scope. Without such authority, retain uncertainty; a current exact
decision in the agreed feed may also resolve that identity. Never silently clear
on lease or tombstone expiry. This applies before any USB32/display limit.

RLCD explicitly accepts unresolved context after partial reconnect or missed,
expired negatives. The first feed does not promise exact eventual retirement
through arbitrary partial outages. A bounded prior-identity reconciliation query
and a new presentation timeout are deferred: neither is a G0 blocker,
prerequisite or approved capability. Do not introduce unbounded tombstones,
implicit deltas/replay or a hidden context-retirement timer.

### Census, provenance and bounded continuity

Retain Observer's current `daemon_threads` completeness predicate: both loaded
and saved censuses complete, no unresolved runtime status and successful bounded
processing. Do not upgrade loaded-only evidence. Complete scope authority also
requires a decidable selected/nonselected result for every identity in that
exact census, with original support for every classification used. Missing kind
support, retained rows, source/read limits or a dropped selected entry make the
scope partial. The internal census identity set is not an inactive wire roster.

Observer's chosen G0 seam is transient engine support captured when a component
accepts its actual sample. Each support reference binds service incarnation,
provider/namespace, source context generation, component, accepted counter,
sample and original expiry. Reconciliation copies the support of the value it
actually chose: runtime kind, or history kind only for the existing fallback.
Capture runtime, kind, positive saved identity, activity and outcome separately;
activity/outcome copy their actual chosen support rather than a union of only
components still live at publication. Runtime/phase keep original runtime
support, workspace original history support, and explicit timing bindings stay
exact. Missing or stale producing support makes the value last-known; title or
identity context grants no freshness.
Known kind without valid support is uncertainty. Explicit unknown remains a
selected kind without asserting user/child/system classification. A parked
negative requires the runtime sample's own positive parked and saved-identity
support, not a saved flag merged from old history. API 4 row bytes stay unchanged.

Complete-scope dependencies are the original runtime census receipt plus the
union of exact kind/saved-identity supports used to classify the census. In the
current two-component source model this is at most runtime and history per
source. The codec must verify exact original references before reducing them to
generic receipt keys. A retained decision whose accepted/sample/expiry/context
no longer equals the current component support is context-only. Never rebind an
old decision to a newer receipt under the same `(sourceId, component)` key.
A genuinely fresh sample may establish a new decision with its own support.

Use Observer's proposed selector-wide recent-member ledger, partitioning
continuity by provider/namespace. The proposed hard ceilings are 4,096 tracked
identities and 1 MiB for the canonical UTF-8 JSON encoding of the whole ledger,
including active, uncertain and nonmember metadata, support references,
watermarks and punctuation. Selected full bodies count separately against the
whole native frame. Untouched dormant history consumes no ledger entries.
These are planning ceilings; G1 must prove exact serialized and resident-memory
accounting, including pinned slow-reader generations. Preserve existing native,
envelope, aggregate and receipt limits; no limit increase is assumed.

Last-positive retention horizons use original positive deadlines. Unknown,
negative, encoding, projection revision and reconnect cannot slide them.
Negative facts have their own support leases; an expired ordering watermark
does not remain current negative authority. Pruning after the old positive
horizon grants no retirement authority. On overflow, fail the affected scope
with `projection_tracking_capacity`, revoke its authority/continuity, and require
a fresh proved baseline after recovery. Do not evict healthy sibling entries
to pretend completeness. Reserve bounded scope-failure metadata outside ledger
space, bind per-scope continuity to incarnation and selector, and change only
the failed/reset scope's token. Recovery invokes no provider/session actions.

The frozen bridge `remaining` and Mesh host `receipts` arrays allow at most 32
entries per host. Ledger capacity is not permission to allocate a historical
receipt per identity. Exact-match-or-context-only provenance avoids such a
receipt bank. More configured source components than the existing map permits
must fail explicitly or receive separate normative capacity review; do not
truncate original dependencies or claim every ledger fits solely by row count.

## Exact binding and proof ownership

The reviewed profile must validate the following combined context, using the
existing fields where possible and projected-domain metadata where necessary:

| Binding | Required check |
| --- | --- |
| Authority/transport | Catalog revision, ordered selected hosts, authenticated route/host and configured source |
| Projection | Profile ID/schema digest, canonical selector version/digest, and exact expected provider scope |
| Producer | Native producer incarnation, projection incarnation if separate, source clock and accepted generation/order |
| Payload | Digest of the complete projected native DTO, including selector, coverage, retirement facts and original receipts |
| Request | Reader/request incarnation, outstanding handle/channel epoch, unpredictable nonce, queue-to-completion deadline |
| Validity | Exact original component counters/health/expiry; row and membership/completeness dependencies independently enforced |

The projection must declare its complete required receipt map. It may exclude
providers outside the explicit selector only through the reviewed domain
contract; it cannot silently reinterpret missing components as healthy. Namespace
disappearance is not complete-empty without producer evidence.

Choose Observer's latest metadata representation: `NativeState.records`
contains only selected unchanged API 4 bodies. Typed coverage, member support,
uncertain and nonmember decisions live in projected owner metadata. The profile
losslessly reconstructs the projected DTO for native validation and digest
admission. Do not expose scope records as Agent sessions. This supersedes Mesh's
intermediate typed-generic-record preference; no new generic expiry API is needed.

The supported public seam is `PreparedReadGuard.current(now_ms, clock)` FIRST,
then `context()`. The first call validates the reader clock/generation and
revokes it on mismatch; a missing/retired generation grants no authority. The
detached context header contains admitted owner metadata and translated host
receipts. On every query, Observer's pure facade requires exact admitted original
support plus matching receipt keys/accepted counters, current/partial health,
`expiresAtMs > now_ms`, ready delivery, and matching owner/source incarnation,
selector, scope and continuity. All dependencies must pass; their minimum
translated expiry is the claim's deadline. Never subtract remote absolute clocks.

A complete-empty scope can therefore be current even when `current()` returns
no bodies, and expires independently when its required receipt expires. Raw
`context()` alone grants no completeness authority. Native exact sample/expiry/
context matching belongs to strict codec admission against the original receipt
map; query-time authority uses those bound facts and Mesh's translated leases.
Selected-body expiry does not validate negative/completeness metadata. An
unrelated healthy component cannot extend a membership claim. For retained body
context the domain facade preserves independent field expiry; conservative
generic whole-body eligibility is not identity-retirement authority. Keep the
existing full-feed facade and all-roster summary meanings intact.

On each accepted replacement, the facade also calls public `snapshot()` once
to own the admitted selected bodies and their bound support as immutable
context. It uses no private guard state and returns detached exports. At each
query it masks fields against their original support, even if generic `current()`
conservatively rejects a whole row because one dependency expired. Valid
runtime/kind can still establish membership while activity/workspace is
last-known. Gap, disconnect, clock mismatch and changed incarnation revoke
this cache's authority; RLCD's separate presentation context may remain uncertain.

On proof, the host-local publisher calls a fresh projected cached read **after**
admitting the nonce. A retained watch object alone is insufficient. Remote expiry
retains whole-request RTT subtraction, the existing safety margin and two-second
proof deadline; absolute remote clock values are never subtracted from the reader
clock. Cache reads, encoding times, heartbeats and transport reconnect cannot
renew original receipts or activity ages.

Gap, coalescing, publisher restart, clock change, disconnect and catalog failure
revoke affected authority. Reconnect requires a fresh proved replacement baseline;
late old-epoch proofs cannot repair a new request. Partial domain scopes preserve
healthy siblings. Apply domain retirement before USB32/display truncation.

## Compatibility and normative review

Prefer retaining SDK 1, state product, Mesh Read 1, Delivery 1 and the full
bridge-reply shape if the new DTO fits their generic contract. The concrete
native protocol/profile identifiers and package versions are not allocated here.
New projected semantics require explicit Observer contract review and a Mesh
profile addendum/new lock checkpoint; never rewrite existing Agent v3, native
schemas, lock digests or accepted package bytes to make tests pass.

The minimal later normative addition is a separate projected profile contract/
schema and frozen projected native schema reference, with exact source commit
and schema hashes in a new profile-extension lock checkpoint. Bind the profile
descriptor's SDK 1, native protocol/version, profile-schema digest and frame cap;
the profile schema binds the exact projected-native contract digest and fixed
selector/version. Keep existing profile entries, defaults and schema bytes.
Review and package new schema bytes explicitly rather than regenerating the
current lock to legitimize runtime changes. Existing hello source/profile plus
snapshot/proof/subscribe suffice; no generic projection or digest-proof capability
is part of this first pass. A change that cannot fit these limits returns to
normative review rather than implicitly expanding SDK/Read/Delivery 1.

Current implementation allowlists in `state.descriptor()` and
`cli.configured_adapter()` must eventually admit the reviewed profile. The
trusted Agent factory can dispatch fixed full/projected sources while retaining
the existing private source descriptor shape and fixed SSH command. It must
reject unsupported source/profile/selector combinations before acquisition.
No silent full-roster fallback, profile downgrade or subscription-to-poll fallback
is proposed. Tmux factory/profile/source bytes and operational selections remain
outside this lane.

## Existing digest-proof: reserve, then assess separately

Lock 4 and the state freeze explicitly exclude `digest-proof`. The packaged
schema and generic Lifecycle's `knownDigest` capability check are reserved syntax.
The synthetic oracle's `sequence`/`encodedAt` exclusions are not native policy.
Current `CachedPublisher` advertises only snapshot/proof/subscribe, accepts only
nonce proof parameters, and produces full replies. The installed factory rejects
additional capabilities. Reader/bridge admission expects a full owner frame.
There is no accepted end-to-end native compact-proof path to turn on.

Use full **projected** proof replies first. Reconsider the reserved extension only
after measuring their size/cost and semantic hit rate. Original receipt/counter
changes can require a new full reply even when all selected row bodies are equal.
The diagnostic 14/16 equal host-row comparisons do not prove compact-proof hits.

Any later compact path needs an explicit native equivalence facade: after a fresh
cached read it proves identical selector, scope, owner incarnation, domain facts,
coverage/errors/retirements and complete original receipt map. Only explicitly
reviewed delivery-only fields may differ. Its nonce proof references the exact
already-admitted full projected digest. Miss/change returns a full **projected**
proof or failure; it never falls back to the unprojected inventory. Publisher loss,
unknown digest, expiry, mismatch and reconnect cannot renew the retained copy.
This requires normative promotion, strict Client/Reader variants, bounded owned
retention and independent installed native/transport/performance qualification.
It saves bytes, not the round trip or original-evidence checks.

## Separate catalog-cost lane

First qualify the existing explicit `library_authority.LibraryMeshAuthority`
with `configured_reader(..., authority=authority, report_routes=False)` and owned
`close()`. Current RLCD explicitly uses `SSHPlusAuthority()` with route reporting
disabled. The library adapter uses canonical config/route-health parsers and
encoder, admits one bounded filesystem job, and has cancellation/lock/capacity
and path-replacement tests. It can remove process startup without introducing a
new persistent authority service or changing `authority.py`.

This is an explicit authority selection, not an automatic substitution for any
configured executable. First establish compatibility with the actual selected
SSH Plus/Host Mesh facade, installed authority bytes, environment and canonical
config/health paths. Keep the process default and route-report writer unchanged;
the proposed RLCD lane does not call the library adapter's inherited writer.
Config revision, route-health observations and picker/history ownership remain
distinct. Canonical lock/permission behavior also needs parity; do not call the
library reader "no filesystem effects" merely because it does not report routes.
Its explicit four-MiB config/health input caps and regular-file restrictions are
adapter policy, not new Host Mesh wire limits; installed selection must verify
and accept those constraints rather than assuming an arbitrary CLI is identical.

Keep the existing full `load()` on each authority check initially. Do not add a
revision-only/stat-mtime cache that can hide invalid config, disappearance or
same-metadata replacement. Health-only changes do not alter config revision.
Change or load failure still terminates the whole fleet watch without fallback.

The exact frozen timing promise is check starts at most five seconds apart when
idle, with a five-second check budget. It is not an unconditional five-second
end-to-end failure bound under a stalled read. Preserve that contract and measure
change/timeout cases; if G0 intends a stricter absolute bound, settle it explicitly.

Compare process facade versus library using identical disposable config/health
inputs, then independently installed reader fixtures. Measure parent+reaped child
and library-thread CPU, total wall latency, memory, check count, failure latency,
cleanup and zero route/history content writes. The 0.90-point command cost is a
target to investigate, not a saving estimate. If library selection cannot retain
the selected authority's semantics, only then propose an owner-reviewed persistent
authority interface with bounded liveness and fresh checks; do not quietly skip
checks or relax cadence. This lane need not block projected-feed G0.

## Required acceptance before implementation/adoption

Mesh's G0 position now chooses the fixed first selector, ServiceState-hosted pure
cache, separate opt-in native/profile route, full replacements and projected
proofs, metadata authority through the public prepared seam, mandatory transient
kind/census support, bounded per-scope continuity and the existing authority
timing promise. RLCD's unresolved-context decision is accepted above. Observer
has confirmed these planning choices, including public snapshot ownership and
ordered clock/context checks. This document does not claim a jointly frozen
DTO, normative acceptance or G1 authorization.
Exact new schemas/addenda and strict fixtures must retain all these bindings;
they cannot silently weaken the G0 choices during implementation review.

After explicit G1 authorization, owning repositories qualify:

- Pure profile/selection fixtures and lifecycle matrix: loaded idle/working/
  blocked/error, positive parked/kind exclusion, unknown/failed reads,
  complete-empty, partial hosts/providers, exact identity collisions and scopes,
  independent row/completeness expiry, no inference from missing loaded lists.
- Standalone and independent native installed wheels on supported Python,
  source/wheel/schema parity, explicit capability/source/profile/selector rejection,
  mutable-input rejection and detached exports. Fresh reviewed artifacts are
  required; package version alone is not acceptance.
- Actual projected IPC and fixed-SSH publisher paths, proof-after-nonce, RTT/
  deadline/suspend/clock/gap/restart/reconnect/late-result behavior, slow reader/
  capacity failure and owned cleanup. Test full-feed and Tmux interoperability.
- Fixed active set with 100/500/2,000 dormant rows within declared bounds; zero/
  one/many active and uncertain records, churn, partial coverage and retirement
  beyond display limits. Compare full semantic membership/context before display
  truncation, as well as final wire frames.
- Serial matched timing without a profiler: consumer, projected publisher,
  collector, catalog parent/children and relevant remote scopes separately. Count
  all IPC/SSH bytes, validation/projection work, CPU, RSS/allocation, latency and
  connection/task cleanup. Show transport/RLCD cost does not follow dormant
  inventory; disclose any producer/history dependence and added service costs.

The existing full snapshot permits at most 4,096 rows per host, with its own
byte ceiling. A 5,000-row single-host fixture is a capacity/partial test, not a
normal benchmark. A larger aggregate needs independently verified per-host and
enclosing Mesh bounds. Add complete-empty expiry with no selected bodies,
same-key newer-receipt rejection, partial reconnect after a missed negative,
scope-local ledger overflow/recovery and exact metadata/frame byte limits.

RLCD adoption and operational G2-G4 follow only after both exact producer tuples
are accepted. Preserve explicit full diagnostics and paired rollback/reselection.
ServiceState hosting requires later adoption of a reviewed Observer collector/
service artifact as well as publisher/read and consumer selections. Client-only
a6/a22 adoption cannot add an endpoint to an older native service. G4 must name
and validate those distinct roles and protected Tmux/349/writer selections.
No user/provider/session actions, firmware or native service changes are part of
this planning pass. Manual panel/readability/reboot gates remain separately owned.

## G0 verification

`rtk proxy .venv/bin/python scripts/check.py` passed on 2026-10-16 UTC with
Python 3.14.8 and jsonschema 4.26.0: 29 locked inputs / 22 identical packaged
schemas, 116 design checks, 169 delivery checks, 165 standalone core tests with
zero skips, and lint. This ran without `--native`, `--wss` or `--check-sources`;
there was no new wheel/installed-package, sibling-source, native, fleet or device
acceptance. Only this planning document changed; existing runtime, schemas,
locks, private artifacts and operational selections remain untouched.
