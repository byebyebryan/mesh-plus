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
