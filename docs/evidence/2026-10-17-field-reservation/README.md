# Exact packed2k reservation call sites

This diagnostic locates the previously unlocalized final reservation failures
on unchanged Mesh `13f27e25c46e1fd3da664975e964104a56fd6dbf` and Observer
`b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f`. It makes no runtime, API, budget,
estimate, artifact or selection change. Both versions still correctly refuse
baseline admission at the original cap. **The two Python versions stop in
different generic construction phases.**

| Python | Refused heap request | Decoded bytes | Reserved bytes | Would total | Call site |
| --- | ---: | ---: | ---: | ---: | --- |
| 3.14.8 | 256 | 11,574,350 | 55,534,310 | 67,108,916 | Packed `_Slot` control while building `$fields` |
| 3.11.17 | 1,024 | 9,669,914 | 57,438,091 | 67,109,029 | Ordered-index baseline node before field processing |

The heap maximum remains 67,108,864 bytes. These are valid refusals, not a cap
overrun or evidence that the request estimates can be cut. Each replay has one
observed reserve failure. Reported heap/encoded peaks, outcome and final six
counters exactly match its original
[field-reference qualification](../2026-10-17-field-ref-sharing/README.md).
All counters return to zero with the actual public failure held and GC disabled.

What was observed

On Python3.14, `reconstruction.py:_field_patch:759` calls the baseline builder
for `index/$fields`. Its recursive packed branch construction reaches
`_packed_nodes.py:_branch:649 -> _slot:310 -> _control:300 ->
Reservation.grow:403 -> reserve(256)`. A weak reference to the exact failing
exception confirms that it escapes `_field_patch`, `_patch` and `_finish`.
This is a control-object reservation after the packed branch allocator has
created its node. Existing unwind releases that node and all other owned data;
the six-counter cleanup remains zero. It is not an observed allocation leak.

On Python3.11, the earlier `apply_indexes:90 -> OrderedMap.baseline_atoms:212`
path reaches `ordered.py:_node:62 -> prepay(1024)`. The workspace intentionally
sanitizes the original exception and then raises a replacement. The diagnostic
links the original weak error identity to `_retire_error`, retains only its
all-scalar `(code, None, None)` result tuple, and matches that exact tuple in
`_raise_failure`. The replacement weak error then escapes `_patch` and
`_finish`. This avoids mistaking the intentional exception replacement for a
handled capacity attempt or incorrectly assigning the Python3.14 field phase
to Python3.11.

Instrumentation and binding

[trace_refusal.py](trace_refusal.py) wraps private `reserve` and the named stage
boundaries around the original compact Runtime/source IPC plus Reader probe.
It stores at most 32 failure records with at most 32 scalar call-site entries
each. It retains no frames, roots, sampled locals or exception objects. Weak
error references and the bounded sanitized scalar tuple add no graph owner.
No ledger counters, limits, return values or failures are altered. These
diagnostic allocations are outside the reported resource account, so this is
not an inclusive physical-resource/RSS or timing measurement.

The final two replays run serially under the existing shared advisory lock,
one per Python3.14.8/3.11.17, with GC disabled. Each verifies all 79 loaded
source hashes against the immutable 262 Mesh /212 Observer input inventory.
The original dynamic probe is separately pinned byte-for-byte. Eight protected
inputs and all 52 prior field-reference artifacts remain unchanged. The
[source bindings](results/source-bindings.json) and [receipt](receipt.json)
bind those inputs, exact script bytes, reports and logs.

Earlier exploratory observations remain separate: an initial 16-frame reserve
trace identified the packed allocator but did not prove fatal propagation;
the next 32-frame/weak-identity trace proved Python3.14 propagation but could
not cross Python3.11's intentional error replacement. Their exact script
snapshots and reports are retained. Only the final script supplies the complete
two-version propagation statements above. No functional/canonical suite or
unchanged twelve-screen qualifier was rerun for this diagnostic.

Next ownership questions

The source retains baseline index duplicate markers and prepared index buckets
through map construction. Retiring those containers earlier would require the
remaining rows to own every borrowed canonical key buffer, with separate credit
through constructor/error cleanup. The packed builder also retains its leaf
control list through recursive tree construction. Any earlier control retirement
must prove that parent edges have acquired ownership before the leaf owner drops,
including rollback and epoch checks. These are candidate lifetime changes, not
an approved estimate reduction or a claim that either will deliver 2,000 rows.

Full-only fixtures have 14,010 membership cells, not dense nine-field or
simultaneous full/active/slow-peer coverage. The private packed arena is
test-owned; native owner storage is separately accounted. Original private
nonce/native pin/proof-carrier/synthetic-clock exclusions remain. Both runs fail
before proof scratch; no currentness, 2s/15s execution or recovery is claimed.
CPU hard failures, inclusive resource/RSS, deliverable2k/dense/recovery,
ordinary authenticated SyncReader route, populated native/fixedSSH and immutable
installed-pair/producer gates remain open. Old findings stay closed. No sibling,
service/provider, ID/schema/version/artifact, rollout or Git attribution cleanup
action occurred; HOLD remains.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-field-reservation/trace_refusal.py --mesh .cache/field-ref-qualified-13f-b6/mesh-13f27e2 --observer .cache/field-ref-qualified-13f-b6/observer-7e496b2 --output .cache/new-reservation-trace.json
```
