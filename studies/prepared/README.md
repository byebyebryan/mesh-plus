# Prepared consumer qualification

These tools qualify the additive [local API](../../docs/prepared-consumer-api.md).
They are not packaged owner adapters. `tests/prepared_fixture.py` explicitly
models static compilation with an existing pure facade; owner adoption still
requires an independently reviewed interface and certification.

Use an isolated candidate wheel Python with jsonschema 4.26.0 and a pinned,
read-only installed-copy Tmux a7 package. Bind both artifact and installed-copy
file hashes. Do not import active Agent development. A separate standalone wheel
environment must contain no Observer packages or input .pth.

```sh
rtk proxy /private/tmux-env/bin/python -I -B studies/prepared/native.py
rtk proxy /private/tmux-env/bin/python -I -B studies/prepared/memory.py
rtk proxy .venv/bin/python studies/prepared/compare.py --python /private/tmux-env/bin/python --output /private/new-matrix
rtk proxy /private/installed-env/bin/python -I -B scripts/check.py --wss
rtk proxy /private/installed-env/bin/python -I -B scripts/check-conformance-wheel.py --ssh --report /private/new-conformance.json
```

Run timing after other local acceptance/allocation workloads finish. The matrix
uses four serial ABBA blocks per 1/4-host and 1/4/16-query cell (96 fresh process
trials), eight complete lifetimes each, fixed 32 rows per host. CPU includes
guard construction, one full admission, immutable compiler input, test compiler
thaw/allocation, compilation, owned query output, row oracle and disconnect. It
excludes imports/schema warm-up, source and transport I/O. Both paths use the
same installed candidate and pinned native facade. Every cell must fit original
leases; expiry is a failed expected-row oracle, never fixture renewal.

Allocation is separately traced without decision CPU timing. It covers 128
replacements for 1/4/16 hosts with 32 rows each and one host with the native
maximum 256 rows. Weak references require old and retired generations to release.
Fixed admission-time queries isolate ownership/churn and do not claim wall-time
fleet performance. Report steady, first-accept and replacement/export peak traced
allocation; this is not RSS/PSS, hard allocator bounds or global fleet capacity.

Native acceptance owns a disposable Tmux namespace/owner and private IPC bridge,
using the actual pinned factory/profile. It compares prepared and legacy pushed
updates and teardown. Remote proof over IPC is synthetic, not ordinary SSH.
Standalone WSS tests additionally compare the two consumers on mixed IPC,
authenticated disposable SSH and mTLS WSS fixture publishers, including updates.
Agent there is an independent frozen fixture; no active Agent/native provider
or owner-preparation release is certified. Preserve failed fixture runs and
identify exclusions in new dated evidence.

## Persistent changing publications

`watch_compare.py` runs `watch_measure.py` against the exact installed candidate
and pinned Tmux facade. It separates envelope-only sequence/revision changes
from native name/service sequence/revision changes with recomputed native proof
digests. Both preserve original receipts, expiry and input chronology. These
are synthetic already-produced publications, not provider acquisition or a real
Reader/transport CPU benchmark. Test-only compilation still requires owner review.

```sh
rtk proxy .venv/bin/python studies/prepared/watch_compare.py --python /private/tmux-env/bin/python --output /private/new-watch-memory --memory
rtk proxy .venv/bin/python studies/prepared/watch_compare.py --python /private/tmux-env/bin/python --output /private/new-watch-timing
```

Timing is 192 fresh processes / 48 ABBA blocks across two change kinds, 1/4
hosts and 1/4/16 queries per publication. Each case has two persistent consumer
lifetimes, eight distinct publications each. A separate untimed counted preflight
requires eight full Mesh profile-schema admissions for either implementation;
decision timing has no patch, counters, profiler or allocation tracing. Queries
use actual BOOTTIME and must fit original leases. The normalized cross-process
oracle includes identities, changed names and stream ordering; volatile clock/
UUID/evidence fields differ between independently constructed valid fixtures.
Raw snapshots are not exported in this timing; current row outputs are owned.

Allocation runs separately in fresh processes, one query per publication, with
32 publications for 1/4 hosts and 16 for 16 hosts. Both implementations receive
prebuilt inputs excluded from traced allocation. Queries use fixed admitted time
to isolate ownership; this is not real-time lease/cadence acceptance. Prepared
old-generation weak references must release after replacement. Report retained,
peak and retired allocations for both paths; no global RSS/PSS bound or maximum
byte-shaped frame acceptance is implied. Failed subprocess records go to a
separate failure.json and cannot be accepted as passed cases. Run timing with
other local qualification workloads stopped; preserve each input/harness/runtime
hash and all positions. Do not overwrite previous outputs or candidates.
