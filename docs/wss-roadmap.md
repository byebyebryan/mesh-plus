# WSS evaluation and extension roadmap

The study sequence below is historical. The separate a14 promotion is accepted
at source/private-wheel scope; see [the promotion record](evidence/2026-10-11-wss-promotion/README.md)
and [WSS SDK/configuration](wss.md). Real-fleet selection remains separate.

2026-10-11 planning checkpoint against released a13. This is a reviewed research
plan, not authorization to advertise WSS support. The [state freeze](contract-freeze.md)
and [lock](../contracts/LOCK.json) still accept IPC/SSH only. Existing Observer
SDK v1 adoption remains independent of this work.

## Outcome and boundaries

The next unattended loop should deliver a Mesh-owned experimental WSS carrier,
an authenticated fixed-source listener, endpoint/configuration draft, end-to-end
state acceptance, a fair SSH/WSS comparison and a concrete promotion proposal.
Completing that loop does not require selecting WSS as a default or releasing it
as supported runtime. A negative or inconclusive performance result is valid.

Keep prototype modules, draft schemas, fixtures and runners under a separate
`studies/wss/` directory. Ordinary package imports, CLI, SDK exports/signatures,
packaged resources and dependencies stay unchanged. A standalone study runner
loads this explicit code; no runtime plugin discovery or hidden backend fallback.
Only disposable loopback listeners, certificates, SSH fixtures and cached native
fixtures are authorized for study acceptance. All project tooling stays in Mesh.

Do not edit Observers, Plus consumers or chezmoi. SSH Plus keeps Host Mesh v1,
SSH route health and picker history. WSS-only hosts, browser authentication,
reverse relays, events/replay, brokers, pooling and compact proofs are separate
tracks. Neither a source refactor nor an experiment authorizes deployment.

## Reviewed constraints

| Finding | Consequence for the plan |
| --- | --- |
| Read/Delivery envelopes reserve WSS, but the freeze excludes its runtime | Schema acceptance alone cannot promote a carrier; preserve every locked byte. |
| Channel consumers also require `maximum`, `closed`, owned close and optional metrics | Prove the actual Client/Bridge interface, not only send/receive compatibility. |
| Reader hardcodes remote delivery as `ssh`, including unavailable outcomes | A raw WSS channel is insufficient for truthful fleet provenance. Draft a binding extension and keep any experimental Reader adaptation isolated. |
| `configured_reader` resolves a Host Mesh catalog and connects remote hosts through SSH | Draft a separate registry resolver; do not reinterpret its current factory or defaults. |
| Read contract describes both backend-specific tokens and revision/host/route-index tokens | Review the exact WSS token preimage and configuration revision interpretation before normative promotion. |
| Existing WSS study uses a synthetic publisher and server TLS trust | Reuse research, not acceptance; client authorization and SDK lifecycle remain unproven. |
| Pushed candidates require a checked full cached reply/proof | WSS carries the same state semantics; Ping/Pong cannot renew source evidence. |

## Proposed study decisions

Use the existing Mesh Delivery v1 frames and domain profiles over one UTF-8 text
message per JSON value. Keep request/reply and subscriptions on the same owned
duplex connection. Reject binary messages, invalid JSON, wrong subprotocol and
multiple JSON values. Reuse the strict Mesh encoder/parser and lifecycle checks;
do not create a second protocol implementation.

Start with `websockets==17.1`, already pinned in the historical study, in a
dedicated study environment. Compression and ambient proxy selection are disabled.
Configure opening, TLS, close, ping, frame/message queues and write limits
explicitly. Select final numerical settings by the bounded acceptance cases,
not library defaults. The existing directional limits apply: 64 KiB client
control frames and the negotiated server message/profile ceiling, at most
8 MiB + 80 KiB. Count UTF-8 JSON bytes; report WebSocket/TLS/NIC bytes separately.
[Client API](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html)

