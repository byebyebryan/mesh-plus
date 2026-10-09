# Mesh Plus base read contract

Status: candidate Mesh Read 1, 2026-10-09. Structural schemas and semantic rules
are used together. This is a read contract; it grants no action capability.
Example domain profile versions are experimental names, not allocated Observer
release versions.

## Request

`request.schema.json` defines a request with `meshProtocol: 1`, an unpredictable
`requestId`, domain profile, operation (`snapshot` or `watch`), `access: cached`,
and selection (`local`, `fleet`, or an explicit nonempty host list). Profile and
source selectors are fixed installed configurations, not arbitrary commands,
provider homes or socket paths. Catalog resolution produces the explicit ordered
host list used by the response. Unknown explicit hosts fail before dispatch.

Snapshot has a finite deadline. Watch requires an initial full replacement
within the same setup budget, then continues with independently bounded host
recovery. Cancelling either operation stops only owned read resources. Reads do
not start an owner service or native runtime and never fall back to direct reads.

## Common response section

`schema.json` describes `mesh`. A domain profile references it alongside its own
`protocol`, `schemaVersion` and `sessions` schema. Local and fleet use the same
profile and the same required fields. Host order follows resolved selection.

| Field | Meaning |
| --- | --- |
| `meshProtocol` | Base semantics version, initially 1 |
| `requestId`, `operation`, `access` | Request correlation, snapshot/watch and cached semantics |
| `scope.hostIds` | Exact ordered selected hosts, never inferred from present rows |
| `catalog` | Ready or local-only authority, revision and local identity |
| `reader` | Reader incarnation, local BOOTTIME clock domain, sequence and material view revision |
| `kind` | Full view or resync; separate small controls carry heartbeat and gap |
| `status` | Delivery completeness: complete, partial, pending or unavailable |
| `hosts` | Exactly one independently attributable outcome per selected host |
| `extensions` | Bounded optional diagnostics; never new authority |

`complete` means every selected host delivered a compatible validated response.
It says nothing about domain coverage, fresh components or native task success.
A delivered warming/null response is still successful delivery. `partial` means
at least one ready delivery and at least one other outcome. With no ready
delivery, a connecting host gives `pending`; otherwise status is `unavailable`.
This rule works identically for one and many hosts.

Remote-only explicit selection need not include the local host. `localHostId`
identifies the reader endpoint; a selected host has `local: true` exactly when
its ID equals that value. A local-only catalog admits only that one host.

Each host outcome contains:

| Field | Meaning |
| --- | --- |
| `hostId`, `local` | Catalog identity; local dispatch uses IPC, never SSH |
| `delivery` | Path, status, epoch, selected route token, transport/compatibility error and correlated proof |
| `viewState` | Current, historical, warming or unavailable retained source view |
| `owner` | Original snapshot metadata, owner contract and optional original service header without its snapshot |
| `receipts` | Source/component validity translated into the reader clock domain |

`owner: null` means no validated owner response. An owner response with
`metadata: null` retains its original warming service header and source status.
Warming is not empty discovery.
An accepted complete-empty snapshot has non-null metadata and zero rows. Retained
metadata after delivery loss uses `historical`; it is not current authority.
The candidate retains no unbounded history: at most one owner view per source.

Top-level sessions are the concatenation of each accepted owner snapshot in host
order, preserving each owner's native order. Every record must name an included
host and match that owner's domain scope. Duplicate complete identities are
invalid; equal native IDs across hosts or provider namespaces remain distinct.
Domain selectors may reorder/filter a validated view without calling collection.

## Errors and compatibility

Transport errors are typed bounded codes on `delivery.error`, with no raw stderr.
Initial codes include `timeout`, `disconnected`, `authentication_failed`,
`host_key_rejected`, `tool_missing`, `unsupported_contract`, `invalid_response`,
`capacity`, `scope_changed` and `cancelled`. Consumers accept unfamiliar valid
diagnostic codes and branch on explicit status fields.

Native/source failures and limitations remain in owner metadata, not transport
errors. An authenticated bridge reporting an absent Observer is a reached host
with an unavailable source. It cannot poison route health or trigger a second
domain invocation merely because the source failed.

