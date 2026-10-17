# Observer patch and Mesh index workspace join

The exact pair is Mesh runtime `231a631337bb8c4d5feb7cd7d7c8193ef29b5ffc`
(exported from evidence `103f3b3056d5f88d4e72e6556e7af6e8ff2e7aed`) and Observer
runtime `b6ce8428b7f9d451bc9e99ca6f8e2943c656c23f` (exported from evidence
`1cc8217d4f60a339a9eacca0589f76bc9667d101`). The public callback shapes remain
compatible. All 132 focused methods pass on each Python version, and all eight
100/500-row intake screens confirm baseline plus two generations. **All four
2,000-row screens still refuse baseline admission** at the unchanged heap cap.
This is a joined source checkpoint, not producer or resource acceptance.

There are no runtime, test, public API, wire/schema/ID, package, selection or
sibling changes in this evidence commit. Earlier gates remain attached to their
original inputs. In particular, the Mesh canonical 403 and focused 68 source
gates in the [index checkpoint](../2026-10-17-index-workspace/README.md) use
Observer84; they are not relabeled as gates for this new pair. Observer's own
patch and prior phase/group joins retain their separate reports and failures.

Exact qualification

[The runner](qualify_join.py) exports both repositories from Git and verifies 262
Mesh, 212 Observer and eight protected inputs. It verifies all 27 prior Mesh
index artifacts, pins the two upstream Observer receipts and unchanged intake
probe, and checks source inventories and runner bytes after qualification.
Imported files match those immutable source inventories: 41 per Mesh worker,
75 per Observer worker and 80 per intake screen on each Python version.

The suites run in separate processes because both projects own a test helper
with the same module name. The Observer worker runs its 64 patch/profile/codec/
read methods; the Mesh worker runs 68 compact/reconstruction/ordered/packed/
workspace methods, including six workspace tests. Python 3.14.8 and 3.11.17 each
report zero failures, errors or skips, with GC disabled. No full Observer or
canonical Mesh suite is rerun for this evidence-only join.

All twelve screens run serially under the existing shared CPU advisory lock.
They use the original actual compact Runtime/source IPC and Reader intake probe
without changes. Source intake and Reader share the original 32 MiB encoded /
64 MiB heap ledger; the native owner has its separate account. All six final
Reader counters are zero in every screen, with real errors held under disabled
GC. The native owner returns to its separate account base.

| Rows/backend | Python 3.14.8 charged peak heap | Python 3.11.17 charged peak heap | Outcome |
| --- | ---: | ---: | --- |
| 100 default | 14,906,203 | 14,951,363 | Baseline + two generations + fresh heads pass |
| 100 private packed | 13,713,787 | 13,759,731 | Same |
| 500 default | 35,932,113 | 36,146,873 | Same |
| 500 private packed | 28,714,434 | 28,929,978 | Same |
| 2,000 default | 67,108,005 | 67,108,591 | `sync_decoded_capacity` at baseline admission |
| 2,000 private packed | 67,108,500 | 67,108,813 | Same |

The completed 500-row default peaks are lower than Observer's prior b6/430
group join by 1,553,176 / 1,553,960 bytes on Python 3.14 / 3.11. Packed peaks are
lower by 1,868,799 bytes on both. Their encoded peaks remain 9,363,952 bytes
default and 7,168,551 packed. These are charged workspace peaks, not a unique
physical allocation census or a process RSS saving. The different refusal
points make failed 2,000-row peaks unsuitable for a savings claim.

Additional failure localization

One separate packed2k/Python3.14 diagnostic uses the original private scalar
audit unchanged. It reaches all 18,000 Observer token DTOs and the 2,000 generic
field groups. A later `_Decoded` retain refuses at decoded 9,672,159 / reserved
57,369,560 bytes; charged peak is 67,108,500. The audit records generic field
group scratch of 1,744,000 bytes and the new compact fixed patch scratch of
6,656 bytes. The old eager 6,146,304-byte whole-patch reservation is absent.
The callback now completes; this later generic failure is not the historical
Observer84 callback refusal or the earlier prototype's eager-patch refusal.

The scalar wrappers observe allocation types and cumulative BudgetRef charges,
not complete physical graph topology. Final allocation bins and six counters
are zero. The audit does not identify an allowance that may safely be reduced,
prove a cap overrun, or justify changing the fixed caps. Its timing is excluded.

Preserved setup diagnostics

Two qualification-driver setup attempts are retained under `diagnostics/` and
excluded from the final run. The first failed while importing the other
project's same-named fixture helper before tests. The second ran both Python
3.14 workers and one successful small screen, then its parent pin checker did
not include the archived evidence probe path. The final runner uses separate
workers and explicitly verifies that extra Git-pinned probe input. No source
or assertion change was needed; setup errors are not native/source failures.
Earlier standalone source and upstream join evidence is preserved unchanged.

Limits and reproduction

Full-only fixtures have 710 / 3,510 / 14,010 membership cells at 100 / 500 /
2,000 rows, not dense nine-field coverage. The private packed arena is test
owned. Private nonce/native input pin/proof carrier, extra prepaid fixture
scratch and synthetic Reader time remain disclosed. Large cases fail before
proof scratch; their cleanup is checked without a successful proof claim.

Ordinary SyncReader/authenticated selected route, controller/relay intake,
inclusive physical heap/RSS, absolute 2s/15s timing, CPU, dense2k capacity,
delivered cold/recovery, populated native/fixed SSH and immutable installed-pair
acceptance remain open. Earlier hard CPU failures, fallbacks without delivered
recovery, attribution cleanup HOLD and independently closed source/controller
findings are unchanged. No artifact allocation, provider/service action or
rollout occurred.

```text
rtk proxy .venv/bin/python -B docs/evidence/2026-10-17-profile-index-join/qualify_join.py --observer-repo /home/bryan/code/agent-observer-active-feed --python311 /home/bryan/code/agent-observer/.local/active-feed-20261016/installed311/bin/python --output .cache/new-profile-index-join
```

[receipt.json](receipt.json) pins the runner, sealer, exact reports, loaded inputs,
upstream receipts and preserved setup diagnostics. [qualification.json](results/qualification.json)
contains the full source inventories and twelve reports; the private scalar
audit is separate from that qualification.
