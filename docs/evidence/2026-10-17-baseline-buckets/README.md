# Baseline duplicate registry and bucket ownership

Mesh runtime `03a681f95a609b20eaa20134f7241d3d14d441a6` gives compact baseline
index rows their own key owners and per-index metadata credit. After every
write/remove has passed duplicate and schema checks, the duplicate registry can
retire before index construction. Each completed bucket retires before the next
constructor. Expanded admission, compact deltas and reserved-rule processing
keep their previous paths and allowances.

Canonical checks pass 411 tests without skips. Immutable workers pass 76 Mesh
plus 64 Observer methods on each Python3.14.8/3.11.17 with GC disabled. The
exact Observer runtime remains `b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f`, exported
from its `51b0f27559b2b1553ffb60d04992ba90e639d873` evidence commit.
**All four 2,000-row baselines still refuse admission at the unchanged cap.**
This is private lifetime work, not capacity, CPU or producer acceptance.

Ownership boundaries

Previously unordered bulk rows kept only encoded key bytes; the duplicate
registry kept the corresponding packed Atom alive. Retiring that registry alone
would refund the encoded buffer owner while the row still borrowed its bytes.
New compact baseline rows retain exact key/value Atoms. Ordered keys keep their
decoded Atom; unordered keys keep their packed Atom. The private row owner
checks both Atom types and their exact ledger before append. Canonical key
buffers stay tracked when duplicate marker tuples and their dictionary drop.

The duplicate registry still prepays 4,096 bytes plus 256 per key. A separate
8,192-byte registry reservation covers at most 32 descriptor index buckets,
their control objects and dictionary resize overlap. Each bucket prepays 256
bytes and 128 per row before tuple/list growth, preserving the previous
per-bucket/per-row allowances. The new fixed registry prepayment is additional;
no estimate is reduced. Every pending key/value payload retains its existing
heap and encoded charges independently.

Only after the complete patch has passed duplicate/schema/entry checks does
`finish_seen()` drop the actual duplicate dictionary and then its reservation.
Buckets build in original insertion order, with no roster-sized name snapshot.
Unordered constructors borrow each owned key's canonical bytes; ordered
constructors receive owned keys directly. On successful return, local row
aliases drop before that bucket's rows and credit retire. On failure, the
existing error boundary sanitizes constructor frames before the active and
remaining bucket owners close. Caller patch graphs and credit stay held through
generic finish or rollback. Key/value ownership is never transferred from the
callback, and no reservation grants semantic admission or current authority.

All retirement is in material admission. Nonce confirmation gets no new cleanup
or roster work. Sparse delta/read behavior is unchanged. The separately proposed
packed-tree grafted-control lifetime change is **not** part of this source.
Public callbacks/DTOs/API, wire/schema/IDs, lock, authority, version and selected
a7/a23 remain unchanged; no sibling source is edited.

Tests and metadata census

Four new methods cover both backend root/index parity and stable construction
order with the duplicate registry already retired; separately owned canonical
key buffers and unchanged encoded credit after retirement; per-bucket weak
retirement before the next constructor/field phase while caller credit stays
held; and constructor failure/reentrant source close with active bucket credit,
receive credit, same-ledger sibling and held public errors. Existing duplicate,
rollback, alias/birth, encoded-capacity and workspace/refund tests remain.

The direct storage test exercises 32 indexes/4,096 rows, refuses new-bucket and
row growth before mutation at the exact limit, rejects late append after the
seen phase, and finishes with six ledger counters zero under disabled GC. Only
the final source test file is overlaid on before runtime
`13f27e25c46e1fd3da664975e964104a56fd6dbf`; the new two-backend construction-phase
method gives two expected old-storage assertions per Python, after successful
native-tag/index parity. This is not an old output/authority defect.

[check_storage.py](check_storage.py) adds ten additional metadata-bound
checkpoints per Python from one through 4,096 rows, including all Reservation
instance dictionaries, amount-integer overlap, bucket/list/tuple storage and
dictionary/list resize overlap. Key/value graphs are excluded from that
metadata sum because their actual Atoms remain ledger-owned. At 4,096 rows,
the measured metadata bound is 899,360 ->341,920 bytes on Python3.14 and
833,832 ->309,152 on Python3.11; metadata credit is 1,593,344 ->540,672 bytes.
The 1,052,672-byte seen reservation drops only after its dictionary drops;
encoded credit is unchanged. These are private metadata bounds and credit,
not unique process-memory/RSS savings. All checkpoints fit their credit and
final six counters are zero. Each census has 30 imported Git pins.

