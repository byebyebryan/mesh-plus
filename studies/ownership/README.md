# Prepared consumer ownership study

[Proposal](https://github.com/byebyebryan/mesh-plus/blob/12723500ea2fa7f06f3c7089fce62577c2d2fcea/docs/history/performance/prepared-consumer-proposal.md) defines a possible opt-in
local API. This directory is outside the packaged runtime and does not implement
SDK 1 preparation support or a negotiated wire capability.

`prepared.py` models sealed row/snapshot bytes, immutable receipt requirements
and expiry facts, copied exports and explicit retirement. PreparedGuard delegates
existing full stream admission, then separately admits/compiles a generation.
Thus current timing includes duplicate preparation admission. It intentionally
compiles eligibility callbacks once, a guarantee existing SDK 1 does not promise.

`check.py` compares Tmux and independent Agent v1/v2 fixtures, input/export/row
mutation, lease/clock behavior, malformed admission, gap/resync/heartbeat and
failed replacement retirement. Legacy mutable-view, later callback rejection and
changed eligibility are expected incompatibility witnesses, not passing legacy
compatibility claims. Static golden success cannot certify a prepared owner.

Use the pinned simplification candidate wheel environment, Python 3.13.7 and
installed-copy Tmux a7 facade recorded in the preceding assessment. Its runtime
is unchanged by this study. Checks use a separate editable isolated environment
with exact source dependencies and no native Agent packages.

```sh
rtk proxy .venv/bin/python studies/ownership/check.py
rtk proxy .venv/bin/python studies/ownership/compare.py --python /private/candidate-env/bin/python --output /private/new-matrix
rtk proxy .venv/bin/python scripts/check.py --wss
```

The decision runner uses fresh subprocesses and four legacy/prepared/prepared/
legacy ABBA blocks per case: 1/4 hosts, 32 rows per host, 1/4/16 current queries
per admitted publication, eight full lifetimes per process. CPU includes guard
creation, accept, preparation, all queries, owned output, identity oracle and
retirement; imports/schema warmup are outside timing. Current rows must fit the
original lease. Original source acquisition/proof rules are unchanged; this
consumer-only study performs no actual source or transport I/O. No profiler or
per-query counter is installed inside the measured operations.

The prototype duplicates snapshot and row storage and retains a legacy guard;
production memory/storage bounds and single-admission integration remain
unqualified. It makes no memory improvement claim, native prepared-owner claim,
ordinary-network performance claim or deployment selection. A one-read lifetime
can be slower; only complete lifetime results qualify a use-case decision.

[Evidence](https://github.com/byebyebryan/mesh-plus/blob/12723500ea2fa7f06f3c7089fce62577c2d2fcea/docs/evidence/2026-10-13-ownership/README.md) preserves exact
inputs, source hashes, reports, incompatibility witnesses and required review.
