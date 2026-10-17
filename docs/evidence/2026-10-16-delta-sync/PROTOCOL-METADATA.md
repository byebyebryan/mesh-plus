# Protocol metadata ownership and key-copy bounds

This source checkpoint follows `8b06de3`. Cache-owned candidate capabilities,
their tags/permits, bounded known/retired heads, four transaction tokens and
clock history are now explicit ledger-owned immutable units. Confirmation
permits belong to their confirmation allocation. Metadata updates retain the
new unit before retiring the old one; a candidate's owner pointer remains a
lookup capability rather than a graph child. This adds no authority to tags or
hints and does not change the shared semantic callback API.

A GC-disabled test replaces candidates and confirms fifty warm generations of
the same material. Retired candidates fail immediately, pending/reserved bytes
return to zero each time, metadata use plateaus, and ordinary cache close still
releases all retained allocation units. This is a structural metadata check,
not the aggregate dense/RSS/plateau or installed qualification gate.

Borrowed baseline keys now calculate their detached-container copy allowance
by scanning owned canonical punctuation, ignoring quoted/escaped punctuation.
The bound matches `Atom.copy_budget` for arrays/dictionaries without decoding
the key. It replaces a loose allowance proportional to every encoded byte.
Scalar leaves remain immutable/shared; private decoder allocation and callback
output retention are separate obligations, not hidden in this copy bound.

The first attempted check, `protocol-metadata-source.json`, is explicitly
**failed/not accepted**: Observer source changed during the run and a new test
had an unresolved `ABSENT` import. Its Mesh core 258 run and failed counterpart
30-test log are preserved. The owning peer repaired the fixture; no sibling
source was edited here.

The subsequent `protocol-metadata-keybound-source.json` records byte-stable
exact inputs and full logs. Python 3.14.8 passes the canonical 259-test core gate
without skips (87 sync tests), design 116/delivery 169 checks, unchanged
33-input/25-schema lock check and Ruff. Observer's updated 31 source adapter
tests pass. This is compatibility evidence, not independent domain/installed
acceptance. The complete auxiliary allocation, dense resource, CPU/bytes/latency,
new sync IPC/fixed SSH, schema/codec agreement and immutable-package gates remain
open. No package identity, frozen G0 bytes, old schema/artifact, deployed service,
sibling source or consumer adoption was changed.
