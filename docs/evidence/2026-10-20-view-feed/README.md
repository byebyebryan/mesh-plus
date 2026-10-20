# Complete-view feed source checkpoint, 2026-10-20

Implemented source: `69bebf16c93a03f658927c8f08aea8e0caeffbf8`, on
`view-change-feed-20261020`, in `/home/bryan/code/mesh-plus-view-feed`.
Integration base is the current working-set SDK source
`2fb502da35c0ef9865762c4dc4b486dd30b7e316`; the retained original checkout at
`8e0c469` is unchanged. Observer is read-only source
`58b90e1a4a6b57e2c07d10856206908d2619af5b`. See the
[public API](../../view-feed-api.md) and [separate contract](../../../contracts/view-feed-v1/contract.md).

The publisher still supplies complete views. The new explicit route computes
whole-record hash/token changes, replaces owner metadata atomically, verifies
the complete target, and sends a replacement after any gap. The client exposes
change events or reconstructs ordinary full candidates for the existing Reader.
Full native snapshots and fresh nonce proofs remain the authority path.

Luna implemented the bounded generic core and focused tests. The primary owned
negotiation/carrier/Reader/CLI integration, independent vectors, resource and
failure review, fixes, actual Observer composition and final qualification.

| Check | Python 3.14.8 | Python 3.11.17 |
| --- | --- | --- |
| Canonical `scripts/check.py` | 479 pass, zero skips; Ruff pass | 479 pass, zero skips; Ruff pass |
| Isolated final wheel, feed tests | 36 pass | 36 pass |
| Actual Observer working-set source → feed → ordinary Reader/facade | 6 scenarios pass | 6 scenarios pass |
| Earlier private wheel + final concurrent-close test | 1 expected failure | 1 expected failure |
| Independent stdlib reference | 9 positive / 24 negative | 9 positive / 24 negative |

The six scenarios per version use a disposable actual Observer Runtime with
`collect=False`, synthetic accepted input, counts 0/3/12, owned IPC or real pipe
stdio, baseline plus changed view, and two fresh native nonce proofs. A pure
domain facade checks membership/currentness on an independently reconstructed
Reader response. The source is still full-view, not a native delta producer.
The reports capture 104 imported files per run; the receipt verifies 41 Observer
files against its immutable Git objects and Mesh wheel files against source.
The final wheel's 107 Python/schema inputs match the committed source. These
are isolated test installations, not a change to installed artifact selection.

Focused cases cover exact order/empty/null/metadata/birth handling; unknown,
duplicate and conflicting operations; corrupted targets; gap/reset; false token
promises; immutable borrowed outputs; preparse reservation refusal; retained
real errors; reentrant close; coalescing; held actual drains; repeated cancel;
concurrent close; sibling isolation; and immediate GC-disabled lease retirement.
The independent model additionally compares actual emitted packets with an
independent merge and restoration. Its 64-row sparse fixture verifies one
upsert has less than one quarter of the full candidate's payload bytes. This is
a payload-only fixture assertion, not an end-to-end bandwidth/CPU benchmark.

Two defects found during integration were fixed: a first coalesced replacement
may have revision greater than one; concurrent subscription close must join one
owned cleanup task and remain registered until it finishes. Target verification
also follows every row callback, preventing accidental callback mutation from
emitting an unchecked initial replacement. Error-held copies keep credit until
their real traceback is dropped. Before/after close evidence uses the preserved
earlier private wheel, exact final committed test bytes, GC disabled, and one
named expected failure; it does not assign an old Git runtime commit to that
uncommitted earlier artifact.

The canonical environment includes the exact Agent `0.7.0a5` contract wheel used
by the original Mesh checkout because one existing lifecycle test imports its
pure service facade. Initial attempts without that optional package are kept in
`.cache/view-feed/canonical-before-optional-contract-{314,311}.log` (one import
error each); no test was skipped or weakened. Feed wheel tests run with neither
Observer installed. The final Observer test explicitly adds only its pinned
source checkout. The final resource-bound prose clarification was separately
checked by `check-view-feed.py` on both versions after canonical execution;
runtime/schema/vector bytes did not change.

The private wheel is retained at
`.cache/view-feed/wheel-final/mesh_plus-0.1.0a23-py3-none-any.whl`, SHA256
`19f8499c4b2228d0fb8eff8c4b819caf627abb8abbd9fd68fc409d004483e964`.
Its a23 metadata is inherited private-candidate metadata; it must not overwrite
or be published as the released a23 artifact. The earlier regression wheel is
retained separately under `.cache/view-feed/wheel/`; both are pinned by the
[receipt](receipt.json). Keep these artifacts with this qualification record.

The root lock still has 37 exact inputs and 28 identical packaged schemas.
`authority.py`, the entire retained `sync` package and old schema bytes match
the integration base. No sibling checkout, service/provider, installed selection,
released artifact or deployment changed. The source commit is local; no new
branch has been pushed as part of implementation.

This is source and private-package qualification. It does not close the prior
producer CPU failures, dense 2k/full+active/slow-peer/recovery gates, inclusive
producer/source/relay/Reader resource budgets, physical/RSS gates, authenticated
catalog/native-fleet/fixed-SSH execution, or immutable installed-pair acceptance.
Feed reservations cover feed-owned state, buffers and queues after channel
handoff; caller input, pre-handoff allocation, source caches, ordinary Reader
copies and profile/validator implementation storage remain outside that ledger.
Full reads, target validation and proofs remain O(N). The old delta engine stays
dark. Run [verify.py](verify.py) to recheck the recorded artifacts and source
objects without running a new qualification campaign.