An invalid request/catalog produces `error.schema.json` before a host view is
available. One host's malformed or incompatible result instead becomes that
host's outcome, preserving valid siblings. Unsupported Mesh/profile versions
are rejected. Top-level known objects are closed; bounded additions go in
`extensions`. A new state, guarantee or required field needs version negotiation.

## Validity receipts

A receipt names a profile-defined `sourceId` and component, and has explicit
health (`current`, `partial`, `stale`, `warming`, `unavailable`). Current or partial
receipts require a positive `expiresAtMs` in `reader.clock`; other receipts have
null expiry. The owner contract determines which rows/facts depend on each
receipt. Networking never interprets provider state or extends source leases.

Cached reads do not renew native evidence. The pure profile facade checks the
reader boot/time namespace and current BOOTTIME at every use, including UI
callbacks. It invalidates expired or disconnected positive facts using the
domain's uncertainty projection. Native event/activity clocks are never changed.
Without a public dependency map, Agent projection conservatively invalidates all
current claims for an affected provider at the earliest active component expiry.
An already stale component does not force a healthy component to expire at zero.
The receipt map includes every configured component in the accepted service
header, including stale and warming components. A missing history receipt cannot
silently turn a runtime receipt into validity for all provider fields.

Local IPC validates ownership, expected source, UID and boot/time domain. Its
receipt expiry is checked in that same clock domain. Remote receipt expiry is
proved as follows:

The common clock namespace is canonical `time:N`, where N is the kernel namespace
inode. Tmux already uses that encoding; Agent's Linux `time:[N]` encoding maps
to it without changing the original owner header. Adapters reject unknown clock
encodings. This is identifier normalization within one host, not time translation
between hosts or an assertion that equal inodes on different hosts are equal clocks.

1. The reader records `t0` on its BOOTTIME clock and sends an unpredictable nonce.
2. On receipt, the host-local bridge performs a bounded **cached** source read.
   It validates the owner contract, same-user endpoint, source binding and original
   source leases. It starts no collection.
3. After validation, it records bridge encoding time in the owner's clock domain
   and calculates each component's `r = max(0, sourceExpiry - encodeTime)`.
   The returned full owner view, receipt map, nonce and source binding travel
   together in one immutable reply. A payload digest binds the proof to that view.
4. The reader validates the entire reply by `t1`, in the same outstanding epoch.
   It computes `expiry = t1 + max(0, r - (t1 - t0) - margin)` for each component.
   Candidate margin is at least 100 ms; accepted proof RTT is at most 2 seconds.
5. It accepts current claims only until that conservative expiry, additionally
   subject to domain coverage and stream health.

The proof deadline begins when the request is queued for send; local write delay
is included. Setup/authentication has a separate deadline. Probe clocks are
local; owner absolute expiry is never subtracted from reader BOOTTIME. Wall time
is for display only. Reader suspend advances BOOTTIME and expires overdue proof.

The bridge need not make the original owner echo a nonce. A fresh local cached
read and remaining validity calculated from **original absolute leases** bind
the nonce to that returned view. It must never calculate remaining time from
source frame arrival, an advertised TTL or a heartbeat. An owner in a different
time namespace is rejected unless a separately proved translation exists.

An unsolicited push carries a candidate view. It cannot renew positive validity;
a materially changed candidate requires a fresh correlated full reply. Gap,
restart, conflicting source binding and disconnect revoke affected positives
immediately. Negative source failures may invalidate immediately. Independent
receipts keep healthy providers usable where the domain profile permits it.

## Bridge and watch

The second candidate separates the
[Mesh delivery session](../mesh-delivery-v1/contract.md) from its IPC/SSH/WSS
carrier. The fixed-source bridge below is the baseline state adapter wire and
full-proof fallback. A negotiated delivery session can carry those payloads or
use the separately specified digest-proof extension. Domain projection and
validity arithmetic are unchanged.

`mesh.hosts[].delivery.path` accepts `ipc`, `ssh` or `wss`. The route token is
an immutable backend-specific binding digest, not necessarily an SSH alias;
WSS uses a separately versioned endpoint registry. The WSS fixture establishes
parser/validity equivalence only, not an implemented WSS owner adapter.

`bridge-request.schema.json` and `bridge-reply.schema.json` define a fixed-source
proof exchange. The bridge has configured source IDs and adapters. A request
cannot choose arbitrary executables or paths. The complete original owner
snapshot/service frame is carried in the reply for independent domain validation;
the user-facing profile then projects it without changing record contents.