Exact qualification

[The qualifier](qualify_buckets.py) verifies 262 before/262 after Mesh inputs,
212 Observer inputs and eight protected inputs against Git. It preserves all
52 prior field-reference artifacts and 16 reservation-trace artifacts, plus
the pinned Observer patch/group/index receipts. Before tests import 37 Git
inputs; after workers import 41 Mesh /75 Observer inputs. Separate workers
preserve the projects' same-named fixture namespaces. All 140 methods per Python
pass without failures/errors/skips under disabled GC.

The canonical command is `rtk proxy .venv/bin/python scripts/check.py`: 33
locked inputs, 25 identical packaged schemas, 116 design, 169 delivery and 411
standalone runtime checks, zero skips and Ruff pass. Native/sibling-source,
wheel, CPU and installed-package gates were not run.

The original actual compact Runtime/source IPC plus Reader intake probe runs
twelve serial screens under the existing shared advisory lock. Intake,
staging and Reader material share the original 32 MiB encoded /64 MiB heap
ledger; native owner storage remains separately accounted. All six Reader
counters finish at zero, native owner returns to its separate base, and actual
errors remain held with GC disabled. All 80 imported hashes per screen match
the immutable pair. Inventories and runner bytes stay stable through the run;
the qualifier's exclusion of source edits refers to that immutable execution.

| Rows/backend | Python3.14.8 charged heap peak | Python3.11.17 charged heap peak | Outcome |
| --- | ---: | ---: | --- |
| 100 default | 14,906,203 | 14,951,363 | Baseline +two generations +fresh heads pass |
| 100 private packed | 13,677,670 | 13,718,740 | Same |
| 500 default | 35,932,113 | 36,146,873 | Same |
| 500 private packed | 28,527,235 | 28,742,075 | Same |
| 2,000 default | 67,108,517 | 67,107,767 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,108,660 | 67,108,667 | Same |

Completed-case peaks are unchanged from the
[exact b6/13 pair](../2026-10-17-field-ref-sharing/README.md), except packed100
on Python3.14 increases by 4,170 bytes with the new fixed registry prepayment.
Completed-case encoded peaks are unchanged. There is no overall peak saving
or CPU claim. Different failed-case peaks are not available headroom or a
capacity improvement.

New failure traces

Two additional instrumented packed2k replays use the
[unchanged bounded tracer](../2026-10-17-field-reservation/trace_refusal.py).
Each records one failed 256-byte control reservation and the same weak error
escaping `_field_patch`, `_patch` and `_finish`, with 79 imported pins and final
six counters zero. On Python3.14 the packed `$fields` branch path and ledger
values exactly match its prior trace: decoded11,574,350 +reserved55,534,310
+256 =67,108,916 bytes. On Python3.11 the old ordered-index refusal is passed;
it now reaches a packed `$fields` leaf control: decoded9,974,708
+reserved57,133,959 +256 =67,108,923 bytes. Both totals exceed the unchanged
67,108,864-byte cap. The traces keep new source provenance; prior13's different
Python3.11 ordered-node trace is not relabeled. Instrumented timing is excluded,
and neither valid refusal permits an estimate reduction.

Limits and reproduction

Raw unittest before-subtest logs preserve their original trailing-space header
lines. They are pinned without trimming; source/scripts/Markdown/JSON whitespace
checks exclude those raw log lines. No setup failures or earlier suites are
reassigned to these final runs. [receipt.json](receipt.json) pins the complete
[reports and inventories](results/qualification.json), scripts, census, traces,
canonical log and unchanged upstream evidence.

Full-only fixtures contain 710 /3,510 /14,010 membership cells, not dense nine
fields or simultaneous full/active/slow-peer coverage. The packed arena is
fixture-owned. Original private nonce/native pin/proof carrier, prepaid fixture
scratch and synthetic Reader time remain disclosed. Large cases fail before
proof scratch, so no currentness or recovery is claimed for them.

CPU hard failures, inclusive physical resources/RSS, dense/deliverable2k
cold/recovery, absolute2s/15s execution, ordinary authenticated SyncReader route,
populated native/fixedSSH and immutable installed-pair/producer gates remain
open. Old findings stay closed; no IDs/artifact allocation, services/providers,
selection, rollout, sibling edits or attribution cleanup occurred. HOLD remains.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-baseline-buckets/qualify_buckets.py --observer-repo /home/bryan/code/agent-observer-active-feed --python311 /home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python --output .cache/new-baseline-bucket-qualification
```
