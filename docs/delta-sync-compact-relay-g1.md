# Small compact source, relay and Reader composition

The [reproducer](evidence/2026-10-16-delta-sync/verify_compact_relay.py) composes
Observer `7213084557ed4dd63361567bb75bd262b2e517bc` with Mesh runtime
`6fce5ed0e997d021e7532051fe985c3693962c3e`, exported from checkpoint
`2ec7bcf3a3422a68bd522502928a648954932e1d`. The
[receipt](evidence/2026-10-16-delta-sync/compact-relay-review.json) binds exact
inputs, results, loaded modules and diagnostics. This adds test evidence only;
production runtime, packaged schemas, identifiers and selected routes are unchanged.

Three methods pass on **each Python 3.14.8 and 3.11.17**, with cyclic GC disabled,
held errors and no skips. They cover nine scenarios:

- Six full/active zero/one/four transaction cases use the actual disposable
  native `Runtime` Unix dispatcher, explicit compact source and structural
  transport codec, Mesh byte relay and independent compact Reader. Every
  baseline, transaction, whitespace-padded completion and nonce-head fragment
  equals the exact dispatcher return after extraction from received Mesh bytes.
  Both baseline and target receive distinct fresh native-head proofs through the
  relay, and confirmed DTOs equal the native owner. An original valid completion
  control presented as a proof rejects; staged changes cannot be acquired before
  a fresh valid proof.
- Expanded source or expanded transport codec combined with compact native
  material rejects before a material prefix, without sniffing or fallback.
- A 200,000-character invalid opaque body crosses the structural source/relay
  unchanged. Independent Reader admission rejects `sync_compact_value_shape`
  and grants no current view.

Reader six counters and relay five counters return to zero, source sessions and
sockets close, native fixture scratch returns to its base, and the native
Runtime threads stop. All 73 loaded project modules in each run match the
immutable input exports. The earlier 203-test source/component runs retain their
[separate provenance](delta-sync-compact-source-observer-g1.md) and were not rerun
or combined into these new counts.

The first test-carrier draft omitted the required native LF. Its correction
initially matched `SourceTag.native` instead of the final payload field. These
were harness errors, preserved in separate diagnostics. The final carrier anchors
to the complete bounded payload header, extracts the received fragment and
restores its single native LF. It checks exact fragment equality independently
of the owner capture; the invalid-body test requires its semantic error code.
No production input or framing rule changed to accommodate either draft.

The native state is synthetic with collection disabled. A trusted test controller
calls public relay methods directly and performs private Reader nonce setup; it
does not execute the proposed controller/carrier grammar or authenticated hello
bootstrap. Owner, capture/oracle, relay and Reader storage are separate accounts.
These results do not qualify aggregate 32/64 MiB peaks, RSS, dense nine-field or
2,000-row capacity/recovery, CPU, fixed SSH, populated native providers or an
immutable installed pair. Compact watch, held-drain/cancellation and expired-head
composition are not exercised by these three methods. The unchanged Observer
consuming-ref pruning defect and its pending owner-query adoption remain open.
No artifact, service, provider, sibling or rollout action belongs to this review.

Reproduce with fresh result and log paths:

```sh
rtk proxy /path/to/python -B docs/evidence/2026-10-16-delta-sync/verify_compact_relay.py \
  --mesh /path/to/mesh-2ec7bcf-export \
  --observer /path/to/observer-7213084-export \
  --output /path/to/fresh-result.json --log /path/to/fresh-unittest.log
```
