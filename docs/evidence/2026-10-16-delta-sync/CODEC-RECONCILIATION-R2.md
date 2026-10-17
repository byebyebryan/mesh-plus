# Compact contract reconciliation, revision 2

This incorporates RLCD `e-260ce3b1` and the immutable Observer owning review
`38e2b64`, SHA256 `69efa803...`, 9,597 bytes. It also reads Observer's later
consolidated normalization decision `ffa302f`, SHA256
`35b1911388e75f4bc2a87087f23f07f7ca95346719933d7b37a5365d528734d6`.
Both current files match their committed bytes. Mesh accepts that exact later
decision's signatures, phases, AliasSpec/HeaderRef, alias/mask and single-writer
choices. The original review's open questions are reconciled against those
concrete later choices rather than treated as a new execution-permission gate.

The proposed standalone [r2 contract](../../delta-sync-codec-contract-r2.md)
adds explicit public-intent and raw-reference completions for same-byte owning
review. Its SHA256 is
`0920bf9ea7c2e76695c2cfe21016636a5ae3ebeac60f59be44f0fac914d8f44d`
(27,992 bytes). Observer has not yet accepted these additional spellings.
No proposed class needs to be implemented before reviewing them.

| Previously open point | Concrete r2 decision |
| --- | --- |
| Changed-group API | Revocable engine-minted MembershipGroupIntent exposes full cohort/ref through the established public array-ref pattern and exact old/new integer masks; no private graph or per-cell operation roster |
| Patch versus expansion | Compact requires membership_expansion exactly (); Mesh is the sole cell expander after validated tokens/indexes; expanded mode keeps the existing G0 path |
| Row reference side/birth | RawRecordRef=[alias,birthGeneration], epoch restored only from exact binding; fixed schema positions resolve strictly before or after with no fallback |
| Receipt reference side | Separate bounded message-local before/after dictionaries of full keys; zero-based receipt indices never borrow the other side's order |
| Group wire shape | Baseline=[afterSide,mask]; delta=[beforeSide|null,oldMask|null,afterSide|null,newMask], side=[receiptIndex,alias,birthGeneration] |
| Removed/reused identity or cohort | Different full refs/keys need separate remove/insert groups; one combined edit cannot reinterpret an old removal |
| Injection and schema streaming | Explicit native_codec keyword/default; records and aliases first, then controlled spaces; per-value raw schema before yield and complete iteration before commit |

Before receipt keys must exist in admitted before state; after keys must exist
in candidate receipts. The codec can build that bounded receipt overlay from
raw receipt edits and before point lookups, without a new private graph API.
These dictionaries convey no completeness, receipt health, currentness or
reobservation. Full original context/negative values keep their exact expanded
meaning. Observer still owns the complete Agent raw schema and actual restoration
implementation; the generic engine independently checks semantic tokens, aliases,
every logical table, cohort seals and native/source roots.

## Arithmetic and native-shaped fixture replay

On Python 3.14.8 and 3.11.17:

- The unchanged r1 upstream oracle reproduces its exact 97,800-byte fixture:
  eight positive cases, 37 rejections and four optional-value token inputs.
- Observer's committed independent stdlib verifier reproduces eight positives,
  all eight logical tables/roots, 11 permutations and the membership-change
  counts [0,1,1,2,1,1,0,4]. It independently executes **zero** of the 37
  rejections; upstream replay is not relabeled independent rejection evidence.
- The new reference supplement reproduces six positive and 26 rejection cases,
  including receipt reorder/removal, a surviving row across reorder, alias reuse,
  foreign/stale refs, zero index, mask types and duplicate groups. Final fixture
  SHA256 is `82f70805585aed2d7a70a2d10736de5650c9dad370b5cb811121fd47ad1761be`.
- Observer's joined-native script runs from an immutable ffa302f export and
  reproduces the retained fixture byte-for-byte: eight full/active cases, 72
  tokens and four partition rejections. SHA256 is
  `9af5486fd0df9401d9a048505628215800c6d595211349343b2237f540d30e2d`.
  It checks literal independent moved-path/nine-field extraction, body IDs and
  tokens against the pure native row facade. It executes no future compact
  codec, plan, cache admission, proof or transport.

Reproduce the Mesh arithmetic with:

```sh
rtk proxy .venv/bin/python scripts/reproduce-sync-codec-vectors.py --check docs/evidence/2026-10-16-delta-sync/codec-review-vectors-r1.json
rtk proxy .venv/bin/python scripts/reproduce-sync-codec-refs.py --check docs/evidence/2026-10-16-delta-sync/codec-refs-r2-vectors.json
```

The scripts run with 3.11 as well. The independent verifier and joined script
are the committed Observer files named in [codec-review-r2.json](codec-review-r2.json).
That manifest pins all reviewed commits/hashes, scripts, fixture inputs and
limits of each replay. The earlier `codec-refs-r2-vectors-draft.json` is retained
as a superseded development sample, not the final fixture or runtime evidence.

## Gate and scope

The new reference model is not the complete native schema: receipt existence,
domain joins, admitted old masks, compact patch enforcement, stage rollback,
header/context/iterator retirement and quota behavior still need actual runtime
execution. The complete raw compact schema/encoding identity and joined raw
restoration vectors need owning agreement. The r2 completions remain under exact
review before shared dependent implementation. G1 freeze and later G2 installed/
native/end-to-end, CPU/bytes, actual capacity, RSS/plateau and rollback gates stay
open. Private normalized storage fit does not settle those gates.

Ruff and the unchanged 33-input/25-schema lock pass. This checkpoint changes
documentation and stdlib review tooling only; all 59 runtime source files still
match `e9f07c3`. No full runtime suite was rerun or attributed to a codec that
does not exist. Frozen G0, agreed input API and old schemas are unchanged.
Relay r4 remains exactly `5377d3a5...` at `7d7b09c`; its already queued owning
review is separate and is not repeated by this compact reconciliation.
No schema/ID/package allocation, sibling edit, provider/service action or rollout.
