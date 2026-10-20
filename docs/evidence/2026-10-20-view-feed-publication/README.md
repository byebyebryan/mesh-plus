# Experimental a24 publication review

Reviewed runtime: `7e152d22fa57fc45049438b50877433d8c96f6d8`, following
the [original source checkpoint](../2026-10-20-view-feed/README.md). Version
`0.1.0a24` is a new experimental GitHub prerelease from the isolated
`view-change-feed-20261020` branch. Accepted `main`, installed selections and
services remain at their existing pins. The retained semantic delta engine
stays dark. The package includes the prior opt-in working-set SDK registration;
it does not claim native producer or deployment acceptance for that profile.

The second review found and fixed:

- A failed receiver constructor could leave its already-created raw subscription
  open. Cleanup now joins that subscription before propagating rejection and
  preserves another subscription on the same channel.
- Python equality aliased bool, float and integer selectors. Setup now uses
  canonical JSON equality, distinguishing those values while accepting object
  key reordering, before any source read.
- A competing ledger narrowing could change the current cap between validation
  and installation. Both steps now run under the same lock.
- The generic Bridge could call a legacy publisher's incidental
  `reset_publication` method. The new reset hook now requires explicit opt-in.
- One standalone lifecycle test accidentally imported an optional Observer
  contract. Its independent SDK fixture now preserves the original cancellation,
  weak-reference and no-GC assertions with no Observer dependency.

The API example also passes complete owner metadata alongside record operations
to the application's atomic update, avoiding a mixed support-table generation.
No wire/schema/lock bytes changed during this review.

| Final exact wheel check | Result |
| --- | --- |
| Canonical gate, Python 3.11.17 / 3.13.14 / 3.14.8 | 483 tests each, no skips; Ruff pass; neither Observer installed |
| Optional WSS, Python 3.11 / 3.13 | 34 tests each, no skips |
| Disposable current Observer composition, all three Pythons | 6 scenarios each: IPC/real-pipe stdio, empty and changing views, ordinary Reader/facade, two fresh native proofs |
| CI fault laboratory, Python 3.11 / 3.13 | pass; seven named fault groups, no performance measurements |
| Runtime/schema wheel parity | all 107 files exact |
| Frozen prior a23 normative inputs | all 33 preserved; root lock remains 37 inputs / 28 packaged schemas |

The before witness uses the immutable previous private wheel (SHA256
`19f8499c4b2228d0fb8eff8c4b819caf627abb8abbd9fd68fc409d004483e964`)
with final committed tests: three methods give four expected failed checks on
each Python 3.11/3.14. A separate legacy-reset witness ends with the expected
`DeliveryError: gap` on Python 3.14. All final cases pass. The original source
and evidence commits remain unchanged. [review.json](review.json) pins exact
inputs, outputs and exclusions.

The two raw `review-before-*.log` files retain unittest's trailing space on
their second line. Those two evidence-only whitespace warnings are preserved
with the original bytes and hashes; the remaining staged files pass the
whitespace check.

The new wheel is retained separately at
`.cache/view-feed-publication-20261020/artifacts-final/mesh_plus-0.1.0a24-py3-none-any.whl`,
SHA256 `9bca5b554babfa59ba56b1a4ac5e8e5c66a85e63709731ee1fe7d4f0ed6a18a6`.
Publication assets include that exact wheel, its versioned manifest, SHA256SUMS
and provenance. Hosted branch/tag CI, downloaded-byte checks and GitHub signed
release verification are recorded in the subsequent publication receipt.

This is an experimental publication, not a default-route or production
performance promotion. Full source reads, whole-target verification and nonce
proofs still cost O(N). Inclusive CPU/RSS, dense large-view/full+active/slow-peer
capacity, delivered recovery, populated native/fixed-SSH and immutable deployed
pair gates remain open. Source fixtures use `collect=False`; no provider,
normal service, sibling checkout, device, rollout or old released asset changes.
