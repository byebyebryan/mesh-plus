# Independent source retirement review

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

The scoped consuming-ref source registry defect is resolved in the reviewed pair:
Observer `e3441d017b94ee27f4dfccb5f1f3f30612435adf` with Mesh runtime
`6fce5ed0e997d021e7532051fe985c3693962c3e`. Observer's changed runtime file,
`sync_owned_source.py`, has SHA256
`3492c94d818eb29be8fd959288de17a8ec49701e90b7d64d118cff7a943f48d1`.
This is a file digest, not an additional commit. The
[review receipt](../../evidence/2026-10-16-delta-sync/source-retirement-pair-review.json)
pins immutable inputs, owning evidence and independent executions. No runtime
or sibling changes belong to this Mesh review.

The source requires the agreed public `ref_is_retired` callable before reserving
session state or starting I/O. It captures that callable, requires exact booleans,
prunes only `True`, and retains available or consuming `False` refs for scoped
revocation. It uses no `nbytes` fallback or generic private graph. Batch cleanup
closes and untracks only its own children without querying unrelated refs. The
captured callback drops after child/I/O cleanup. These changes preserve shared
owners, sibling sessions and physical pin credit through actual retirement.

Independent runs on **each Python 3.14.8 and 3.11.17**, with cyclic GC disabled
and no skipped tests, cover:

- The byte-identical original five-case overlay (`95b02d0c`) and hardened overlay
  (`fa9fd6e9`) each reproduce three expected source gaps plus two control passes
  on Observer `7213084` with the same Mesh runtime. Each overlay passes all five
  cases on `e3441d0`. The hardened end-of-pin-body assertion remains intact.
- **48 affected source tests**: nine retirement tests, 24 existing owned-source
  tests and 15 completed-changes tests. They include real public-factory relay
  refs, healthy inspect/receive during a pin, immediate scope-close revocation,
  held physical credit, strict setup/non-bool rejection, bounded retained
  terminal history, callback retirement, batch cleanup and sibling survival.
- The [named eight-method completion probe](delta-sync-completed-relay-retirement-probe.md)
  passes against the final pair. It retains the AST-verified one-assertion
  correction requiring five live pinned transaction/completion refs. Actual
  source/relay/Reader, exact terminal bytes, native control limits, held real
  drains, cancellation, failed writes and sibling teardown remain checked.
- The [three compact composition methods](delta-sync-compact-relay-g1.md) pass
  again on this final pair: six full/active zero/one/four transaction cases,
  exact received native fragments, two fresh actual relay-head proofs per case,
  completion-as-proof rejection, wrong-route refusal and semantic rejection of
  an opaque invalid body. This is new-pair evidence; prior `7213084` results keep
  their own provenance.

These counts are separate suite executions with overlapping fixture coverage,
not a claim of 79 unique tests. All loaded project modules match the corresponding
immutable exports. Owning 220-test and 940-test results are verified saved
evidence, not independently rerun or included in these focused counts. The
original upstream 220-test failures at its stale zero-ref assertion remain
preserved; the historical probe and old source receipts are unchanged.

The source, Reader and relay retain their existing pin/counter teardown checks.
The pin fixture uses disclosed private generic pin helpers; the actual relay
composition uses a trusted direct test controller and private Reader nonce setup.
Native state is synthetic. These observations do not establish aggregate
32/64 MiB peaks, RSS, dense CPU or 2,000-row/cold recovery, populated native
providers, fixed SSH, ordinary controller/carrier execution or an immutable
installed pair. No artifact, schema/encoding ID, selected role, provider, service
or rollout acceptance follows from this scoped source closure.

The [focused runner](../../evidence/2026-10-16-delta-sync/verify_source_retirement.py)
accepts explicit Mesh/Observer exports and an optional exact overlay. Before mode
`--expect-gap` requires precisely the three named failures; default mode requires
all cases to pass. The receipt records fresh result/log paths and commands for
each original/hardened before/after run and both existing relay reproducers.
