# Stamped-header copy/close correction

Runtime **`14990c789f853441b51af81ea0919facf0aff320`** corrects the
coordinator's m156 finding against **`a482abbd463d23ebf66f23c60e4e95a521c19cc6`**.
Before, `HeaderRef.materialize()` borrowed the frame's DTO without a copy pin.
Reentrant frame close or concurrent carrier close could return that DTO's credit
while `deepcopy` still held it, and the call could return a detached value after
revocation. The original [controller](README.md) and [lifecycle](lifecycle.md)
checks passed their bounded scopes but did not close this separate finding.
They remain unchanged at their original runtime pins.

The correction keeps the original DTO and its original frame credit pinned
through copy and error unwind. Close revokes metadata immediately. A copy that
observes retirement before its publication check raises `sync_control_retired`;
it does not return the detached value. Original and caller-copy credit remain
independent. Error frames are sanitized and borrowed/result locals cleared
before the original pin can release.

There is one in-flight copy per frame, still within the two-frame carrier bound.
Concurrent or recursive materialization of that same frame rejects before copy
as `sync_control_copy_busy`. A retired frame with an active copy still occupies
its slot. Fixed lock/event/counter metadata and bounded owner-loop cleanup
callbacks use the existing prepaid carrier reservation; no cap increases.
Worker completion leaves its slot busy until the one owner-loop callback runs,
so worker loops cannot queue a history of pending completions. Credit/range/slot
retirement occurs on the owning event loop. Carrier close joins copy unwind,
including repeated cancellation, and preserves sibling carriers and caller
copy reservations. Clock checks/read sampling are serialized with that state.

Public signatures, wire grammar, role/encoding binding, source/scanner APIs,
authority checks, deadlines, original 32/64 caps, schemas, LOCK and version remain
unchanged. This is a compatible implementation correction, not an API freeze or
runtime/producer acceptance.

## Immutable qualification

The [receipt](copy-close.json) and [saved results](copy-close/qualification.json)
bind exact Git bytes and retained before/after outputs. The [qualifier](qualify_copy_close.py)
replays the **unchanged coordinator probe**, SHA256
`b33788f836fd9585fad85fb50c439eb3d567e3f75682d76145bd2819fc933a0f`,
preserved as [original source](probe_header_close_original.py.txt).

| Check | Python 3.14.8 | Python 3.11.17 |
| --- | --- | --- |
| Unchanged original probe, before | Both close interleavings reproduce early credit return and detached return after close | Same |
| Unchanged original probe, after | Heap stays 593,088 during copy; concurrent close does not finish early; no detached return; retired error; sibling usable; caller 66,760 credit retained; final five counters zero | Same |
| Three final named tests against before source | Three expected failures, zero errors/skips | Same |
| Carrier/controller/relay focused checks | 67 pass, zero failures/errors/skips, GC disabled | Same |
| Actual-source basic composition | 24 scenarios pass | Same |
| Actual-source lifecycle composition | 20 scenarios pass | Same |
| Canonical gate | 386 tests, zero failures/errors/skips; lock/design/delivery/Ruff pass | Not rerun |

The new tests cover reentrant frame close during copy; concurrent carrier close
joining a worker copy despite repeated caller cancellation while preserving a
sibling; and same-frame concurrent-copy rejection plus the two-slot bound while
a logically retired copy remains physical. Real errors are retained with GC
disabled. The before source uses only the final test overlay, not changed
runtime helpers. The original probe uses public carrier/header/frame/ledger
APIs with controlled copy timing and no private source mutation.

Both actual-source replays use immutable Observer
`e3441d017b94ee27f4dfccb5f1f3f30612435adf`. Their original private nonce/native
fixture teardown, trusted caller, synthetic data/collection-disabled Runtime,
writer hooks/physical inventory audit, separate ledgers and oracle exclusions
remain explicit. The basic runner covers Unix IPC and pipe stdio,
expanded/compact, full/active, 0/1/4 transactions and fresh actual heads. The
lifecycle runner covers watches, expiry, cancellation, partial writes, physical
pins, EOF caller disconnect and siblings. These new runs have their own source
pin; prior f667588 / 1e37541 outputs are not relabelled.

Reproduce with fresh immutable exports and fresh output:

```sh
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-controller/qualify_copy_close.py \
  --mesh /absolute/export/14990c7 --before-mesh /absolute/export/a482abb \
  --observer /absolute/export/e3441d0 \
  --python311 /absolute/environment311/bin/python --output /absolute/new/results
```

The first draft of the new concurrent test left its sibling open until teardown
then incorrectly expected the shared ledger to be zero before that sibling's
close. The fixture now explicitly closes the sibling; the draft remains a
test-cleanup diagnostic, not a producer fail-before case.

No measured cap/RSS overrun, late wire output or authority bypass is claimed for
the original defect. Independent correction review, aggregate resource/RSS,
whole-pipeline CPU, dense 2,000-row delivery and delivered cold/recovery,
populated native providers, fixed SSH, immutable installed-pair qualification and
ordinary authenticated/selected Reader integration remain open. Producer CPU
failures remain failures. No artifact/ID/schema allocation, source selection,
sibling edit, provider/service action or rollout occurred.
