# R1 review reconciled with the accepted R2 compact contract

This answers RLCD `e-1353aee7` against the already committed later contract;
it changes neither accepted bytes nor APIs. Mesh R2 is commit
`b9dd8c610ea4575c1f4441d9331cfaef5ac1f58c`,
[delta-sync-codec-contract-r2.md](../../delta-sync-codec-contract-r2.md),
27,992 bytes, SHA256
`0920bf9ea7c2e76695c2cfe21016636a5ae3ebeac60f59be44f0fac914d8f44d`.
The prior R1 packet and its 8-positive/37-rejection arithmetic remain unchanged.

## Explicit callback relationship

The accepted R2 callback rule is exact:

- Compact `DomainIndexPatch.membership_expansion` is the empty tuple `()`.
  Every nonempty callback expansion rejects, including otherwise matching,
  wrong, duplicate or conflicting cells. It cannot become a second writer.
- The callback supplies its independently validated field-token/index patch.
  Generic completion alone expands memberships from admitted before cells,
  validated tokens and provisional masks, then verifies the logical tables,
  cohort seals and roots. Omitted masks inherit the before mask; changed tokens
  still update its retained bits. An equal-mask assertion does not suppress
  token changes or renew original evidence.
- Expanded mode preserves existing G0 `membership_expansion` semantics and the
  four callback signatures. The compact gate does not reinterpret that path.

These are in R2's public contract section, including the explicit field name
and rejection of nonempty matching cells. No alternative completeness or
double-application cross-check is proposed.

R2 also pins `receiptRefs={before:[fullReceiptKey,...],after:[...]}` with at
most 32 distinct full keys per side. Indices are strict zero-based integers;
removal and expected-old references resolve before, puts/replacements resolve
after, and no fallback crosses sides. Dictionary reorder cannot rebind an old
removal. A changed full cohort or record/birth needs separate removal/insertion
groups. These exact typed positions must carry into Observer's eventual Agent
compact schema, which remains separately owned and unallocated.

## Requested review vectors

The new [stdlib supplement](../../../scripts/reproduce-sync-codec-patch.py)
retains three positive cases and nine rejections in
[`codec-patch-review-vectors.json`](codec-patch-review-vectors.json), 40,522 bytes,
SHA256 `b5114719c4a1085a1d21cdd0c2a29fa44012e23f18ed7ae23236945c4dc0a0dd`.
Python 3.14.8 and 3.11.17 reproduce identical bytes.

The positive cases cover a changed activity token under an omitted mask, the
same change under an equal-mask assertion, and a body-only change with no field
token change. The retained activity bit changes exactly one membership cell;
the first two cases produce the same eight toy tables, cohort seals and native
root. The body-only case changes no membership cell. Each result matches the
retained explicit R1 logical-table fixture.

The rejection inputs cover nonempty matching, wrong-token, duplicate,
conflicting, removal, foreign-cohort and malformed expansions, plus a list and
null in place of the required Python tuple. Each model rejection precedes its
cell-expansion phase and leaves the toy before tables unchanged. Tuple contents
are represented as JSON descriptions; no real native patch DTO, callback or
stage is executed.

This is a **shared-model arithmetic supplement**, using the unchanged pinned R1
oracle and fixture. It is not an independent verifier, actual compact guard,
semantic validation, stage rollback, sparse-cost, lifetime or capacity test.
Independent runtime/root and GC-disabled held-error tests remain required.
The expanded runtime was not rerun for this docs/arithmetic-only change.

Reproduce with either supported Python:

```sh
rtk proxy .venv/bin/python scripts/reproduce-sync-codec-patch.py --check docs/evidence/2026-10-16-delta-sync/codec-patch-review-vectors.json
```

The [review manifest](codec-patch-review.json) binds the scripts, fixtures,
logs and unchanged contract/source inputs. Ruff and the unchanged 33-input/
25-schema lock pass. No runtime source changed from `66b9c1e`; its earlier
290-test gate is not reattributed as compact-path acceptance.

## Same-byte agreement already recorded

Observer `8a075bc78ef6f3710fa47ea57136260d5703dfee` accepts these exact R2
public-intent, raw-reference and single-writer decisions, with no remaining
owning contract conflict. Its review SHA256 is
`337c5ac11ab803f7121ee632e193b1d6c46e2a0b7ff0cda17b5c638bca9d9772`;
agreement manifest SHA256 is
`52bbc0ecdba1ca7107cb507993bdc84525a84b5965c67c9fc376d60f32f254fd`.
RLCD records joint reconciliation at
`5bb452a444f7ac97e64956f017b1413e8f4024f4`,
`projects/agent-dashboard/docs/delta-sync-codec-agreement.md`.
Mesh verified those committed bytes. The later root `157a888d` update only
advances its material-credit source-fix finding; the accepted contract tuple is
unchanged. The manifest distinguishes that current document from the original
closure bytes instead of attributing the updated status to the older commit.

The exact generic interface agreement permits its dependent G1 implementation;
this delayed R1 review needs no duplicate approval request. Complete Agent raw
schema/encoding and joined restoration vectors, actual compact/expanded
admission and rollback, physical ownership/resource/RSS, dense/cold/recovery
performance, installed populated IPC/fixed SSH and G1/G2 acceptance remain
separate. A1 is already closed on its own tuple. Frozen G0, schemas/lock,
package artifacts and deployed selection remain unchanged. No sibling,
provider/service, consumer, device or rollout change occurs.
