# Compact proof identity: research stop and optional owner proposal

2026-10-12. **Draft for owner review, no accepted capability or required migration.**
Inputs are Mesh 0.1.0a15, SDK 1 / lock 2 and Tmux Observer 0.6.0a7.
[Native evidence](evidence/2026-10-12-compact-research/identity.json) measured
**zero exact native-frame digest matches in 26 comparisons**. Rapid cached
reads regenerate correlation/emission metadata. Periodic collection renews
original accepted receipts even with unchanged records. Idle native watch
filters heartbeats, so it does not necessarily deliver those renewed receipts.
This is an identity/admission issue before it is an encoding issue.

## Disposition

Keep full fresh proofs. Stop the conditional JSON compact prototype and its
CBOR/Protobuf comparison at R1. No generic timestamp, sequence, request ID or
receipt exclusions are authorized. The actual native check covers unchanged
cache, accepted evidence renewal, watch/status, idle watch, changed rows, ready
empty, loss and owner restart. Warming/expired/failed/unsupported states in the
ledger are pure installed OwnerState fixtures, separately identified. Tmux does
not declare partial as a native service receipt state; no partial fixture was
invented. Neither this fixture nor synthetic unchanged frames proves a viable
compact hit rate for real observers.

## Narrow optional owner interface

An owner could propose an **optional pure, versioned partition/reconstruction
facade** on top of its supported profile. These are interface requirements,
not names or methods to implement now:

- Validate the complete acquired native frame, then partition it into a retained
  authority-bearing body and a bounded fresh delivery overlay.
- Preserve every field losslessly. Declare which fields are delivery-only and
  why excluding them from retained identity cannot alter state/authority.
- Keep original receipt identity, accepted counters, expiry, owner incarnation,
  clock and all domain facts in the retained body under this proposal. New
  accepted evidence invalidates its identity even when record contents match.
- Reconstruct the exact new full native frame from body and overlay; run the
  existing pure full native validation before ordinary fleet composition.
- Specify limits, canonical logical identity and a distinct versioned digest
  domain. Existing `ownerDigest` continues hashing the complete native frame.
- Demonstrate useful hit rate with realistic accepted-evidence renewal, owner
  watch filtering and proof cadence. Do not assume periodic idle evidence is
  delivered as a changed state candidate.

If including receipts in the retained body still defeats useful hit rate, stop
this proposal. A record-only body with **fresh authority-bearing receipts in
every overlay** would be a different design requiring explicit owner and Mesh
review, fresh evidence validation, full receipt chronology and new oracles.
It must not be presented as delivery-only field removal.

No existing Observer/SDK factory must acquire this hook. Current downstream
work can continue independently on the accepted full-proof contract. Mesh owns
transport, negotiation, retention and delivery; owners certify native partition
semantics. Agent active development was neither imported nor edited.

## Closed semantic proposal for later review

Only an explicitly negotiated capability may carry a compact variant. Optional
offer falls back at setup to full proofs; requiring the capability rejects an
unsupported peer. Authentication or policy failure never triggers fallback.
Prototype schemas, if authorized, belong in studies until normative review.

A request binds an unpredictable admitted nonce, host, configured source,
profile/codec identity, owned channel and the exact retained-body identity.
The publisher must perform a new checked native cached read after nonce
admission. A watch object, revision number, heartbeat or cached proof cannot
substitute. Only one proof is outstanding per Reader host.

A compact result binds the nonce, source/profile, bridge and owner incarnation,
clock, retained identity, fresh full-frame digest, bounded overlay, original
receipt identities/counters and freshly evaluated remaining leases. Missing
identity, any semantic mismatch or a body change returns a complete checked
replacement in the same result, or a typed error. No extra fallback RTT is
assumed free. A two-request fallback design must count the extra RTT and retain
no positive old state during replacement.

The client reconstructs and validates the exact fresh native frame and digest,
then applies the existing remote proof/RTT/expiry rules. The whole request RTT,
margin and original remaining validity bound local expiry. Candidate retention
alone grants no current authority. Retention is per owned host/channel,
size bounded, and retired on gap/disconnect/scope or profile change, revocation,
clock change and owner/bridge restart. A late result cannot revalidate a retired
incarnation. Healthy sibling hosts keep independently admitted outcomes.

## Independent expected-outcome oracle

This table fixes expectations before a future prototype. It is a design oracle,
not a report of compact runtime tests; no compact runtime was implemented.

| Input / event | Expected result |
| --- | --- |
| Identical complete frame and bindings | Exact-frame compact success is semantically possible after a fresh read; not observed in native ledger |
| Header-only differences, no owner partition | Full replacement; never strip unknown fields |
| Reviewed overlay, byte-exact reconstruction, unchanged retained body | Conditional compact success, then full native admission |
| New accepted receipt, same records | Retained-body miss under this proposal; full checked replacement |
| Changed row / ready empty / partial state | Changed body replaces; empty is valid only from positive owner evidence |
| Failed/warming/unsupported/stale owner | Preserve actual native outcome; no current state inferred from missing snapshot |
| Expired receipt or RTT exceeding remaining lease | Zero positive validity regardless of transport liveness |
| Wrong/reused nonce, wrong host/source/profile/digest | Reject, no old positive rows survive mismatch |
| Missing/duplicate receipt, regressed counter or altered expiry at same counter | Reject; full proof cannot renew unchanged evidence |
| Owner/bridge incarnation or clock change | Invalidate retained identity and bind a complete replacement |
| Change between push and proof | Fresh proof wins; retained candidate alone remains non-authoritative |
| Change during owner acquisition | Owner's coherent cached frame governs; Mesh does not stitch collections |
| Late result after disconnect/revocation/resync | Reject retired channel result, clear affected retention |
| Malformed/deep/oversized codec or overlay | Reject before unbounded allocation/reconstruction |
| Failed fallback or missing full replacement | Affected host unavailable/stale, no preserved positive authority |
| Sibling host success | Keep separately validated sibling outcome |
| Cancellation / slow reader / credit starvation | Bounded retirement; no orphan cache/source subscription |

## Reserved sketch gaps

`contracts/mesh-delivery-v1/digest-proof.schema.json` is frozen reserved study
material, not an accepted runtime variant. Its fixed 32-receipt bound, restricted
health vocabulary, configured-source grammar and synthetic epoch/binding shape
must be checked against each real profile. A production proposal must explicitly
bind profile/codec and bridge/owner incarnation, preserve unknown/unsupported
outcomes, and establish limits compatible with actual profile descriptors.
Do not regenerate the lock or reuse a reserved name as implementation approval.

## Encoding research after identity review

JSON remains the semantic control. Constrained CBOR preserves the current JSON
logical model most directly, but requires depth/size bounds, duplicate-key and
type/tag rejection. [RFC 8949](https://www.rfc-editor.org/rfc/rfc8949.html)
defines deterministic encoding requirements and duplicate-map-key concerns.
A small Protobuf envelope can avoid repeated field names, but needs explicit
presence, enum/unknown-field and duplicate-field admission rules; native domain
frames remain opaque JSON unless owners approve a separate codec.
[Protobuf deterministic serialization is not canonical](https://protobuf.dev/programming-guides/serialization-not-canonical/),
so codec bytes cannot replace the existing canonical logical digest.
No codec winner or byte/CPU advantage was measured in this pass.
