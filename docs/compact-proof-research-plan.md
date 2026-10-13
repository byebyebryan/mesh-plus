# Compact proof, encoding and stream-carrier research

2026-10-12 local date. **Research assessment complete; no runtime promotion.**
Baseline is committed `0345ea579664495d2729b592bddc84e4f511cacc`, released
Mesh a15, SDK interface 1 and accepted lock revision 2. Concurrent uncommitted
Agent timing/profile work is not an input to this plan. Before execution,
refresh the accepted source/artifact tuple and preserve any subsequent accepted
profile addenda; do not replace their locks with this older baseline.

The [execution assessment](evidence/2026-10-12-compact-research/README.md)
records the conditional compact-proof stop, optional owner proposal and matched
TCP/TLS rejection. Accepted runtime and downstream requirements remain unchanged.
The ordered gates below preserve the reviewed plan and its conditional exits.

The [controlled assessment](evidence/2026-10-12-controlled-performance/README.md)
establishes exact-work benchmarking and a WSS shared-publisher memory benefit,
without a compelling single-reader CPU improvement. The next question is whether
avoiding repeated full-state transmission helps more than replacing the carrier.
No TCP, CBOR, Protobuf or compact-proof performance advantage is assumed.

## Separate decisions

| Track | Changes | Holds fixed |
| --- | --- | --- |
| Compact proof | Response contents and binding to retained state | JSON, existing carrier, source acquisition and native admission |
| Binary encoding | Representation of the same logical messages | Proof semantics, source/profile, validation and topology |
| TCP/TLS | Framing and carriage | JSON messages, publisher sharing, authentication and workload |

First establish a safe compact-proof identity. Start its prototype in JSON.
Then compare its JSON, CBOR and Protobuf representations. Separately compare
length-prefixed JSON over TCP/TLS with WSS/JSON. Do not start with a combined
compact/binary/TCP rewrite, or mix process sharing with an encoding claim.

