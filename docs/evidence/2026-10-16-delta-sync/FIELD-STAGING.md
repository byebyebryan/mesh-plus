# Compact private field staging checkpoint

This follows source checkpoint `e15764b` on the isolated G1 branch. It does not
allocate a package, enable a route, revise the frozen G0 appendix or constitute
G1/G2 acceptance. Prior evidence remains tied to its original source hashes.

Two generic correctness fixes are included. An atomic index key replacement
now removes old keys before inserting new keys, so its final declared capacity
is sufficient. Removing a field token also checks unchanged incident membership
cells; an extant cell cannot refer to a token that no longer exists. Regression
tests verify both cases and failure atomicity.

Field staging groups compact owned record refs and processes one decoded field
dictionary at a time. It retains canonical token buffers and small offsets;
membership checks compare borrowed encoded spans rather than decoding a full
dictionary per cell or retaining a second decoded field roster. Interleaved
updates with distinct equal refs, escaped field names and Unicode names retain
the same exact tokens, cohort seals and native roots. Retired birth refs and
duplicate registries also retain charged compact owners instead of uncharged
borrowed decoder output. Auxiliary controls receive explicit scratch charges.
The facade's returned-patch allocation obligation and the complete aggregate
RSS/peak/plateau qualification remain open.

Ordered AVL nodes/maps now use prepaid intrusive allocation ownership too.
Private large height/count integers are grouped with their nodes; bulk-build
list/sort scratch is reserved before growth. A GC-disabled 512-row/100-generation
test verifies deterministic pending/retained reclamation. This is structural
evidence, not a CPU or RSS comparison.

`compact-field-staging-source.json` records exact input hashes and before/after
stability, including added/removed input paths. On Python 3.14.8, the canonical
gate passes 249 core tests with no skips (77 sync tests), design 116/delivery 169
checks, the unchanged 33-input/25-schema lock check and Ruff. The explicitly
supplied Observer checkout's 28 source adapter tests pass. Its captured logs and
hashes are alongside the report. Native/installed/fixed SSH, matched performance
and independent Observer acceptance are still separate gates. No numeric result
from the previous checkpoint is attributed to these changed runtime bytes.

Compact wire/normalization and the publisher role remain pending owning review.
No shared semantic callback signature, native contract, deployed service,
sibling source, package version or artifact was changed.
