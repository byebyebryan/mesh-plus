# Compact index workspace phases

Mesh runtime `231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc` gives compact index and
rule scratch explicit ownership and bounded growth. The canonical gate passes
403 tests without skips; 68 focused reconstruction/compact/ordered/packed/index
methods pass on Python 3.14.8 and 3.11.17 with GC disabled during the new tests.
No shared API, callback DTO, wire/schema/ID, lock, authority, version, selected
a7/a23 or production workflow changes.

The pinned Observer84 screen still **fails 2,000-row baseline admission inside
the callback**, before the new generic index phase is reached. Observer's newer
grouped/coalesced patch prototype is excluded until its immutable handoff. Its
reported complete callback followed by the old generic metadata refusal is
provisional evidence on its own older tuple, not an accepted pairing here.

Ownership change

Previously `_patch` prepayed `1024 + 256 * all_patch_entries` at once, including
field-token DTOs already retained by the caller, and held an index duplicate
registry through field processing and later rules. Compact admission now owns
the actual new containers in independent index and reserved-rule workspaces.
Each prepays 4,096 bytes before creating dictionaries, then 256 per duplicate
marker, 256 per new bulk bucket and 128 per bulk row before insertion/append.
Tracked key/value Atoms retain their own payload and encoded charges.

The duplicate registry still spans removals and inserts. Removals precede
inserts, so final declared entry capacity remains sufficient. Ordered keys keep
their original decoded Atom; unordered markers keep the packed owner of the
exact canonical buffer. Bulk lists drop before the seen-key owners, after the
ordered/Merkle constructor and its own scratch cleanup return. Error frames are
sanitized before local aliases and workspace credit retire. A reentrant source
retirement cannot close another workspace's reservation or refund its live data.

Reserved `$rules` keys cannot collide with declared index names. Their later
phase independently checks duplicates across changed and removed rules. The
original returned patch and DTO graphs remain caller-prepaid through finish or
rollback; no ownership or admission capability transfers from them.

Compact fixed layout/current-token scratch prepays `4096 + 256 * columns`.
Per-record field lists and offsets keep their existing `512 + 40 * columns`
allowance. An early exact record/field duplicate check bounds each borrowed
reference list by the descriptor's fields before append; final changed-token
masks are still recomputed from old/new values. Derived-membership,
affected-scope and invalidation metadata keeps its per-entry allowance.
Expanded admission retains its previous whole-patch prepayment and late field
duplicate behavior. Its ordered/unordered baseline/delta outputs are checked
against compact outputs; this is not new expanded resource acceptance.

This replaces blanket eager allocation with charged containers and a proved
reference-list bound. It does not lower caps or treat cumulative stage charges
as unique physical allocations. Sparse operations add no unchanged-roster pass.

New tests and source gate

Six methods verify index workspace retirement before field processing while
caller credit stays held; bounded duplicate-token rejection; confirmed-material
rollback on index/rule duplicates; ordered/unordered baseline and delta parity
with the expanded route; actual container sizes/resize overlap and refusal
before slot/row growth; and reentrant schema failure with charged receive data,
same-ledger sibling isolation and immediate weak retirement. Actual public
errors are retained with GC disabled. Existing compact tests also exercise the
new index path with the private packed backend.

Only the duplicate-reference-list method is added to old runtime
`4301339515e84f2edb63c88a886380bcde56c621`. It reproduces one expected assertion
failure per Python: old input is rejected at eager `sync_decoded_capacity`,
where the new bounded path rejects `sync_duplicate_field_token` at the second
item. Both reject invalid input; this is not a prior output/authority bypass.
The fixture caller prepays the 16,384-reference tuple, with a 2 MiB test budget.
An initial 512 KiB setup could not reach this phase and is excluded.

The final immutable focused suite has 68 methods per Python, including 35 compact
and six new workspace methods. The canonical command was
`rtk proxy .venv/bin/python scripts/check.py`: 33 locked inputs, 25 identical
packaged schemas, 116 design, 169 delivery and 403 standalone runtime checks,
zero skips and Ruff pass. Native/source-parity/wheel/CPU gates were not run.
An initial exploratory invocation named a nonexistent index test module; it is
not a gate result. New evidence scripts and local links are checked separately.

Pinned intake results

[The qualifier](qualify_indexes.py) uses immutable Observer
`84d284dab04b68ae0e9070335d017e85564f2ba9` and the original
[intake probe](../2026-10-17-reader-capacity/probe_reader_intake.py) and
[scalar audit](../2026-10-17-reader-capacity/profile_intake.py) byte-for-byte.
It verifies 260 before/262 after Mesh inputs, 211 Observer inputs and eight
protected inputs against Git. Only the declared before test file is added to
its export. Inventories and runner bytes remain stable through the serial
shared-advisory-lock qualification; 27 earlier group artifacts stay unchanged.

| Rows/backend | Python 3.14.8 peak heap | Python 3.11.17 peak heap | Outcome |
| --- | ---: | ---: | --- |
| 500 default | 44,268,370 | 44,711,042 | Baseline + two generations + fresh heads pass |
| 500 private packed | 37,050,691 | 37,494,147 | Same |
| 2,000 default | 67,108,560 | 67,097,918 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,084,946 | 67,098,008 | Same |

All eight finish with six Reader ledger counters zero and held errors under
disabled GC. Original 64 MiB heap/32 MiB encoded limits remain enforced. The
completed 500-row default peaks are lower than the
[group checkpoint](../2026-10-17-group-ownership/README.md) by 1,553,176 / 1,553,960
bytes on Python 3.14 / 3.11; packed peaks fall 1,868,799 bytes on both. Encoded
peaks remain 9,363,952 / 7,168,551 bytes at 500 and 12,490,114 / 11,954,777 at
2,000 for default / packed. Native owner returns to its separate account base.

The extra packed2k/Python3.14 scalar audit reproduces the previous boundary:
11,763 token writes, `_Decoded` retain refusal at decoded 8,370,588 / reserved
58,664,378 bytes, all bins and final counters zero. The new `_patch` allocation
is not reached. This cannot prove whether the completed new Observer patch will
fit; that exact pair still needs qualification after immutable source handoff.

Limits and reproduction

The actual disposable compact Runtime/source IPC and Reader share one original
ledger; native owner has a separate account. Full-only 500/2,000 fixtures have
3,510/14,010 cells, not dense nine-field coverage. The packed arena is test-owned.
Private nonce/native pin/proof carrier, prepaid fixture scratch and synthetic
Reader time remain disclosed. Large cases fail before proof scratch.

Ordinary SyncReader/authenticated route, controller/relay intake, absolute2s/15s,
inclusive physical heap/RSS, matched CPU, delivered 2,000-row cold/recovery,
populated native/fixed SSH and immutable installed-pair/producer acceptance stay
open. No sibling edits, service/provider actions, artifact/ID allocation,
selection, rollout or attribution cleanup. Earlier CPU hard failures and closed
source/controller findings remain bound to their original sources.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-index-workspace/qualify_indexes.py --after 231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc --observer .cache/observer-row-reuse-84d284d --observer-repo /home/bryan/code/agent-observer-active-feed --output .cache/new-index-workspace-run
```

[receipt.json](receipt.json) pins the [results and inventories](results/qualification.json),
scripts, canonical log, prior receipt and every new artifact.