Preserve BOOTTIME acquisition/proof budgets and owned cleanup through repeated
cancellation. Fragmented messages need a first-fragment-to-completion deadline,
size and fragment-count bounds. A partially consumed fragment stream or timed-out
write closes the owned connection; it must not be reused with uncertain framing.
Prove the pinned library's receive/send cancellation behavior with real fragments.
[Connection lifecycle](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html#using-a-connection)

Study authentication uses mutual TLS for native Python clients. Server trust and
hostname validation remain mandatory. The listener verifies a client certificate,
maps its DER fingerprint through an explicit principal allowlist, then authorizes
an exact host/source/profile before invoking Bridge. A certificate subject or a
claimed hello host is not an identity registry. No secrets in URLs, requests,
public reports or debug TLS logs. Browser-origin requests are rejected in this
native-client study; browser access is not an acceptance claim.
[Python TLS](https://docs.python.org/3.14/library/ssl.html)

Each listener exports one configured cached publisher, with no request-selected
path, executable or collector. Rotation can overlap explicitly listed old/new
certificates. Authorization removal and listener-policy changes revoke existing
connections, not just future handshakes. Propose policy checks beginning at most
five seconds apart with a five-second BOOTTIME read budget; failed checks close
the channel, with separately bounded cleanup. Test certificate expiry during an
active connection as well as admission. This is bounded policy observation,
not instantaneous PKI revocation. Default TLS verification does not itself supply
an application revocation service.
Certificate validity uses the TLS wall-clock validity interval; source leases
and acquisition/cleanup budgets remain BOOTTIME based. Tests must not subtract
certificate timestamps from source clocks. Read configuration/credential inputs
as bounded owned snapshots and test path replacement between validation and use.

The draft registry references existing canonical Host Mesh IDs. It contains
version, endpoint ID/index, host/source/profile, WSS URL and local trust/credential
references; credentials are separately private. It creates no aliases or SSH
routes. Resolve ordered immutable selections under one Mesh composition owner,
using Host Mesh plus registry/trust revisions. Monitor changes to every admitted
configuration input. WSS failures never become SSH route-health reports.
Use a parsed `wss://` URL with one configured path. Reject userinfo, query,
fragment, redirects and implicit proxy destinations. W0 must verify that the
pinned library can enforce that exact endpoint without unsupported private hooks;
otherwise choose another carrier implementation before continuing.
Keep draft registry identifiers in a study namespace. Admit only product `state`,
the three frozen capabilities and current configured-source selector syntax.
The reserved endpoint schema's broader event/source vocabulary is not an
accepted runtime configuration format.

W0's candidate token preimage is canonical JSON containing `bindingProtocol`,
`selectionRevision`, `hostId` and `endpointIndex`. The candidate selection revision
binds the Host Mesh revision, ordered endpoint registry and admitted local trust/
credential configuration. Private key material and route health are excluded.
Server authorization revisions are monitored by the listener; they are not
pretended to be client-local catalog inputs. These are explicit study semantics,
not a reinterpretation of the currently frozen route-index rule.

Draft a backend binding with truthful path and immutable endpoint token, applied
to ready, connecting and unavailable outcomes. Preserve legacy IPC/SSH factory
behavior. Keep the current `Endpoint`, `Reader` and `configured_reader` public
signatures while studying how an additive, separately reviewed factory/binding
could expose this. Do not infer a backend from a function name or mutable Client
attribute. An experimental Reader specialization may label outcomes for study
only; it is not evidence that unmodified SDK v1 supports WSS configuration.

## Unattended sequence

| Phase | Deliverable | Gate to advance |
| --- | --- | --- |
| W0 — baseline and proposal | Exact a13/native/dependency inputs; Channel inventory; registry, authorization and provenance drafts; explicit runtime promotion diff | Frozen/package hashes captured; concrete ambiguity resolutions recorded; existing core/profile gates pass. |
| W1 — isolated carrier | Owned WSS channel and loopback TLS listener implementing the actual Client/Bridge seam | Same strict parser/lifecycle; small/large UTF-8 frames, fragments, deadlines, cancellation and close tested; no ordinary runtime edits. |
| W2 — authenticated binding | Mutual-TLS principal mapping, fixed-source authorization, registry resolver and experimental truthful Reader binding | Wrong/missing/expired certs and wrong host/source/profile fail before source dispatch; active revocation and combined-revision changes revoke authority. |
| W3 — end-to-end state acceptance | Both profiles over WSS: snapshot, proof, subscribe, update, restart, disconnect, reconnect and source expiry | Compare native/current-state semantics against a13; prove passivity, visible revoke/resync, original receipts and zero retained connections/tasks. |
| W4 — carrier comparison | Matched fresh-process IPC/SSH/WSS measurements, cold/warm acquisition and resource limits | Same native validators, payloads, proof cadence, subscriber count and process topology; every run has complete semantic and cleanup evidence. |
| W5 — decision and handoff | Accepted/rejected/inconclusive study; exact draft runtime/configuration changes, dependency/packaging proposal, rollback and owner-independent integration tasks | Redacted reproducible evidence; all locked/runtime bytes retained; supported runtime promotion remains an explicit later review. |

Each phase gets one coherent commit after review and its checks. Push checkpoints
under existing authorization. Never commit temporary private certificates, keys,
host data or unbounded logs. Report a failed phase and retain its scoped evidence;
repair an implementation defect, but do not relax authentication, parser, lease
or resource guarantees to make it pass. Revisit a dependency choice if the actual
Channel lifecycle cannot be implemented with its supported API.

W0–W5 are the bounded next goal. Normative promotion is not a pause halfway through
that goal: it is the separate follow-on task described below. No prototype is
added to the normal wheel or ordinary CLI by the unattended research loop.

## Acceptance matrix

| Area | Required positive and adversarial cases |
| --- | --- |
| Framing | Exact directional ceilings; UTF-8 byte boundaries; duplicate keys/nonfinite/depth/node failures; fragmented large frame, stalled fragments, excessive/empty fragments, binary frame and wrong subprotocol. |
| Authentication | Trusted server and authorized client; untrusted server, wrong hostname, missing/untrusted/expired client cert, authorized CA but unknown principal, wrong source/profile/host, browser Origin and unexpected URL/path. |
| Policy | Explicit certificate overlap then removal, active certificate expiry, authorization removal, missing/unreadable/malformed policy, registry/trust/catalog replacement during snapshot/watch, revision change before first dispatch. |
| Delivery | Requests amid push, baseline barrier, independent cancellation, credit exhaustion, slow consumer gap/resync, late result quarantine, terminal exhaustion, full handle-budget rotation. |
| Native state | Both domains; empty current versus warming/historical/partial evidence, saved/unsaved Agent eligibility, stale receipt and expiry without new publications, forged nonce/digest/clock/receipt and lossless reconstruction. |
| Recovery | Actual publisher update/restart, listener restart, abrupt TLS loss, reconnect with a new epoch, healthy sibling under failed host, paused consumer and repeated cancellation during setup/write/close. |
| Resources | Bound admitted connections and pending handshakes in the fixture; account for library frame buffers, assembly/JSON copies, Mesh queues and OS/TLS buffers; no surviving listeners, children, tasks or keys. |
| Independence | Frozen v1 and pure profile parity; no provider imports/collection in generic carrier, no SSH health/history writes, no sibling-source-HEAD dependence. |

A queue high-water mark is not a hard whole-process memory limit. Fragment queues,
assembly and decoded JSON can coexist with Mesh's existing 96 MiB per-client
queue. Capture RSS and queue counters under slow readers and oversized peers;
use explicit fixture connection/handshake admission ceilings. Do not claim a
global memory pool or unmeasured RSS bound.
[Library buffers](https://websockets.readthedocs.io/en/stable/topics/memory.html)

## Measurement and decision rules

For each domain, compare SSH and WSS in ABBA order across idle, four-reader
updates, 256-row updates and observed failure/recovery: 32 fresh-process runs,
30 seconds of steady observation each. Run IPC separately as a local reference;
it is not a like-for-like remote winner. Add ten cold acquisitions per remote
carrier/domain and a bounded slow-reader/handshake-admission resource case.

Use the same pinned native validator/profile, cached fixture and proof cadence.
Place publishers in separate owned processes for both remote carriers; an
in-process WSS server versus SSH descendants would confound the comparison.
Match one publisher worker per Reader in the primary four-reader comparison.
Any shared-listener/multi-client WSS process experiment gets a separate topology
label and cannot be attributed solely to the carrier. Publication fixtures must
broadcast updates to every subscribed reader; the kit's single-consumer `changes`
queue must not be treated as a multi-reader broadcaster.
Report worker/publisher/process-tree CPU, RSS, logical handles, physical channels,
completed JSON bytes, transport bytes when measured, latency samples, expiry
and revoke/recover observations. Record warm-up, excluded descendants, sampling
interval, host load, tool/library/TLS versions and raw run order.
An idle cached source may expire during observation; record that expected
transition. Fixture producer updates may issue new original receipts only through
the reviewed native facade. Carrier traffic must not manufacture receipt renewal
to keep the measurement inventory positive.

Two samples per carrier/scenario establish descriptive feasibility, not stable
tail latency. Repeat only the decision-driving scenario if variance prevents a
conclusion. Do not infer NIC savings from JSON byte counters or proofless push
from lower validation CPU. Report whether a benefit comes from cold setup,
persistent carriage or a topology difference. No cost reduction is required to
finish the study; native-client reachability can independently justify a carrier.

Default disposition: keep IPC/SSH supported, WSS opt-in candidate. Select a shared
connection service only if duplicated reader costs justify its own ownership and
downstream-expiry design. Select compact proof only if full-state/proof cost
justifies a separately negotiated capability. A disappointing WSS result does
not trigger an unattended broker, pooling or protocol rewrite.

## Supported runtime promotion after the study

Before ordinary WSS support, review a concrete contract/lock addendum that removes
only WSS runtime from the excluded set, defines authenticated endpoint authority,
revision/token provenance and authorization/lifetime guarantees, and preserves
Read/Delivery/domain meanings. Review new SDK/configuration surfaces separately;
do not regenerate the existing lock or packaged schemas to hide semantic drift.
If compatibility cannot be preserved, negotiate a new interface/profile explicitly.

Then implement opt-in packaged modules and dependency extra, source and installed
conformance, pinned native acceptance, SSH Plus compatibility when authority is
affected, and immutable package/checksum verification. Existing clients retain
their exact pins until owner-selected acceptance. Listener/service installation,
real Snap/Starship networking, physical suspend, WAN/proxy behavior and paired
rollback are a further operational task. The study completes without these gates.

## Planning review and validation

The [planning review](evidence/2026-10-11-wss-roadmap-review.json) records checked
inputs and unresolved runtime questions. It validates roadmap boundaries and
existing design gates, not WSS functionality or production performance.
Historical [carrier acceptance](transport-validation.md) retains its own scope.

## Completed study checkpoint

The W0–W5 loop completed on 2026-10-11. The
[outcome](../studies/wss/outcome.md) records authenticated state carriage, both
native profiles, cross-Python acceptance, 32 original and eight refined remote
ABBA runs, 40 cold acquisitions, true local IPC controls and bounded resource
stress. Its disposition is feasible opt-in candidate, with runtime promotion
deferred to the [concrete review proposal](../studies/wss/promotion-proposal.md).
The frozen parser's generic byte/depth limits do not add a global node cap.
Study phase budgets and local-file thread limits do not establish a promoted
aggregate setup/send/configuration IO guarantee. Existing runtime, schema/lock,
authority and deployed pins retain their own accepted bytes.
