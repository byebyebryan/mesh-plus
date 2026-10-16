# Owned acquisition and preallocation source checkpoint

This advances the isolated G1 implementation from `68fb8a4`. It is not G1/G2
acceptance, an installed candidate, or an enabled sync route. The accepted G0
appendix remains exactly SHA256
`a376bc848a78027d4fd723e8a2959dbbc4e00114da132d3a5d2733a6ebce2eb6`.
The old 33 locked inputs and 25 packaged schema copies remain unchanged.

The source now prepays dominant immutable node/atom creation and encoded bytes,
including allocations not yet attached to a retained root. Decoder borrows do
not prematurely release a live staged atom's reservation. Recursive builder
closures are explicitly retired; a GC-disabled repeated-generation test checks
deterministic reclamation. Baseline cohort and record-link construction avoid
an additional roster of decoded identity DTOs. Typed operation/control scratch
and private index schema trees are charged; validator/compiler objects are
operation-scoped under a conservative scratch reservation. The complete
auxiliary-container, facade staging, compiler peak and RSS audit remains open.
Ledger counters here are accounted allocation evidence, not an assertion that
the final aggregate resource gate has passed.

Transactions now decode and privately pack one operation value at a time.
Canonical transaction-ID framing streams the same exact pieces through SHA256;
it does not construct a second full operations tree or concatenate a whole
canonical transaction. Pretty JSON, Unicode, duplicate-key/numeric corruption,
old-value/root checks and rejection cleanup are covered. A 100-record synthetic
all-body update fits a 13 MiB cache where the whole-frame decoder reservation
would exceed that cap. This generic fixture is not an Agent performance result.

The internal acquisition controller enforces compact proof work within two
seconds and the original absolute fifteen-second acquisition deadline. A known
moved head revokes authority before separate bounded catch-up and at most one
fresh proof retry. It supports an explicit recovery baseline, rejects concurrent
acquisitions on one cache, and revokes before awaiting endpoint cleanup under
repeated cancellation. Endpoint exceptions cannot export private acquisition
frames. Ordered aggregate handles bind exact request/catalog/routes and channel
incarnations, share a ledger, and preserve per-host atomicity. These controller
tests use injected endpoints; real sync IPC/SSH remains unimplemented.

`owned-acquisition-source.json` records exact Mesh/Observer input hashes, full
logs and before/after byte stability. On Python 3.14.8, the canonical gate passes
245 core tests without skips, design 116/delivery 169 checks, the unchanged
lock/schema check and Ruff. Its 73 sync tests include the new acquisition,
aggregate, streaming and allocation cases. Observer's 28 source adapter tests
pass against these same source bytes. This is compatibility evidence, not
independent Observer G1 acceptance or the optional installed/native gate.

The separately recorded `capacity-owned-acquisition-source.json` uses valid
attempt/accept fixtures from the explicitly supplied Observer checkout. Its
unpaired full-view diagnostics are:

| Records | Legacy native bytes | Expanded sync native bytes | Retained accounted bytes | Peak accounted bytes |
| --- | ---: | ---: | ---: | ---: |
| 100 | 138,533 | 429,266 | 2,366,062 | 7,066,147 |
| 500 | 683,333 | 2,125,267 | 11,254,278 | 30,321,835 |
| 2,000 | 2,726,333 | rejected by native frame limit | not admitted | not measured |

All admitted caches close with zero retained/reserved bytes. The 500-row Mesh
baseline CPU observation is 2,874.56 ms; it is unpaired and is not a regression
or savings result. Expanded wire bytes still fail the cold byte gate. The
2,000-row legacy source fits, so the sync capacity failure is not equal-work
performance evidence. These fixtures have four memberships per row and do not
prove the dense nine-field, full+active, selected-host aggregate cap or plateau.
Earlier draft diagnostics retain their original source hashes and scope; they
are not acceptance attributed to this later runtime.

Remaining gates include joint compact-codec/mask/alias agreement and the
publisher admission/relay role decision; complete auxiliary accounting and dense
resource/RSS/plateau qualification; owned sync publisher/Reader, IPC and fixed
SSH; reviewed new framing/schema/vector/lock inputs; an unused package identity,
immutable wheels and independent installed 3.11/3.14 acceptance; and all matched
CPU/bytes/latency/cleanup/oracle gates. No shared semantic callback signature was
changed. `docs/delta-sync-codec-proposal.md` remains a proposal awaiting its
owning review. No new version/wheel, sibling source edit, service action,
deployment or consumer adoption occurred.
