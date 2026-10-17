# Compact normalization phase ownership

Mesh runtime `13876e6d723ad3ff5511c12e2900e7dc34f2c778` retires duplicate-key
storage at its actual phase boundary. The source gate passes 391 tests without
skips; 29 compact tests pass on Python 3.14.8 and 3.11.17 with GC disabled during
operations. This is a private implementation change. Shared APIs, callback
contracts, canonical tables/roots, frozen schemas, lock, authority, package
version and selected a7/a23 remain unchanged.

The paired capacity screen still **fails at 2,000 rows** on both default and
private packed backends. All four 500-row cases admit a baseline and two later
generations with fresh heads. Each has 968,569 fewer accounted peak heap bytes
than the [prior pinned screen](../2026-10-17-reader-capacity/README.md).
No CPU, physical heap, RSS, recovery, native fleet or producer acceptance follows.

The change and ownership proof

Previously `CompactState.adopt` accumulated `512 + len(encoded_key)` in the
transaction budget for every normalized operation. Each phase's duplicate set
was cleared, but its allowance survived through the profile callback and final
root check. The set retained only encoded markers. The new phase dictionary
retains each marker's original tracked key Atom, keeping its payload and encoded
credit live while the marker is used.

Each dictionary prepays 4,096 fixed bytes plus 256 bytes per slot, including
resize overlap. Its key Atoms own their separate intrinsic/encoded charges;
dictionary entries alias those original encoded buffers. Baseline record
Operation/list storage prepays another 512 bytes per entry until alias
definitions finish and the operations clear. Other baseline phases have only
the bounded current operation already covered by the existing stage control
allowance. Delta operations instead keep 512 bytes each in the transaction
budget through callback, finish or rollback.

The foreign iterator closes before phase storage retires. On failure, exception
frames are sanitized, actual record operation references clear, and then the
phase dictionary drops before its reservation closes. Phase reservations are
local owners, so a reentrant input-owner retirement cannot refund their live
storage. Group/alias staging, callback patch credit and affected-identity staging
retain their previous lifetimes. There is no new roster pass or query path.

Four new tests cover callback-entry capacity, owned marker topology through
foreign/reentrant close, retained delta operations during failed callback, and
at-limit refusal before dictionary insertion. The topology test checks that
markers alias charged Atoms and dictionary resize storage remains prepaid; it
uses private accounting inspection and scalar observations. Actual public errors
remain held with cyclic GC disabled.

Only the callback-entry resource assertion and delta rollback control were
overlaid on the old runtime, checkpoint `f0924e457230c49d04d3e5983476766d4c58a4af`
(runtime bytes d013d2a). Each Python reproduces exactly one expected assertion
failure: 128 metadata entries add 99,986 bytes to callback-entry transaction
credit, exceeding the 32,768-byte bound. The delta control passes. All 29 tests
pass on the immutable new export; no missing-private-helper failure is counted
as a before regression.

The paired intake evidence

The Observer input remains immutable
`84d284dab04b68ae0e9070335d017e85564f2ba9`; the independent Observer patch-builder
investigation is excluded. The original [intake probe](../2026-10-17-reader-capacity/probe_reader_intake.py)
and [scalar audit](../2026-10-17-reader-capacity/profile_intake.py) are reused
byte-for-byte. [The runner](qualify_phases.py) verifies 260 before and 260 after
Mesh inputs, 211 Observer inputs and eight protected inputs against Git blobs.
Only the declared before test overlay differs from its export. Inventories stay
stable through the serial run under the shared CPU advisory lock.

| Rows/backend | Python 3.14.8 peak heap | Python 3.11.17 peak heap | Outcome |
| --- | ---: | ---: | --- |
| 500 default | 46,627,309 | 47,086,685 | Baseline + two generations + fresh heads pass |
| 500 private packed | 39,725,253 | 40,184,629 | Same |
| 2,000 default | 67,095,892 | 67,101,606 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,096,828 | 67,101,794 | Same |

All eight screens retain actual failed-operation errors, keep heap below
67,108,864 bytes and encoded retention below 33,554,432 bytes, and finish with all
six Reader ledger counters zero. Encoded peaks remain 9,363,952 / 7,168,551 bytes
at 500 and 12,485,928 / 11,950,591 bytes at 2,000 for default / packed storage.
The native owner's separate account returns to its base on close.

The unchanged additional scalar audit on packed 2,000/Python 3.14 reaches 10,575
token writes before a refused `_Decoded` retain, versus 9,153 in the prior audit.
The old 3,862,069-byte cumulative normalizer duplicate/operation charge is absent
at this later failure. Observer cumulative token/index staging has progressed to
17,406,450 / 11,315,921 bytes; generic group staging remains 5,216,000 bytes.
These are charged reservations and progress observations, not proof of physical
duplicates or permission to lower estimates. Scalar allocation bins all return
to zero. No instrumented timing is used for a performance claim.

Bounds and remaining gates

The probe uses an actual disposable collection-disabled native Runtime and
compact owned source IPC, with source intake and Reader on one original
32 MiB encoded / 64 MiB heap ledger. The native owner has a separate account.
The full-only synthetic workload has 3,510 / 14,010 membership cells at 500 /
2,000 rows; it is not dense nine-field coverage. The packed arena is explicitly
test-owned and closes after source/cache cleanup.

Confirmation uses a disclosed test nonce/native pin/proof carrier with extra
prepaid fixture credit and synthetic Reader clock. All 2,000-row cases fail
before this proof scratch. Neither ordinary network Reader/authenticated route,
relay/controller intake, absolute 2s/15s execution, inclusive process memory/RSS,
matched CPU, delivered 2,000-row cold/recovery, populated native/fixed SSH nor
immutable installed-pair acceptance is exercised. SyncReader remains a pending
public implementation. The existing producer CPU hard failure is unchanged.

The canonical command was `rtk proxy .venv/bin/python scripts/check.py`: 33 lock
inputs, 25 packaged schemas, 116 design and 169 delivery checks, 391 standalone
runtime tests, no skips, Ruff pass. `--native`, `--check-sources`, wheel and CPU
gates were not run. An initial exploratory canonical log predates the final
dictionary-drop ordering and stays in `.cache`; only `canonical-final.log` is
part of this evidence. The new scripts and local document links are checked
separately. Prior frozen evidence remains unchanged.

Reproduce from the owning repository with the same Python environment and
immutable Observer export:

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-normalization-phases/qualify_phases.py --after 13876e6d723ad3ff5511c12e2900e7dc34f2c778 --observer .cache/observer-row-reuse-84d284d --observer-repo /home/bryan/code/agent-observer-active-feed --output .cache/new-normalization-phase-run
```

[receipt.json](receipt.json) pins the [results](results/qualification.json),
canonical log, scripts, input inventories, prior receipt and every new artifact.
