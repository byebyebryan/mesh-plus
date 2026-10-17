# Public input retirement query implementation

Mesh runtime `6fce5ed0e997d021e7532051fe985c3693962c3e` implements the exact
[owner-bound query agreement](delta-sync-ref-retirement-proposal.md). Observer
accepted the unchanged 6,067-byte proposal at `5543fc79`; RLCD's exact review
is `0738f941`. No additional role/coordinator permission is needed for the
already authorized dependent source fix.

```python
InputOwner.ref_is_retired(ref: OwnedInputRef) -> bool
RelayInputOwner.ref_is_retired(ref: RelayInputRef) -> bool
```

Both methods are available in the owning source checkout. This is an unselected
source API checkpoint, not a wheel/version, installed selection or release.
There is no competing ref property. Available and healthy consuming refs return
literal `False`. Explicit logical revocation, completed consume or retired intake
epoch returns literal `True`, including a revoked pin whose bytes remain charged.
A closed minting owner still answers for its own refs. Wrong owner/role/type,
uninitialized/malformed refs and conflicting live record identity reject
`sync_input_owner` without closing or refunding a supplied/sibling handle.

The implementation reads bounded owner/weak-scope/buffer identity and revocation
metadata. It does not call semantic owner/cache checks, codecs/profiles, parse
bytes, reserve/release credit, scan a roster or reclaim material. Absence of a
well-formed own record is terminal, without consumed history; it does not attest
private-field tampering or earlier material admission. Existing strict `nbytes`
and all actual consume/pin-exit/publication checks remain unchanged. `False` is
registry bookkeeping, never permission to use data or a currentness capability.

The query's error boundary clears its own unwound frames/input arguments, so a
caller-held failure does not retain the minting owner/cache/ledger after their
own cleanup. It leaves an enclosing caller exception, cause and traceback intact;
that caller's retained graph is not this query's cleanup responsibility. No
generic admission boundary or other public error path is changed.

Seven new methods cover cache and relay states, healthy/successful/failed consume,
revocation with 1,753 bytes still pinned, unsealed receive credit, same-owner close,
replacement and shared-ledger sibling isolation, strict role/handle errors,
unchanged counters/confirmed publication/configured callbacks, 70 caller-retained
terminal handles, saved errors and immediate weak retirement with cyclic GC off.
Private generic pin helpers and live buffer counts are disclosed test-only
instrumentation; no new byte accessor or private source access is introduced.

All 60 input/relay tests pass on Python 3.14.8 and 3.11.17 with GC disabled.
The final selected-environment canonical gate passes 355 tests with zero skips,
plus 33 lock/25 schema, 116 design, 169 delivery and Ruff checks. The immutable
parent `975ecb8` with only the final two test files overlaid produces seven
missing-method errors on each version: that proves the old optional capability
is absent, not that an old accepted source tuple fails its contract. The
[reproducer and receipt](evidence/2026-10-16-delta-sync/ref-retirement-g1-review.json)
pin this distinction and every tested source/overlay.

The original source still needs to adopt the method through its supported public
protocol: require callable before session state reservation/I/O, capture it,
accept exact bool only, prune only `True`, retain consuming `False` revokers, then
drop the callback after its own child/I/O cleanup. No ambiguous `nbytes` fallback
or shared-owner/sibling close is supported. This generic implementation alone
does not fix or close Observer's old pruning defect. The unchanged five-case
source regression and actual source/relay/Reader/cancellation/codec gates still
need the final committed source pair after that owning fix.

No frozen contract/schema/LOCK, deadline/cap, encoding ID, ordinary raw/legacy
source, authority, profile, package, selected a7/a23, provider/service or sibling
file changed. Controller R2 remains a separate review. Aggregate resources/RSS,
dense CPU/bytes, deliverable 2,000-row recovery, native/populated IPC/fixed SSH,
immutable installed pair and later adoption remain open. Earlier evidence retains
its original sources and exclusions.
