# Completion relay probe retirement expectation

> Historical record. This document preserves its original checkpoint and may describe retired providers, interfaces or plans. Use the [current documentation](../../README.md) for supported setup and behavior.

The [named probe revision](../../evidence/2026-10-16-delta-sync/verify_completed_relay_retirement.py)
corrects one historical test expectation: a four-transaction batch and its exact
completion still have **five live consuming refs** while material drain is
blocked. Source inspection must retain their scoped revokers. The old expectation
of zero refs observed the consuming-pin pruning defect and is unsuitable for
qualifying its fix.

The original
[completion probe](../../evidence/2026-10-16-delta-sync/verify_completed_relay.py), SHA256
`7ffe624538930c634738a5b940da20e58a78306437822f080bee05692463803c`, remains
byte-for-byte unchanged. The revision imports its fixtures and inherits seven
methods unchanged. Its one replacement method must match the original AST after
only changing `ownedRefs == 0` to `ownedRefs == 5`; the runner verifies this before
executing any test. Drain, batch, credit, sibling, cancellation, error and teardown
assertions remain intact. It runs only these eight relay methods, with owning
component suites retaining their separate provenance.

The [receipt](../../evidence/2026-10-16-delta-sync/completed-relay-retirement-probe.json)
pins a **before** run on unchanged Observer
`7213084557ed4dd63361567bb75bd262b2e517bc` and Mesh runtime
`6fce5ed0e997d021e7532051fe985c3693962c3e`, exported from
`2ec7bcf3a3422a68bd522502928a648954932e1d`. Each Python 3.14.8/3.11.17 run,
with cyclic GC disabled, produces exactly one expected `0 != 5` failure and seven
passes, with no errors or skips. The existing owning fixture teardown checks
remain enabled. This is validation of the revised test and reproduction of the
old source registry behavior; it is **not** a passing final source pair.

Observer's reported uncommitted source adoption and one-assertion adaptation
retain their own evidence. An immutable committed source fix, the unchanged
original/hardened five-case regressions and final paired source/relay lifetime,
physical-credit, history and sibling checks remain required. The public
[owner retirement query](delta-sync-ref-retirement-g1.md) and its exact interface
agreement are already complete; this revision introduces no new API or approval
wait. No source weakening, runtime, artifact, schema, ID, selected-route or rollout
change belongs to this probe update.

Run against a committed fixed source with fresh paths:

```sh
rtk proxy /path/to/python -B docs/evidence/2026-10-16-delta-sync/verify_completed_relay_retirement.py \
  --mesh /path/to/mesh-export --observer /path/to/committed-observer-export \
  --output /path/to/fresh-result.json --log /path/to/fresh-unittest.log
```

`--expect-old-pruning` explicitly selects the before mode, requiring just the
named ref-count failure. Default mode requires all eight tests to pass. Both
modes preserve the original limits and exercise disposable synthetic native/IPC
fixtures under a trusted direct test controller. They do not qualify populated
providers, ordinary controller/carrier execution, aggregate resources, CPU,
dense 2,000-row recovery, RSS, fixed SSH or an immutable installed pair.
