# Isolated native identity and carrier study

Study-only code, outside packaged runtime and frozen schema bytes. Inputs:
Mesh 0.1.0a15, Tmux Observer 0.6.0a7, Python 3.13.7; exact wheel and dependency
hashes in [R0](../../docs/evidence/2026-10-12-compact-research/R0.json).
No active Agent imports, ordinary tmux state or deployed configuration.

`identity.py` uses a disposable TMUX_TMPDIR/default-server namespace and actual
installed owner/factory. It records digest differences without native payloads.
All native commands and children are owned and retired. `check_native.py` uses
that same ownership boundary for full-proof WSS and experimental TCP poll/push,
rename, source loss and owner restart. These are native correctness checks,
not actual native performance acceptance.

`tcp_stream.py` is an experimental mTLS carrier: u8 tag, u32 big-endian length,
bounded JSON data or ping/pong/close control, ALPN `mesh-study-tcp-json-1`.
It reuses pinned WSS pre-TLS admission/policy monitoring/retirement, caps before
body allocation, two-second partial-frame/send budgets, five-second ping cadence,
certificate expiry checks and a bounded queue. It is not a supported Mesh backend
or endpoint and has no production selection/fallback path.

`check_carrier.py` checks framing, malformed inputs, credentials, ALPN, admission,
reconnect, nonce admission, idle no-renewal, missing pong and policy revocation.
`compare_carriers.py` separately compares complete existing JSON proofs over
WSS and TCP with identical shared publisher/native fixture topology, pure Tmux
profile, generic Reader and ReadGuard. Synthetic generic Reader path labels
are common placeholders; this does not establish production TCP provenance.

Use an isolated installed wheel environment (not editable runtime):

```sh
rtk proxy /path/to/venv/bin/python -I -B studies/compact/identity.py --output /private/new-identity.json
rtk proxy /path/to/venv/bin/python -I -B studies/compact/check_carrier.py
rtk proxy /path/to/venv/bin/python -I -B studies/compact/check_native.py
rtk proxy /path/to/venv/bin/python -I -B studies/compact/check_interruption.py
rtk proxy /path/to/venv/bin/python -I -B studies/compact/compare_carriers.py --output /private/new-matrix --blocks 4
rtk proxy /path/to/venv/bin/python -I -B studies/compact/compare_carriers.py --output /private/new-long --blocks 1 --fanout 1 --modes push --steps 12 --interval 3 --expired
```

Use `summarize_carriers.py --root /private/new-matrix --output /private/summary --expected-cases 96`
to requalify/archive the primary matrix; the cadence control expects four cases.
[Assessment](../../docs/evidence/2026-10-12-compact-research/README.md) records
decisions and measured limits.

Outputs must be new and private. The runner freezes installed runtime/harness
fingerprints, matches the exact trace/proof/source/consumer work per ABBA block,
attributes PID/birth-specific roles, and fails on cleanup or resource-accounting
errors. Source acquisition/fixture role and sampler overhead remain separately
visible. Logical JSON counters exclude framing/TLS/IP. Experimental TCP records
framing counters including liveness; WSS application counters do not imply
physical wire capture. The expired three-second-cadence control proves expiry
handling and liveness in that workload, not ordinary fresh-fleet admission.

[Research plan](../../docs/compact-proof-research-plan.md) and
[owner identity proposal](../../docs/compact-proof-owner-proposal.md) specify
conditional stops. Compact JSON and binary encoding are gated by native identity;
this directory does not advertise those capabilities.