SDK v1 consumers continue receiving the existing reconstructed fleet response
and original receipt semantics. An internal negotiated optimization may preserve
that public shape, but does not automatically fit the accepted wire contract.
The [freeze](contract-freeze.md) explicitly excludes digest-proof; the
[reserved sketch](../contracts/mesh-delivery-v1/contract.md#optional-compact-state-proof)
and [reserved schema](../contracts/mesh-delivery-v1/digest-proof.schema.json)
are review inputs, not implementation authority. Binary WSS messages are also
rejected by the accepted [WSS binding](../contracts/wss-v1/contract.md).

## First gate: what state can actually be retained?

The pinned Tmux a7 cached source opens new status/watch requests. Its owner
frames regenerate `encodedAt`; request correlation, frame kind and stream
sequence are also acquisition-specific. Identical session records do not mean
an identical complete native frame. The preceding synthetic trace deliberately
kept those fields fixed and therefore does not establish native compact-proof
hit rate.

Measure exact raw-frame digest matches first, with a disposable native Tmux
owner and fresh checked acquisition after each nonce. Include unchanged cache,
new accepted evidence with unchanged records, actual changed records, idle
watch delivery, partial/stale/empty/warming state and owner restart. Report
which differences cause misses; matching view revision alone is insufficient.

There are two possible designs:

1. **Exact-frame proof:** retained complete frame and fresh complete frame have
   identical native digests. Compact reply attests that exact frame. This has
   the smallest semantic surface, but may rarely hit on actual owner replies.
2. **Owner-defined stable state plus delivery overlay:** a supported pure owner
   facade partitions a checked frame into retained state and bounded delivery
   metadata, and reconstructs the fresh native frame losslessly. A distinct,
   versioned stable-state digest identifies the retained state. The compact
   reply includes the necessary fresh overlay and fresh full-frame digest.

The second design is only a hypothesis. Mesh cannot generically discard fields
named sequence, timestamp, request ID or remaining validity. The owner must
prove what is delivery-only, retain all authority-bearing facts and receipts,
and certify exact reconstruction. New accepted receipts invalidate the retained
version even if records have not changed. If this needs an owner facade addition,
record a narrow optional networking-interface proposal for owner review. Do
not edit a developing Observer checkout or make existing SDK use depend on it.

If neither design has a safe useful hit rate, stop compact-proof work and retain
full proofs. Do not manufacture hits by extending receipts or ignoring metadata.

## Experimental proof state machine

The study needs a closed request/response definition before code. Candidate
fields include protocol/profile binding, nonce, host/configured source, bridge
incarnation, native owner incarnation/clock, retained identity, fresh evaluation
time and the complete original receipt map. Overlay designs additionally need
their codec/version identity, bounded fresh overlay and fresh native-frame digest.
Review the reserved schema's receipt cardinality, health vocabulary, source ID
grammar and epoch type against the actual supported profiles; do not copy its
synthetic restrictions blindly.

The intended lifecycle is:

1. Admit and retain a complete native frame from snapshot or subscription,
   with explicit byte ownership and existing size/domain checks. Positive remote
   validity still requires a fresh proof.
2. Send a fresh unpredictable nonce and the exact negotiated retained identity
   on that owned channel. Only one proof remains outstanding per Reader host.
3. Validate nonce before a new `native.snapshot()` and check its complete reply.
   No retained watch object or heartbeat substitutes for fresh source acquisition.
4. Return compact success only for a proved matching retained state, owner,
   clock, source and profile. Otherwise return a full checked replacement or a
   typed failure. Define stale-result ordering and replacement/gap/resync rules.
5. The client validates channel/incarnation/nonce bindings, retained identity,
   complete receipts and chronology. For overlays, reconstruct and validate the
   exact fresh native frame and verify its fresh native digest before composing
   the ordinary fleet view. Do not call the old digest a stable-state digest.
6. Derive local expiry from the whole request RTT, original remaining leases
   and existing margin/deadline rules. Transport traffic never renews evidence.

Restart, clock change, gap, disconnect, revocation and scope/profile change
invalidate the appropriate retained state. Proof mismatch cannot keep old
positive rows alive while a replacement is pending. Healthy siblings retain
their independent outcomes. Cache memory and lifetime are explicitly bounded;
no global body cache or cross-client identity shortcut.

Initial snapshots, absent retained state and declared misses use full replies.
An optional offer can negotiate the legacy path at setup; an explicit required
compact capability must reject when unavailable. Authentication failures never
cause carrier fallback. Existing clients never receive unnegotiated variants.

## Encoding candidates

**JSON is the semantic control.** Avoided body transmission and avoided JSON
parsing must be measured before attributing improvements to binary encoding.

**CBOR:** use a specified constrained JSON-compatible data model, string map
keys initially, exact integer/float/bool/null distinctions, bounded depth and
length, and rejection of duplicate keys and unapproved tags/types. Wire byte
fields for nonce/digest require an explicit mapping back to canonical logical
fields. Deterministic encoding is a reproducibility choice, not a substitute for
domain semantics. Integer-key envelope variants are a separate measured option.
[RFC 8949](https://www.rfc-editor.org/rfc/rfc8949.html) defines the data model and
deterministic encoding; its JSON guidance supports a constrained mapping.

**Protobuf:** define a small Mesh-owned envelope/proof schema, with explicit
presence and required semantic admission. Specify missing versus null versus
zero, integer ranges, enum/unknown-field policy, duplicate singular fields and
oneof conflicts. Generated decoding alone is not the existing strict admission.
Keep field numbers reserved when removed. Do not duplicate Tmux/Agent domain
schemas or use a generic JSON Struct conversion as an unmeasured fast path.
Native full replacements initially remain opaque original JSON bytes. That
hybrid experiment measures proof/envelope encoding, not native binary encoding.
[Field presence](https://protobuf.dev/programming-guides/field_presence/) and
[encoding](https://protobuf.dev/programming-guides/encoding/) document those
choices. Protobuf does not require gRPC.

Keep existing native canonical-JSON digest semantics for exact full frames.
If stable-state identity is needed, specify its own domain separation, canonical
logical representation and version. Never hash arbitrary codec bytes and assume
cross-codec equivalence. Protobuf's
[deterministic serialization is not canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/).
All codecs must decode to equivalent validated logical messages and identities.

Full-state CBOR can be a separate size/conversion benchmark over pinned synthetic
Tmux frames. It must include encoding, decoding, reconstruction and existing
native validation costs; smaller wire output alone is insufficient. Agent data
may be represented by documented synthetic sizes/receipt counts, with no active
Agent imports or claimed native Agent acceptance.

## TCP/TLS control

Use one shared listener/publisher topology for both WSS and TCP/TLS. Carry the
existing JSON logical frames over a reviewed fixed-width length prefix with
caps before body allocation, bounded partial-frame deadlines and the same mTLS
identity/source allowlist, policy revocation, per-listener admissions, ownership,
backpressure and shutdown guarantees. Define equivalent liveness checks rather
than removing them to make TCP look faster. No plaintext default, production
endpoint registry change, ordinary firewall opening or live selection.

The accepted WSS protocol uses a handshake followed by framed messages over TCP;
its [specification](https://www.rfc-editor.org/rfc/rfc6455.html) describes masking
and control frames. Measure application framing/parser/liveness cost separately
from TLS, state processing and process topology. This control can proceed even
if compact proof stops at its identity gate.

## Ordered work and exit criteria

| Gate | Deliverable | Decision to proceed |
| --- | --- | --- |
| R0: refresh/pin | Accepted source/lock, immutable Mesh/Tmux wheels, dependency/harness hashes, producer coordination exclusions | Source, package, fixture and live evidence are distinct; concurrent work preserved |
| R1: identity/feasibility | Native Tmux raw-digest hit/miss ledger; stable/overlay proposal only if needed; reserved-schema gap review | Safe identity and useful expected hit rate, or a documented compact-proof stop |
| R2: semantic design/oracle | Experimental negotiation, payload/state machine, digest rules, independent successful/hostile fixtures | Every authority/expiry/recovery case has an explicit expected outcome |
| R3: JSON study | Full versus compact JSON on one existing carrier; same native source checks and downstream view | Exact native reconstruction, unchanged original receipts and complete cleanup |
| R4: encoding study | JSON/CBOR/Protobuf of the same proof/envelope; codec microbench plus full pipeline | Lossless semantics and meaningful end-to-end gain, not just byte savings |
| R5: TCP/TLS control | Same full-proof JSON over WSS versus TCP/TLS with matched sharing/auth/liveness | Attribution isolates carrier implementation cost; no protocol-performance conflation |
| R6: bounded combinations | Only individually useful combinations, repeated actual Tmux acceptance and adversarial/recovery/resource checks | Candidate meets correctness/resource gates and explains mismatches/fallback cost |
| R7: review/handoff | Per-track keep/reject/promote proposal; SDK impact, migration and rollback; exact immutable candidate if justified | Explicit normative review before runtime integration or lock changes |

Prototype files, draft schemas and codec generators live under a study directory,
outside packaged schemas and `contracts/LOCK.json`. R0–R6 research does not
advertise a runtime capability. R7 prepares a reviewable normative proposal;
it does not grant automatic promotion or ordinary deployment selection.

## Measurement and validation matrix

Use the [controlled runner](../studies/controlled/README.md), adapting it only
after native identity feasibility is understood. Pin disposable actual Tmux
source/facade inputs; no active Agent checkout or service is needed. Include
header-changing native traces as well as synthetic immutable-frame controls.

- Successful unchanged proofs, new evidence with identical records, changed
  state, source loss/partial/stale/empty/warming and owner/clock restart.
- Tiny/ordinary/large frames and low/high receipt counts; one reader first,
  then two/four independent upstream readers and a distinct prepared topology.
- Nonce reuse/mismatch, stale digest, profile/source/epoch swap, field mutation,
  receipt omission/duplicate/health/expiry changes, malformed/oversized codec
  input, slow readers, credit starvation, disconnect and cancellation.
- Source changes between push and proof or during admission, expiry during RTT,
  late results after invalidation, failed fallback and healthy sibling isolation.

Record match/miss reasons, full-replacement rate, bytes by logical variant and
carrier framing, source acquisition/validation, hashing/encoding/decoding/copying,
consumer work, CPU time per completed step, latency, sampled PSS/RSS, channels,
drops/resync and owned teardown. Do not omit the native full read or reconstruction
cost from compact success. Count fallback extra round trips and CPU explicitly.

Four fresh ABBA blocks are the primary comparison, after a small accepted pilot.
Require exact logical trace and receipt outcomes, equal native acquisition/proof
cadence and attributed roles. Archive failures and exclusions. Include both
short proof-only work and a longer normal-cadence owned trace; body/byte savings
may vary substantially with state-change rate and proof hit rate.

Planning heuristics remain >=15% primary CPU or >=20% primary PSS improvement
in three of four blocks with no reproducible >5% regression elsewhere. A byte
gain alone requires a concrete network/deployment use case; no universal codec
winner is assumed. Freeze any revised decision threshold before timing. Physical
suspend, real network paths and credential operations remain separate selection
gates. No change is a valid outcome for every track.

## Coordination and boundaries

Mesh owns proof negotiation, delivery, codecs, carrier, generic identity binding,
measurement and cleanup. Observers own any native stable-state/overlay semantics
through supported pure facades; Mesh does not infer provider state or strip
native fields. Existing Tmux and Agent development continues against accepted
SDK/profile contracts. Proposed new optional hooks get a narrow written owner
handoff only after R1/R2, with no required migration of existing consumers.

SSH Plus remains the authority client; its configuration, route-health and picker
history interfaces are unaffected. No Plus UI/action work, broker, replay/event
protocol, delta-state protocol, collector change, chezmoi scripts/docs or ordinary
transport selection belongs in this research pass. State deltas remain a later
independent proposal after compact proof demonstrates value.
