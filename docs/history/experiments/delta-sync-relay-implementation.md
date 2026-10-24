# Private relay G1 implementation checkpoint

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

The closed [R4 contract](delta-sync-relay-api-r4.md) is implemented here as an
opt-in Python ownership/output scaffold on the G1 branch. It is **unqualified**:
there is no installed factory selection, CLI route, operation dispatcher,
artifact, service change or rollout. The frozen G0 appendix and LOCK are
unchanged. Contract closure and these source tests do not establish G1/G2
completion or expand the selected a7/a23 tuple.

`mesh_plus.sync.create_sync_relay` takes the explicit R4 source, descriptor,
source binding, structural codec, budgets and shared ledger. It accepts no
domain profile or material cache. Separate relay ref/reservation/owner types
reuse only the private byte allocation engine; ordinary Reader admission stays
independent. The supplied source's `open_session(inputs)` is synchronous, as in
Observer's supported facade. No private Observer state is used.

Channel, acquisition capsule and watch have separate lifetimes. Argument
rejection precedes channel ownership transfer; valid setup takes ownership even
when setup fails. Input close revokes the owning channel immediately. Unsealed
receive leases and consuming output pins retain physical credit until cleanup.
One output lock serializes material, control and head sequence numbers. Capsule
and proof deadlines remain absolute and include output-lock waiting. A capsule
cannot reset its deadline. Closing an idle watch or capsule preserves its
channel, shared input owner and siblings. A partially written frame can require
closing its affected connection.

Structural scanner reserve capabilities retire after each callback; returned
ticket leases remain independently owned. Detached headers are prepaid through
the public `materialization_bytes`/`materialize` seam. Native JSON is never
decoded or reserialized by the generic relay. It is pinned, checked for strict
single-LF framing and spliced into bounded envelopes. Chunked writes prepay
transport copies and require empty userspace buffers after drain. Failed physical
shutdown retains quarantined copy/input credit and fails close rather than
claiming successful retirement. This failure path still needs independent
resource qualification.

Baseline and head forwarding run through the complete supported Observer source
and scanner in the controlled two-IPC probe. Ordinary Reader baseline admission
and fresh confirmation run independently. Structurally valid changed bodies
with unchanged claimed roots are forwarded and rejected by that admission.
These tiny synthetic fixtures are not populated capacity or native service
acceptance. Their inputs, capture buffers and oracle storage are outside the
relay ledger; its peak is not an aggregate process/RSS measurement.

## Remaining controller/completion seam

The current supported `SourceSession.changes()` returns a tuple of transaction
refs only after verifying native completion. It closes/discards the native
completion control. R4 also requires exact native control forwarding, so the
relay cannot reconstruct that control from the returned tuple. The present
Python changes scaffold checks the whole bounded chain before emitting any
prefix and drains the material frames, but it does **not** claim native
completion delivery. It must not be selected by a controller as a completed
R4 transaction route. One concrete completion-transfer review is pending with
Observer/RLCD; no duplicate role approval or private source access is needed.

The exact generic operation-request grammar and its hello/setup dispatcher are
also not allocated or implemented by this source checkpoint. The trusted
controller must complete authenticated fresh hello before calling
`open_channel`; a fixture-supplied complete binding does not qualify that
bootstrap. No wire command, schema or legacy fallback is invented here.

Dense producer CPU, compact normalization/schema execution, packed 2,000-row
input/staging/recovery, aggregate ownership/RSS, real proof timing, installed
IPC/fixed SSH and paired qualification remain open. The narrow earlier
input-owner and confirmation-lifetime fixes remain separate accepted source
findings; this implementation does not reattribute their evidence.
