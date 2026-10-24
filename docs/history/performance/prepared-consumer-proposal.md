# Opt-in prepared consumer ownership proposal

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

2026-10-13. **Draft for explicit API/guarantee review, not SDK 1 acceptance.**
Historical proposal: the subsequent user-authorized implementation defines the
additive [prepared interface](../../prepared-consumer-api.md). This document and its
study evidence retain their original scope; they do not certify implementation.
Builds on the [simplification assessment](../../evidence/2026-10-13-simplification/README.md).
Accepted source main is `c4ec7ca`; this branch includes the compatible
simplification checkpoint `cd4acc5`. SDK 1 / lock 3 and all packaged bytes stay
unchanged by this ownership study. No downstream work must wait for this proposal.

## Decision

Do not transparently replace ReadGuard.current/current_sessions with compiled
state. Legacy callers can mutate raw dictionaries, and later native/profile
callback rejection is observed by full admission. The study provides explicit
mutation, later-rejection and changed-eligibility witnesses: a sealed compiled
view can behave differently. Passing static-data golden cases does not remove
that incompatibility.

Pursue an **explicit opt-in local consumer type** only after its ownership and
static-preparation guarantee are reviewed. No compact proof, binary carrier,
transport capability or wire field is needed. Publishers/Readers continue full
fresh acquisition/proof/admission exactly as before.

## Proposed surface (names remain draft)

`PreparedReadGuard(domain, request_id, *, profile, preparation, host_ids=None)`
would own one sealed generation. It would expose:

- `accept(frame)`: full existing schema/native/proof/receipt and stream admission,
  then privately copy/compile the admitted generation before publishing it.
- `current(now_ms, clock)`: new owned row dictionaries from that generation,
  applying current receiver clock and original per-record receipt expiry.
- `snapshot()`: a new owned raw dictionary in the ordinary fleet response shape.
  Mutating this export or a current result cannot mutate the retained generation.
- `disconnect()`: retire the generation and stream, release retained state and
  return no positives thereafter. Fresh reconnect requires a new guard.

Existing ReadGuard, raw current_sessions/validate_response, signatures, callback
invocation behavior and mutable-view revalidation remain unchanged. The prepared
type has no public writable view/receipt facts; private Python internals are not
a sandbox against hostile installed code or reflection.

An explicit unsupported preparation rejects at construction before dispatch.
No guessed profile marker, automatic opt-in, wire/config callable selector or
fallback after authentication/policy failure is introduced. Default callers
continue on the accepted path. CLI and deployment selection are separate work.

## Optional owner preparation boundary

A supported pure owner facade could supply a versioned preparation object bound
to the selected profile descriptor/native version and reviewed package bytes.
Its conceptual operation is `prepare_rules(checked_native_state)`, returning
one typed rule per admitted record, matched by the already admitted identity.
A rule contains original receipt requirements and a boolean native eligibility.
Mesh supplies the records; the compiler does not invent or replace row payloads.

The owner must explicitly promise:

1. Rules depend only on the complete admitted native value, never wall time,
   callback mutable state, environment, live owner activity, actions or I/O.
2. Preparation is nonmutating, lossless and deterministic for the same value;
   rules remain valid for that sealed generation until it is retired.
3. Any native semantic change affecting requirements/eligibility needs a new
   checked publication. Current visibility remains bounded by original leases.
4. Native policy/validator changes do not silently affect an already prepared
   generation. A changed installed compiler/profile must retire it and re-admit.

These are **new explicit guarantees**, not inferred from the word “pure” in SDK 1.
The study calls existing callbacks once to model compilation; that alone cannot
certify an existing owner profile for the new contract. Tmux a7 is a study input,
not an accepted prepared owner. Agent active code was not imported or modified;
Agent v1/v2 golden fixtures establish generic shape only.

Mesh validates rule count, identity/order, exact types and receipt-key attribution
against the admitted native state. None/empty requirements grant nothing. Foreign
or malformed rules cannot grant visibility; invalid preparation fails closed.
Known unavailable/unknown/unsupported requirements remain nonpositive. A True
native eligibility flag cannot override Mesh health, lease, delivery or clock.
Mesh does not implement provider/session policy to make missing rules work.

## Sealed representation and checks on each query

Internally retain immutable row bytes, an immutable rules/lease table and bound
reader/scope/incarnation/profile identifiers. Scope and original receipts are
captured after full admission; raw views are copied exports, not mutable aliases.
The study stores a full snapshot plus row bytes for clarity; production storage
must account for that duplication and may choose one body representation.

For each query, check receiver clock and now >= admitted reader encodedAt;
require ready delivery and native eligibility; require every named receipt to be
originally current/partial and its projected receiver expiry > now. Use the
minimum expiry of required receipts only when that is equivalent to the existing
all-required rule. Never extend leases because of queries, controls or retained
objects. No row is made positive from absent/partial owner evidence.

Keep dynamic lifetime distinct from immutable facts. EOF, liveness failure,
revocation, gap, terminal, source loss, clock/incarnation or scope/profile change
must retire the affected generation using the existing observable adapter
barriers. A gap requires an admitted resync. A heartbeat cannot replace or renew
facts. Healthy sibling outcomes keep only their independently admitted leases.
Retired generations cannot be recovered by a late result. No replay/broker.

One guard owns one generation with aggregate/native/metadata caps unchanged;
replacement is transactional and accounts for peak old/new storage. Compile
failure retires positives for the prepared path and closes/resyncs it; it does
not silently retain a previous positive value or fall back to unchecked JSON.
This fail-closed prepared behavior is explicit, separate from legacy transactional
accept failure plus its caller's mandatory disconnect handling. No instantaneous
external failure detection or cross-thread hard real-time promise is added.

## Study and acceptance gates

The [study](../../../studies/ownership/README.md) fully admits every new frame and models
sealed output/expiry/lifetime rules. Its lifecycle wrapper intentionally uses
both legacy stream admission and separate full preparation admission; timing
includes this duplicate preparation. It makes no native/source/transport saving.
It compares complete consumer lifetimes with 1/4/16 reads per publication,
including accept, preparation, output ownership and teardown, not only cheap
lookup time. Static-profile equivalence and incompatible legacy witnesses are
reported separately.

Before a supported implementation:

1. Review this local Python API, static-rule promise and mutation/later-rejection
   behavior explicitly. Preserve every accepted legacy default and wire byte.
2. Specify preparation DTO/version binding, errors, cancellation/publication
   ownership, serialized-byte capacity, cache lifetime and replacement memory.
3. Mesh implements complete admission plus compilation with one privately owned
   result per accept; no server/client or provider collection changes.
4. Each opted-in owner independently certifies golden rule equivalence, partial/
   missing evidence, expiry, future timing semantics and code/version invalidation.
   Existing profile-only work remains independent and usable.
5. Run frozen native inputs, hostile/mutation/lifecycle cases, repeated reads and
   high churn. Require measured benefit including preparation and allocation,
   steady/peak memory bounds and no receipt/authority regressions.
6. Isolated installed wheel/compatibility/native and optional transport acceptance;
   release and operational adoption are later explicit selections with rollback.

The present goal ends with a reviewable proposal and evidence. It does not
promote the study model or regenerate a contract lock to approve it.
