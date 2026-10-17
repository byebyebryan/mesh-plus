# Revoked candidate credit during compact confirmation

Runtime `66b9c1e9c170dbfab847c1c691a6b7b11c9eff13` fixes the separate material
lifetime finding in RLCD's review of `e9f07c3`. Immediate input/publication
revocation from that earlier fix remains intact. The new source changes no
public signature, accepted input contract, relay role, schema or package version.

The defect occurs when `check_head()` closes the cache's current InputOwner or
disconnects the cache. Candidate capabilities become invalid immediately, but
`_discard_candidate()` also released the MaterialRoot while confirmation and
the callback still held it. Its charge could then be reused before its physical
graph retired. This was an accounting defect; no measured cap/RSS overrun is
claimed.

Confirmation now keeps its phase active through owned-input failure cleanup.
Candidate revocation retains the graph and its original charge in the existing
stage slot, marks that material retired and invalidates the capability. It
allocates no additional root or unbounded retirement list. Reentrant material
admission and nested confirmation reject. The retired stage cannot be reminted.
The next ordinary material entry or owning close retires it outside compact
confirmation. Acquisition drains that retired slot before selecting its material
base, so it cannot silently remint the discarded stage. Fresh proof and original
receipt eligibility remain independent requirements.

## Exact source checks

- The new GC-disabled regression fails in all four before cases: bare/owned
  proof crossed with owner close/disconnect. After the fix, no MaterialRoot
  release occurs in the callback, confirmation or owned-input unwind. The root
  remains charged, old candidate/head/view access rejects, a full ledger refuses
  further allocation, and reentrant staging rejects. The next baseline replaces
  it and requires ordinary fresh proof. Final owning cleanup leaves zero live
  ledger counters.
- A separate acquisition regression starts with this retired unconfirmed stage;
  its next acquisition obtains a baseline and proof rather than reminting it.
- Python 3.14.8 final canonical gate: **290 tests, zero skips**, 116 design and
  169 delivery checks, unchanged 33-input/25-schema lock and Ruff.
- Both Python 3.14.8 and 3.11.17: **59** focused Mesh input/cache/acquisition/
  private-page tests and **101** Observer source/intake/acquisition/profile/read
  tests against immutable Observer
  `4254a97e1b07b8428a62771e291cdc3d4b722f66`.

The retained independent RLCD probe is copied byte-for-byte, SHA256
`3921fad65d42bafd8ff1674412f2410a554a9325f43676a2854ff107cf62626c`.
Its test-only accounting instrumentation observes the same defect on immutable
Mesh `e9f07c3` and its correction on the changed source:

| Python | Material releases inside callback, before / after | Charged heap before / after owner close, old | Charged heap before / after owner close, fixed |
| --- | --- | --- | --- |
| 3.14.8 | 1 / 0 | 166,470 / 135,809 B | 166,470 / 164,932 B |
| 3.11.17 | 1 / 0 | 166,926 / 136,313 B | 166,926 / 165,372 B |

The small fixed decrease retires capability controls, not material. Both versions
retain the 1,024-byte live receive credit, reject old handles, preserve sibling
and replacement authority, and end at zero after explicit cleanup. Probe
fixtures and test-only borrowed audit pointers are outside production ownership;
this is not an aggregate capacity measurement.

[`head-retirement.json`](head-retirement.json) pins committed Mesh and immutable
Observer inputs, exact commands/PYTHONPATH, probe, outputs and logs. The initial
289-test canonical run preceded addition of the acquisition regression; the
separate final 290-test log is the complete gate. Historical `f000171` evidence
stays unchanged. Its three-path working overlay is not reattributed to Observer
4254: only one of those three exact hashes matches that final commit. The new
101-test compatibility runs use the complete immutable 4254 export.

## Current coordination, separate gates

RLCD notice `e-28e670cb` is consistent with the already accepted common input
contract SHA256 `7f7751ec...` and Observer's implemented opt-in adapter. Its
bounded own-ref registry, public retired-`nbytes` pruning, independent header/
ticket leases and source-local cleanup need no new mandatory child-owner API.
The owning adapter at `4030d50` and watch-close fixes through `4254a97` are
source work under that agreed shape. This receipt and the compatibility checks
do not certify all physical buffers, aggregate intake peaks or native delivery.

A1 is now closed, independently of this fix. Mesh verified exact Observer
`ccf6577d81b45ce9e400ebf0881ad71383339f27` acceptance and RLCD's committed
coordinator closure `818bdb7a8e2f5585386b012ca4b7ef3770b261aa`. The standalone
Mesh [relay r4](../../delta-sync-relay-api-r4.md) remains 47,213 bytes, SHA256
`5377d3a52c9e20bc839a1ecc135199b3103786f71b3e6e73a3e61a283dad7e5e`.
Dependent relay implementation may proceed through that accepted interface.
The copied contract's earlier candidate status and previous dated evidence are
historical; their bytes are preserved rather than rewritten as later acceptance.

The exact shared compact-r2 completions are still in counterpart review. Dense
producer CPU, packed cold/recovery, aggregate resources/RSS, installed IPC/fixed
SSH and end-to-end acceptance remain open. This source checkpoint makes no
performance claim and does not reattribute older packed-node measurements.
No artifact, service/provider, consumer, device, sibling or rollout change occurs.
