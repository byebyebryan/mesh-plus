# Private compact group ownership

Runtime `4301339515e84f2edb63c88a886380bcde56c621` shares the exact validated
record-ref and cohort owners used by compact membership groups. It also gives
each retained canonical group marker explicit heap **and encoded-byte** ownership.
The canonical gate passes 397 tests without skips; 35 compact tests pass on
Python 3.14.8 and 3.11.17, with GC disabled during operations. This is a private
implementation change; no shared API, callback, wire/schema/ID, lock, authority,
package version, selected a7/a23 or production workflow changes.

The capacity blocker remains: all four 2,000-row cases still refuse baseline
admission under the original 64 MiB heap cap. Four 500-row cases complete a
baseline, two later generations and fresh native heads. Relative to the
[phase checkpoint](../2026-10-17-normalization-phases/README.md), their accounted
peak heap is lower by 805,763 bytes on Python 3.14 and 821,683 on Python 3.11.
No performance, RSS, physical-process memory, recovery or producer acceptance is
claimed.

Ownership and validation

`_ref` first checks exact identity, side, record existence and birth. It then
requires the canonical value of the matching generic BEFORE/AFTER alias ref to
equal that record ref. Groups borrow this already owned immutable Atom instead
of freezing another record-ref graph. A removed and reinserted alias therefore
retains distinct before/after identities and births. This is private allocation
sharing, not admission reuse or current authority. All proof, token, index,
native-root and lease checks remain independent.

Cohort Atoms are shared in a stage-local dictionary with at most 64 entries,
covering the bounded before/after cohort union. A new slot prepays 256 metadata
bytes; each actual Atom retains its own intrinsic and encoded charge. Repeated
cohort input is still strictly owned/validated before lookup. No whole roster
scan is added to sparse operations.

The marker's canonical bytes are formed from the two owned canonical values:
`[cohort, identity, birth]`. Construction prepays temporary concatenation and
encoded overlap, then transfers actual ownership into a tracked PackedAtom.
The dictionary key and ordered intent list alias that exact buffer. The fixed
1,024-byte group metadata allowance remains; marker payload formerly included
as `len(marker)` heap allowance now has its actual object/buffer accounting and
encoded charge. This is not an estimate reduction or cap increase. The ordered
aliases clear before marker owners; cohort pools and group metadata survive
callback, independent root checks, rollback and reentrant retirement.

Six new methods check both-backend sharing and expanded index parity, exact
canonical markers including escaping/Unicode/object keys, sided alias rebirth,
encoded-limit refusal before buffer construction, reentrant callback retirement
with charged receive storage, and order-alias retirement before marker credit.
The last uses a private scalar destructor/accounting hook; all actual errors are
held with GC disabled. Existing strict raw, masks, duplicate groups, token-only
updates, roots, sparse visits and rollback tests remain enabled.

Only the two-backend sharing method is overlaid on old runtime
`13876e6d723ad3ff5511c12e2900e7dc34f2c778`. Both Pythons reproduce two expected
topology assertions: four separately retained record-ref Atoms instead of the
new two shared owners. Native tags and expanded index roots match before that
assertion. This demonstrates the intended allocation change, not a prior output
or authority defect. The new immutable export passes all 35 methods per Python.

Same pinned intake workload

Observer stays at `84d284dab04b68ae0e9070335d017e85564f2ba9`; its independent
patch-builder work is excluded. The [runner](qualify_groups.py) reuses the
[original intake probe](../2026-10-17-reader-capacity/probe_reader_intake.py) and
[scalar audit](../2026-10-17-reader-capacity/profile_intake.py) unchanged. It
verifies 260 before and 260 after Mesh inputs, 211 Observer inputs and eight
protected inputs against Git blobs. The declared before test overlay is the only
export deviation. All measured inputs stay stable under the shared CPU advisory
lock; prior 27 phase-checkpoint artifacts remain unchanged.

| Rows/backend | Python 3.14.8 peak heap | Python 3.11.17 peak heap | Outcome |
| --- | ---: | ---: | --- |
| 500 default | 45,821,546 | 46,265,002 | Baseline + two generations + fresh heads pass |
| 500 private packed | 38,919,490 | 39,362,946 | Same |
| 2,000 default | 67,108,560 | 67,097,918 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,084,946 | 67,098,008 | Same |

All eight screens finish with six Reader ledger counters zero, with actual
failure objects held and GC disabled. Heap remains below 67,108,864 and encoded
retention below 33,554,432 bytes. Encoded peaks are 9,363,952 / 7,168,551 bytes at
500 and 12,490,114 / 11,954,777 bytes at 2,000 for default / packed storage. The
native owner's separate account returns to its base after close.

The separate scalar audit on packed 2,000/Python 3.14 observes 12 live tracked
Atoms versus 4,010 in the prior audit, consistent with sharing the cohort owners.
PackedAtom count remains 14,001: marker buffers replace group record-ref buffers.
Their encoded bytes grow from 7,371,952 to 7,747,952; the ordinary Atom encoded
bytes fall from 376,484 to 4,670. These are tracked allocation classes, not RSS
or an assertion that every staging reservation measures unique physical bytes.

It reaches 11,763 token writes before a refused `_Decoded` retain, versus 10,575
previously. At this later failure the callback's cumulative token/index charges
are 19,361,898 / 12,586,947 bytes. Fixed generic group metadata is 4,096,000 bytes,
with marker payload tracked separately; cohort-pool metadata adds 512 bytes.
The failure has decoded 8,370,588 and reserved 58,664,378 bytes. All audit bins
and six final counters return to zero. No instrumented timing enters a CPU claim.

Scope and reproduction

The actual disposable compact Runtime/source IPC and Reader share one original
32 MiB encoded / 64 MiB heap ledger; native owner memory has a separate account.
The full-only synthetic 500/2,000 workload has 3,510/14,010 membership cells,
not dense nine-field coverage. The packed arena is explicitly test-owned. A
disclosed test nonce/native pin/proof carrier has extra prepaid fixture scratch
and synthetic Reader time; 2,000-row admission fails before proof scratch.

Ordinary SyncReader/authenticated selected route, relay/controller intake,
absolute 2s/15s execution, inclusive physical heap/RSS, matched CPU, delivered
2,000-row cold/recovery, populated native/fixed SSH and immutable installed pair
remain unqualified. Prior CPU hard failures and closed controller/source findings
remain bound to their original sources. Observer source, services, providers,
sibling projects, artifacts, IDs and rollout were untouched; attribution cleanup
HOLD remains.

`rtk proxy .venv/bin/python scripts/check.py` passes 33 locked inputs, 25 packaged
schemas, 116 design and 169 delivery checks, 397 standalone tests/zero skips and
Ruff. Native/source-parity/wheel/CPU gates were not run. New evidence scripts and
local links are checked separately.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-group-ownership/qualify_groups.py --after 4301339515e84f2edb63c88a886380bcde56c621 --observer .cache/observer-row-reuse-84d284d --observer-repo /home/bryan/code/agent-observer-active-feed --output .cache/new-group-ownership-run
```

[receipt.json](receipt.json) pins the [results and inventories](results/qualification.json),
canonical log, scripts, exact prior receipt and every new artifact.
