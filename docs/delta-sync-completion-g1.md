# Completion forwarding G1 source checkpoint

This implements the generic side of the
[reconciled optional source seam](delta-sync-completion-transfer-r2.md).
It is unselected source work: actual Observer source-to-relay qualification and
route acceptance remain open. No wheel, native schema, encoding ID, controller
grammar, installed selection or rollout changes.

Relay setup requires `changes_with_completion` explicitly. A legacy
transaction-only source fails setup; no completion is inferred from its tuple,
EOF or watch, and no native JSON is synthesized. The ordinary material publisher
and source `changes()` API keep their own existing route and behavior.

An acquisition accepts either the supported completed batch or an explicit
recovery control. It validates bounded public shape, unique exact-channel refs,
at most four transactions/eight MiB, and the independently bounded completion.
Malformed/oversized/foreign result shapes do not transfer; owning session cleanup
retires their own scope. A valid transferred batch closes as one source-owned
result even when its first raw header fails.

The generic relay pins and scans all frames before emitting any material prefix.
It checks exact tag/binding adjacency, cursor epoch/continuity, requested target,
terminal complete status/base/target/tag/cursor, and public control metadata
against the original native header. Zero transactions require equal base/target
and a self-consistent original control. Preflight also verifies every nested
Mesh envelope, including the final 64 KiB control bound. The configured structural
codec independently enforces its native-family limit (Agent: 16 KiB).

Successful output drains each original transaction before the original terminal
control, preserving its exact native fragment. All pins and separately owned
metadata remain charged through physical output cleanup. Each write/drain
rechecks batch and input-ref revocation. Once the source revokes its transferred
refs, a late completion rejects even when the shared input owner and siblings
remain live. The actual source tracking gap described below remains open.
Failure/cancellation retains unretired physical pins and existing quarantine
credit until cleanup. No proof timer, acquisition deadline, shared cap or Reader
admission/authority rule is relaxed.

The 27 focused relay tests run with cyclic GC disabled, including retained
failures and repeated cancellation. They cover zero/one/four exact completion,
chain and terminal mismatches, malformed/duplicate headers, missing or replaced
metadata, foreign/duplicate refs, preallocation refusal, material/envelope bounds,
recovery, drain ordering, scope revocation, both material/control failed writes,
sibling isolation and final five-counter zero. The source and codec in these
tests are bounded **fixtures**, not the actual Observer implementation. The
existing single-line IPC fixture still uses that fixture source.

The actual Agent structural codec is additionally exercised with fixture batches
for full/active zero/one/four transaction cases. The existing native control has
no separate `nativeBindingDigest` field: its exact typed tag carries the binding.
An initial draft assumption requiring that extra field rejected valid controls;
the corrected consumer preserves the existing schema and original bytes.
This codec composition remains distinct from the actual owned-source result.

A separate scoped diagnostic against Observer `3a75191` receives a real source
head ref over its synthetic Unix endpoint, holds a disclosed private generic
input pin, optionally calls public `session.inspect()`, then closes that session.
Without inspection, pin exit rejects `sync_input_retired`. With inspection,
the source registry prunes the consuming ref and pin exit succeeds after session
close. The raw remains charged during the pin and all counters eventually reach
zero. This exposes a revocation/tracking gap, not measured late relay output or
a cap overrun. No `nbytes` semantics, new public scope API or sibling code is
changed here; the owning source/generic retirement seam needs reconciliation.

At this checkpoint the owning Observer worktree has the accepted method/result
proposal and completion-correlation fix, but has not implemented
`changes_with_completion`. Therefore actual source completion transfer,
completed-result/cancel-before-delivery, real full/active metadata accounting and
joined native/Reader behavior remain required before any route acceptance.
The older [relay source report](evidence/2026-10-16-delta-sync/RELAY-G1.md)
retains its old runtime/producer pins; its four controlled actual-source
baseline/head cases are not completion coverage and are not reattributed here.

Original dense/cold/recovery CPU and byte gates, packed 2,000-row delivery,
aggregate 32/64 MiB resources, RSS/plateau, populated IPC/fixed SSH and the exact
immutable installed pair remain open. Actual source integration will be qualified
against an owning committed implementation rather than an adapter that reads
private producer state or fabricates the missing control.

The [byte-pinned checkpoint evidence](evidence/2026-10-16-delta-sync/completion-g1-review.json)
records the exact runtime and immutable Observer export, commands, full/focused
results, native-codec composition and separate source-pin diagnostic. The saved
diagnostic is an expected reproduction of the open gap, not a passing source
lifecycle qualification.