A bridge channel has its own publisher UUID, boot/time scope and monotonically
increasing sequence. Owner sequences remain in their original per-connection
scope; a new cached probe can legitimately have owner sequence one again. The
adapter compares owner incarnation, view revision and source counters, rather
than comparing sequence numbers from different local connections.

A `watch` bridge request first receives a nonce-correlated `proof` reply. It then
receives `candidate` events containing the original owner frame and its digest,
with null nonce and no translated remaining map. Material candidates trigger a
coalesced `proof` request on that same configured channel. Only its correlated
full reply can renew positives. Bridge heartbeat/gap controls contain no owner
payload or receipts; a gap revokes source positives until a new full proof.
An unsolicited `error` has a typed error and no owner payload. A failed proof
echoes its nonce and carries a typed error. All events keep the channel's fixed
source/host/bridge/clock binding and consecutive bridge sequence; restart creates
a new channel guard. Original owner sequences remain independently validated.

A watch emits full replacement domain views plus `control.schema.json` records.
The domain stream schemas accept these records and a terminal base error.
Reader sequence starts at one and
advances for every frame; view revision advances on material change only. A
heartbeat carries only request/profile correlation, reader/clock/sequence,
the same view revision and transport liveness; it carries no owner rows or
receipts. Gap revokes current claims in the retained view, followed by a
full resync before positives can return. There is no durable or native event
replay. Reconnect creates a new guard; late old-epoch results are rejected.

The reader projects partial host failures in replacement views, rather than
waiting for every remote to recover. Source sampling remains independent of
subscriber count. Refresh hints, where supported by Tmux, are a separately
negotiated extension; Agent does not gain a refresh operation.

## Bounds

At most one correlated proof is outstanding per channel. Protect its reply from
unsolicited candidate coalescing; blocked protected delivery ends the channel
within the proof deadline. Reader view revision describes aggregate publication,
not an atomic cross-host sample or a total order of native events.

Loss of catalog authority or a changed immutable selection terminates the watch
with a correlated base error and closes its guard. Resubscription resolves a
new scope. Late replies from the old guard never acquire the new authority.
Candidate bridge/reader heartbeat interval is five seconds and transport silence
deadline is fifteen seconds, independent of owner lease lengths.

These are candidate admission limits, not performance acceptance claims. The
catalog retains Host Mesh v1's 128-host limit; an initial prepared reader admits
at most 16 selected hosts and returns explicit capacity errors beyond that.

| Resource | Initial bound |
| --- | --- |
| Requests and terminal errors | 16 KiB each |
| Common response metadata excluding owner documents | 64 KiB |
| Owner documents | Domain limits: Tmux 1 MiB observation plus 16 KiB service overhead; Agent 8 MiB plus 16 KiB |
| Aggregate response including metadata and LF | 16 MiB |
| Sessions | Domain limits per host; aggregate constrained by exact byte cap |
| Strings / JSON nesting / nodes | Domain-specific documents keep their own stricter limits; common metadata uses 4096 chars, depth 12 and 8192 nodes |
| SSH diagnostics | 64 KiB, private and content-free public classification |
| Setup concurrency | Four attempts, with established streams serviced independently |
| Setup deadline / snapshot total deadline | 15 seconds, no restarted whole-operation budget |
| Proof round trip / started-frame deadline | Two seconds through full validation |
| Reader subscriber limit | 32 |
| Per-reader output | One started frame and one replacement; slow clients disconnect within bounded progress deadline |
| Aggregate queued/retained application bytes | 96 MiB per reader, including shared buffers counted once and owned child accounting reported separately |

Unknown extensions count toward byte/depth/node limits. Capacity failure never
truncates a roster while claiming complete delivery. Local and fleet require
the same limits; a local Agent response can be larger than Tmux's whole current
fleet protocol and must not inherit its 1 MiB cap by accident.

Host Mesh identifiers retain their existing 16,384-character bound as an
exception to the common string limit; the metadata byte cap still applies.
Owner documents and bridge remaining maps are validated independently against
the selected profile. A bridge reply may add at most 16 KiB to its owner frame's
native limit. Route tokens are `sha256:` of canonical JSON containing catalog
revision, canonical host ID and configured route index, and are diagnostics only.
A route token does not authorize an action or replace the catalog's destination.
