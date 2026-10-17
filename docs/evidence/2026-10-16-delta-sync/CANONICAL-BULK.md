# Canonical bytes, bulk indexes and clock checks

This is an isolated source checkpoint after `70fb22d`, not G1/G2 acceptance.
The frozen G0 appendix, accepted schema copies, package identity and immutable
artifacts remain unchanged. No sync route is enabled.

Profiling the 500-row synthetic baseline identified temporary canonical-value
trees, reference/decoder work and the Observer callback as major costs. The
profiling-only run had 46,877,923 calls; about 5.68 of its 10.44 Mesh-admission
CPU seconds were in the owning Observer callback. Its profiler overhead is not
a latency/deadline or performance acceptance result. The owning `.cache`
profile is `sync-bulk-index-70fb22d.prof`; no sibling source was changed.

Canonical byte encoding now validates/emits captured nodes in one pass without
constructing a second frozen JSON tree. Retained values still use the existing
owned `Atom` boundary. The exact accepted hash vectors and 720 insertion
permutations pass, and 1,000 generated Unicode/control/integer/optional trees
match both stdlib JSON and the retained-value encoder. Mutation after an earlier
encoding is revalidated; unsupported numeric/types remain rejected.

Baseline declared indexes, field-token indexes and body-reference indexes now
bulk-build once, using already canonical owned keys and privately owned values.
Ordered indexes bulk-sort/build their immutable AVL tree. A 300-record test
checks each unordered private index writes exactly its final 599 Patricia nodes;
normal sparse updates retain path-copy behavior. This changes no domain callback
signature, native table contents, seals or native/source commitment math.

Cursor generations now reject booleans rather than accepting Python's `True ==
1` alias. Owner clock history is scoped to host/UID/owner/boot/time identity,
so a provider/namespace context-generation change cannot reset monotonicity.
Bridge clocks cannot regress within that scope or exceed measured whole-proof
elapsed time plus the existing 100 ms margin. Moved heads validate basic clock
shape and configured host before requesting catch-up. Regression tests cover
these cases and preserve failed-proof revocation.

`canonical-bulk-source.json` captures exact input hashes, full logs and source
stability. Python 3.14.8 passes the canonical 256-test core gate with no skips
(84 sync tests), design 116/delivery 169 checks, the unchanged 33-input/25-schema
lock check and Ruff. Observer's 28 source adapter tests pass. No installed/native
or real sync IPC/SSH qualification is claimed.

`capacity-bulk-index-draft.json` and `capacity-canonical-encoder-draft.json`
preserve separate, unpaired diagnostic source snapshots. They observed 2,760.06
and 2,105.55 ms of 500-row Mesh baseline CPU respectively; they are not matched
ABBA, regression-ceiling or savings evidence and do not pin this later checkpoint.
Expanded native bytes still fail the cold-byte gate, and the 2,000-row native
frame failure remains unresolved. Compact codec/alias/mask and publisher-role
agreement, complete allocation/RSS/plateau audit, immutable new artifacts,
installed 3.11/3.14 acceptance and every matched pipeline gate remain open.
