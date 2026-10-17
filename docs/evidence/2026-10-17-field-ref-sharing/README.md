# Compact field-reference ownership

Mesh runtime `13f27e25c46e1fd3da664975e964104a56fd6dbf` reuses exact stage-owned
record references in compact field-token staging. Canonical standalone checks
pass 407 tests without skips. Immutable focused workers pass 72 Mesh and 64
Observer methods on each Python version, with GC disabled. This is a private
ownership change: no public callback/DTO/API, encoded wire/schema/ID, version,
authority, cap, estimate, selected a7/a23 or sibling change.

The exact joined Observer runtime remains
`b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f`, exported from its evidence
`7e496b2b0555a76e7c381b1d5e6cada63f441c7b`. Small intake results remain correct;
**all four 2,000-row baseline admissions still refuse** at the unchanged cap.
No producer, CPU or inclusive physical-resource acceptance follows.

Ownership and validation

Previously each generic field group minted its own packed full record-reference
buffer, even when normalization already owned that exact identity/birth pair.
Compact staging now checks the full reference shape and canonical bytes, then
borrows an existing retired reference or the exact AFTER alias-definition owner.
The lookup uses the record's complete identity and birth plus the configured
alias/birth paths. An alias number alone cannot select another record or birth.

An unmatched reference retains the original independently owned fallback and
ordinary field validation. Expanded admission keeps its original path. Current
record/birth checks, exact token checks, independent index/native roots and
membership/seal validation are unchanged. There is no callback admission reuse,
roster scan, new cache, key mutation or early refund. Group metadata allowances
remain unchanged; the change removes duplicate retained owners rather than
reducing an estimate.

An independent prepayment covers transient comparison bytes on both heap and
encoded ledgers, through their last local alias and failure unwind. Returned
keys already have a stage/retired owner; callback patch graphs and their credit
remain live through finish or rollback. A remove/reinsert that reuses an alias
keeps the retired old identity/birth owner distinct from the new AFTER owner.

Four new methods check exact owner identity on both default/private packed
backends with expanded index/root parity; retired-reference and same-transaction
alias reuse with distinct full identity/birth; wrong-birth/bool/foreign-host
rejection with confirmed-root rollback and denied acquire; and refusal before
constructing comparison bytes when encoded credit is exhausted. Existing
workspace retirement, reentrant schema/source close and held-error tests remain.

On immutable before runtime `231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc`, only the
final test file is overlaid, and only the new two-backend topology method runs.
It produces two expected non-sharing assertions per Python after successful
native-tag/index parity, without errors or skips. Both implementations admit
the same valid fixture; this is not an old authority/output defect.

Exact gates and intake

[The qualifier](qualify_fields.py) verifies 262 before/262 after Mesh inputs,
212 Observer inputs and eight protected inputs against Git. It preserves all
56 earlier [index-join artifacts](../2026-10-17-profile-index-join/receipt.json),
pins the original Observer patch/group/index receipts, and uses the unchanged
actual compact Runtime/source IPC plus Reader probe. Separate worker processes
preserve the projects' same-named test-helper namespaces. Imported Git pins
match: 37 per before test, 41 per Mesh worker, 75 per Observer worker and 80 per
intake screen. Inventories and runner bytes stay stable through qualification.

The canonical command is `rtk proxy .venv/bin/python scripts/check.py`: 33
locked inputs, 25 identical packaged schemas, 116 design, 169 delivery and 407
standalone runtime checks, zero skips and Ruff pass. Native/sibling-source,
wheel, CPU and installed-package gates are excluded. The final immutable focused
qualification has 136 methods per Python 3.14.8/3.11.17, all passing without
errors or skips under disabled GC.

Twelve original intake screens run serially under the shared advisory lock.
Source intake and Reader staging/material use the same original 32 MiB encoded /
64 MiB heap ledger; native owner storage remains in its separate account. All
six final Reader counters are zero in every case and native owner returns to
its separate base, with real errors held under disabled GC.

| Rows/backend | Python 3.14.8 charged heap peak | Python 3.11.17 charged heap peak | Outcome |
| --- | ---: | ---: | --- |
| 100 default | 14,906,203 | 14,951,363 | Baseline + two generations + fresh heads pass |
| 100 private packed | 13,673,500 | 13,718,740 | Same |
| 500 default | 35,932,113 | 36,146,873 | Same |
| 500 private packed | 28,527,235 | 28,742,075 | Same |
| 2,000 default | 67,108,005 | 67,108,591 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,108,660 | 67,108,813 | Same |

Compared with the exact b6/231 [prior join](../2026-10-17-profile-index-join/README.md),
default-backend peaks are unchanged. Successful packed100 peaks fall 40,287 /
40,991 bytes on Python 3.14 / 3.11; packed500 peaks fall 187,199 / 187,903 bytes.
Completed small-case encoded peaks are unchanged. Failed packed2k progresses
to a different point: its Python3.14 encoded peak is 14,954,968 rather than
15,158,657 bytes; its heap peak is 160 bytes higher. No savings, available
headroom or successful capacity claim is made from failed cases. These are
charged peaks, not physical/RSS or CPU measurements.

One additional packed2k/Python3.14 run uses the original private scalar audit
unchanged. It reproduces the 67,108,660-byte charged peak/refusal and final zero
bins/counters. The callback emits all 18,000 field DTOs, and generic field-group
charges reach all 2,000 groups (1,744,000 bytes, unchanged allowance). Unlike the
prior join, this audit records no failing `ledger.retain` call; it does not trace
the final reservation's underlying caller. No more precise method attribution
or safely reducible allowance is inferred. Cumulative stage charges are not a
unique physical topology census; audit timings are excluded.

Diagnostics and limits

Initial new-test setup incorrectly treated an ordered index as a Merkle root
and used a member-bearing fixture with the nonmember proof scaffold. Correcting
those test helpers gives the final parity and rollback tests; no runtime change
was needed for those setup errors. An initial before overlay asserted inside
the admission boundary, which wrapped its assertions. Its test bytes/log remain
under `diagnostics/` and are excluded. Final topology assertions occur after
successful admission/parity and reproduce only the two named failures. An
unused queued scalar audit was stopped while waiting for the lock; it produced
no profile result. The later completed audit remains separate from the twelve
qualification screens.

Full-only fixtures contain 710 / 3,510 / 14,010 membership cells, not dense nine
fields or simultaneous full/active coverage. The private packed arena is
fixture-owned. Private nonce/native input pin/proof carrier, prepaid fixture
scratch and synthetic Reader time remain disclosed; large cases fail before
proof scratch.

Ordinary SyncReader/authenticated selected route, controller/relay intake,
absolute 2s/15s timing, inclusive physical heap/RSS, CPU, dense/deliverable2k
cold/recovery, populated native/fixed SSH and immutable installed-pair/producer
acceptance remain open. Prior hard CPU failures and fallback-without-delivery
results remain failures. Old source/controller findings stay closed. No API
permission gate is reopened; no artifacts/IDs, services/providers, selection,
rollout, sibling edits or attribution cleanup occurred. Git HOLD remains.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-field-ref-sharing/qualify_fields.py --observer-repo /home/bryan/code/agent-observer-active-feed --python311 /home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python --output .cache/new-field-ref-qualification
```

[receipt.json](receipt.json) pins the scripts, reports, inventories, canonical log,
scalar audit and diagnostics. [qualification.json](results/qualification.json)
contains the exact immutable before/after pair and all twelve screen reports.
