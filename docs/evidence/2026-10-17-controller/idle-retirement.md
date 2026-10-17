# Queued idle-frame retirement correction

Runtime **`d013d2afd14c3d6fa03a3fe377b62aff3ee5944b`** corrects the
coordinator's adjacent queued-retirement finding against
**`14990c789f853441b51af81ea0919facf0aff320`**. The earlier
[copy/close correction](copy-close.md) remains at its original source and
evidence pins; this report supplies new evidence for the additional correction.

A worker could logically close an idle stamped frame and enqueue its one
owner-loop retirement callback. If the owner loop immediately entered carrier
close before that callback ran, close skipped the already pending frame, dropped
the range storage, and returned its own credit. The pending callback then failed
while updating ranges and never returned the frame's credit. The unchanged
public probe reproduces a callback `TypeError` and a remaining 132,952-byte heap
reservation on both Python versions. This is an implementation regression in
the earlier correction, not a new contract or measured cap/RSS violation.

Owner-loop carrier close now directly retires every idle frame, including one
whose worker already queued retirement. The queued callback subsequently sees
an already retired credit and does nothing. Storage also requires an empty
frame inventory before release; retiring the last frame rechecks that boundary.
The inventory remains bounded to two frames and queued callbacks remain bounded
to one per frame. Active materialization still pins its original DTO, frame slot
and credit until copy/error unwind. Revocation is immediate; close joins active
copies, preserves independent detached-copy credit, and closes only its own
carrier. Public APIs, wire, source/scanner interfaces, role/encoding bindings,
deadlines, 32/64 caps, schemas, LOCK and version are unchanged.

## Immutable qualification

The [receipt](idle-retirement.json) and
[saved qualification](idle-retirement/qualification.json) bind source inputs,
commands, loaded module hashes and retained outputs. The
[qualifier](qualify_idle_retirement.py) uses the
[unchanged new public probe](probe_idle_frame_retirement_original.py.txt), SHA256
`051e31f1fbecb3f4ef4fe76d5f32a7897fc80066f40d57088bba0bc27a97d1be`,
and the unchanged earlier copy/close probe `b33788f8`.

| Check | Python 3.14.8 | Python 3.11.17 |
| --- | --- | --- |
| New unchanged idle-frame probe, before | One callback TypeError; 132,952 heap bytes retained; sibling usable | Same |
| New unchanged idle-frame probe, after | No callback errors, sibling usable, repeated close safe, final five counters zero | Same |
| Original copy/close probe, before and after this correction | Both copy interleavings remain charged, retired copies reject, close joins unwind, sibling and final counters correct | Same |
| Final new test against before source only | One method, two failed checks: callback assertion and teardown credit assertion; no errors/skips | Same |
| Carrier/controller/relay checks after correction | 68 pass, zero failures/errors/skips | Same |
| Frozen actual-source basic composition | 24 scenarios pass | Same |
| Frozen actual-source lifecycle composition | 20 scenarios pass | Same |
| Canonical gate | 387 tests, zero failures/errors/skips; unchanged lock/design/delivery/Ruff pass | Not rerun |

The new test queues worker close for both live idle frames, repeats close while
the owner loop cannot process callbacks, and verifies immediate public rejection.
It retains real callback/public errors with GC disabled, checks independent
caller copy credit and the detached value, and exercises a same-ledger sibling.
The before run overlays only this final test onto the prior immutable runtime;
the teardown failure is an additional assertion on the same retained credit,
not another test method or independent defect.

The frozen basic and lifecycle runners use immutable Observer
`e3441d017b94ee27f4dfccb5f1f3f30612435adf`. Their trusted caller, synthetic
collection-disabled Runtime/source data, private nonce/native teardown,
controlled writer hooks, bounded private physical-storage audit and separate
fixture/owner/Reader/relay/oracle accounts remain explicit. Both have new outputs
at this runtime pin; no old acceptance or current Observer CPU checkpoint is
reattributed. Prior controller, lifecycle and copy/close artifacts are unchanged.

Reproduce with fresh immutable exports and output:

```sh
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-controller/qualify_idle_retirement.py \
  --mesh /absolute/export/d013d2a --before-mesh /absolute/export/14990c7 \
  --observer /absolute/export/e3441d0 \
  --python311 /absolute/environment311/bin/python --output /absolute/new/results
```

Independent correction review remains pending. No wire output/authority bypass,
aggregate physical-heap/RSS/plateau, whole-pipeline CPU, dense 2,000-row delivery
or delivered cold/recovery, populated native providers, fixed SSH, immutable
installed-pair qualification or ordinary authenticated/selected Reader route is
accepted here. Existing producer CPU failures remain failures. No API/schema/ID
allocation, artifact build, selection, Git attribution cleanup, sibling edit,
provider/service action or rollout occurred.
