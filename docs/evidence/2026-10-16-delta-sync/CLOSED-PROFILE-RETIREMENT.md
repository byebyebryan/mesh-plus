# Terminal profile callback retirement

Runtime fix `32090d69c0603955613421d100386b3809e0ab90` detaches the configured
profile from a terminally closed Mesh cache and reconstruction store. The cache
also drops its clock callback. This is an implementation/lifecycle fix within
the existing experimental API. No contract, wire bytes, descriptor, lock, package
version, source intake signature, admission rule or authority check changes.

Observer's independent `be0559e` retention finding prompted this bounded audit.
Mesh's recursive Patricia insert/remove/bulk builders, allocation visitor and
payload-size visitor already clear recursive closure cells. A separate terminal
callback cycle was reproducible in Mesh: a supported profile retains public
body/head references; those reference a store/cache which still retains that
profile after close. Dropping the external profile/cache/view references with
cyclic GC disabled leaves the cache, store, profile and ledger weakrefs live,
despite zero accounted live bytes/allocations. Accounting alone did not prove
physical retirement.

The new regression uses ordinary baseline/domain admission and fresh proof, then
explicitly closes twice. It tests callbacks retaining both store-backed body
and cache-backed head references, first with no externally retained refs and
then with caller-held retired refs. It repeats both cases eight times with GC
disabled and never calls `gc.collect`.

| Probe at parent `50b6e68` versus fixed source | Before | After |
| --- | --- | --- |
| Live decoded/encoded/reserved/pending counters after close | 0 | 0 |
| Cache/store/profile/ledger weakrefs after close and external drop | all live | all retired immediately |
| Internal accounted peak in the small probe | 1,196,977 B | 1,196,977 B |

When the caller deliberately keeps retired public refs, the profile retires
immediately; the refs retain their closed owner until the caller drops them.
All attempted access still rejects `sync_cache_closed`. After dropping them,
cache/store/ledger retire immediately too. The fix does not mutate the caller's
profile or revoke unrelated owners. Disconnect remains the reusable operation;
terminal close stays idempotent and rejects further cache reads/input minting.
This weakref/probe evidence is not an RSS or plateau result.

The selected Python 3.14.8 canonical command
`rtk proxy .venv/bin/python scripts/check.py` passes 277 core tests, no skips,
116 design checks, 169 delivery checks, Ruff and the unchanged 33-input/25-schema
lock gate. The new test is
`test_sync_cache.CacheTests.test_closed_profile_and_owner_retire_without_cyclic_gc`.
An additional Python 3.11.17 run passes 74 focused Mesh cache/reconstruction/
input/decoder/commitment tests with no skips.

The current owned-source adapter was also tested against the changed Mesh
source, without editing Observer. Its source/runtime matches Observer
`4030d50c0d21c1e34daad45c29e2373502a3413a` (current docs head `8a39a6f`).
Both Python 3.14.8 and 3.11.17 pass 99 focused source/acquisition/profile/read
checks, including the twenty owned-source checks. These exercise controlled
local Unix sockets, full/active independent **unconfirmed** material admission,
paused receive/watch, batch/head/control, credit failure, mutation and cleanup.
They do not establish a populated end-to-end fresh-proof/transport/performance
gate or qualify an installed pair. No ordinary producer/service is contacted.

Exact commands, 68 Mesh and 91 Observer file hashes, stable before/after focused
inputs, logs and exclusions are in
[`closed-profile-retirement.json`](closed-profile-retirement.json). Full focused
logs are [`closed-profile-mesh311.log`](closed-profile-mesh311.log),
[`closed-profile-observer314.log`](closed-profile-observer314.log) and
[`closed-profile-observer311.log`](closed-profile-observer311.log).
The canonical gate ran separately on the same changed Mesh source; its totals
are recorded in that report. Observer's prior 827-test full-source gate against
its exported Mesh `0ca3b99` remains its own older evidence, not rerun/attributed
to these new runtime bytes.

G0 appendix `a376bc84...`, common input contract `7f7751ec...`, codec r1
`a67f11ae...`, relay r2 `8616bfba...`, lifecycle r3 `eb5c217c...` and LOCK
`11736752...` are unchanged. Exact compact/relay agreement, complete input/output
and aggregate peaks, dense CPU, packed recovery, RSS/plateau, installed/native
IPC/fixed SSH and end-to-end qualification remain open. The source-only fix is
not producer readiness. No new wheel/version, sibling edit, artifact selection,
native service/provider action or rollout occurred.
