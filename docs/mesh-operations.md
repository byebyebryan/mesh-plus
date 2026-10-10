# Mesh operations and optional pooling

This pass implements diagnostics and a reproducible synthetic lab. Source a3 is
an unreleased candidate; the deployed SSH Plus authority remains a1. The
[frozen contract](contract-freeze.md) and its lock are unchanged. This work is
independent of the Observer and consumer integration gates.

## Diagnostics

`mesh-plus doctor` reports installed package versions. Observer packages are
optional for the generic runtime. With `--config PATH --source ID`, it also checks
the selected private source descriptor without constructing a native adapter,
connecting to its socket or collecting provider state. A successful doctor is
package/configuration evidence, not endpoint, native version or fleet acceptance.

`mesh-plus probe --domain tmux --host HOST --source ID --socket PATH` connects to
one private local Mesh bridge, negotiates its native profile and requests a
validated cached snapshot. `--mode subscribe` waits for a data baseline;
heartbeats alone cannot pass. Omit `--socket` for one explicit remote catalog host
using the installed `mesh-plus` authority command and normal SSH route policy.
Local catalog hosts require an explicit socket. Probes never report route health.
Success means acquisition and native payload validation, not current session
authority or receipt freshness. Use the fleet Reader and validity facade for those.

`--timeout-ms 1..60000` bounds setup and acquisition using BOOTTIME (default 5000).
Owned channel cleanup follows acquisition, so total elapsed time can include the
existing channel shutdown grace. JSON stdout uses the separate diagnostic format
`mesh-plus.diagnostics.v1`; success exits 0, failure exits 1. Reports contain no
producer records, configuration paths, SSH destinations or arbitrary exception
text. Known safe failure codes remain distinguishable; other errors are rejected.
Arguments can contain host/socket identity, as with existing read commands.

`Client.inspect()` reports local outstanding work, retained lifecycle handles,
queue bytes and negotiated capabilities. `LineChannel.inspect()` counts completed
framed reads and writes including LF. These are in-memory snapshots, do not alter
wire frames, and exclude SSH encryption, partial writes and kernel buffers.
Decoded Python objects can occupy more memory than the encoded queue-byte count.
There is no new diagnostic daemon, metrics port or implicit connection sharing.

## Reproduction and acceptance

Run in an isolated environment with the declared Mesh dependencies:

```sh
rtk proxy .venv-design/bin/python scripts/check.py --native --check-sources
rtk proxy .venv-design/bin/python scripts/mesh-lab.py --faults-only
rtk proxy .venv-design/bin/python scripts/mesh-lab.py --ssh --report /tmp/mesh-lab.json
```

The lab uses its own synthetic adapter and actual Bridge/Client/IPC delivery; it
imports no Observer packages or provider collectors. SSH uses the reviewed owned
localhost fixture with disposable private keys, StrictModes and a forced test
command. It never uses operational host configuration. `--ssh` requires Linux,
`ssh`, `sshd`, `ssh-keygen` and a non-root user. CI runs the IPC fault pass on
Python 3.11/3.13; native and owned SSH acceptance remain separate local checks.

Fault coverage includes source failure isolation, repeated request deadlines,
concurrent cancellation, publisher epoch replacement, fresh connections, push
acquisition and cleanup. SSH additionally proves a deadline leaves sibling work
usable, a pushed baseline arrives, disconnect wakes pending work and a fresh owned
SSH connection works. Existing suites provide framing, route policy, credit
starvation, gap/resync, receipt expiry and fleet sibling-failure checks. This is
not physical suspend, WAN interruption or prolonged production stress acceptance.

Each resource workload runs in a fresh subprocess. The default matrix covers
1/4/16 IPC hosts, 1/2/8 readers, 4 KiB/1 MiB/8 MiB payload padding and simultaneous
snapshot, artificial full-payload proof and periodic pushed replacement state.
SSH covers 1/4 hosts with one reader per host. Admission bounds the matrix to
16 hosts, 8 readers, 100 rounds and 64 MiB aggregate payload padding.

[Lab evidence](evidence/mesh-lab.json) binds exact runtime, fixture and lab bytes.
CPU/RSS samples are descriptive. Worker peak RSS excludes SSH descendants;
reaped-child CPU excludes the complete SSH tree. A separate 20 ms sampler walks
only the fresh worker's descendant tree
for observed process counts, aggregate RSS and first-to-last observed CPU deltas.
It can miss short-lived processes or peaks while the event loop is blocked;
aggregate RSS counts shared pages in each process. Application bytes are not NIC
traffic. Push wait includes publication cadence and queued work and is not
publisher-to-consumer latency. Queue bytes are sampled at the end, not a peak.
Synthetic proofs measure payload carriage, never native proof correctness.

Selected observations from this pass (one reader, five rounds):

| Carrier / padding | Setup ms | Mean snapshot ms | Worker peak RSS KiB | Sampled peak owned processes |
| --- | ---: | ---: | ---: | ---: |
| IPC / 4 KiB | 11.1 | 4.8 | 31,896 | 1 |
| SSH / 4 KiB | 310.8 | 5.0 | 31,896 | 6 |
| SSH / 1 MiB | 367.7 | 57.2 | 44,108 | 6 |
| IPC / 8 MiB | 375.8 | 646.8 | 96,312 | 1 |

SSH setup includes disposable key generation and daemon startup. Its process
count includes the test daemon and worker; these are not predictions for an
existing fleet. IPC publishers run in the worker while SSH publishers run in
children, so worker-only CPU/RSS is not a carrier comparison. The small sample
count is insufficient for a stable p95. Periodic push remains active while each
case runs, so total traffic also reflects elapsed time and queued publications.
These observations support further profiling, not a performance guarantee.

[Review evidence](evidence/mesh-operations-review.json) records 79 native tests on
source Python 3.13 and the isolated Python 3.11 wheel, 52 wheel core tests without
Observer packages, 34 byte-identical packaged runtime/schema files, unchanged
lock/authority hashes and all 11 lab workloads. The native tests also invoke the
actual diagnostic CLI against both domain fixture publishers for poll and push.

## Optional pool proposal

Decision: keep owned direct IPC/SSH connections as the default. Add pooling only
as an opt-in Mesh-owned layer after the existing producer integrations settle.
No broker or new capability is implemented or advertised by this proposal.

The proposed first phase is a process-local connection pool. Its key binds the
canonical host, catalog revision, route token, source, profile and required
capabilities. Routes from different trust/policy bindings cannot share a slot.
One pool owns the upstream Client; each Reader receives a **lease** exposing
`codec`, `request`, `subscribe`, and `close`. Reader currently consumes precisely
that interface; `codec` must retain the bound Observer facade that Reader expects.
Lease close cancels only that lease's handles; the last lease
closes the upstream. Pool lifecycle is explicit and bounded by its owner.

Start by sharing channels while keeping requests and subscriptions independent.
Requests preserve caller-specific nonces and deadlines, including time spent
waiting for one of the upstream's eight request slots. Do not return a cached
proof from another nonce or renew original receipts. Subscription slots are also
limited to eight; excess admissions fail visibly or use a separately bounded
pool slot rather than silently falling back to polling. Reconnect creates a new
upstream epoch; leases cannot carry positive validity across it. Rotate channels
before the 4096 retained-handle limit through a drain-and-replace policy.

The second phase may share a native upstream subscription and fan out state to
lease-local iterators. Each downstream has independent bounded credit, cancel,
gap/resync and lifetime. A slow reader cannot block siblings or consume their
control reserve; coalescing produces a visible delivery gap and a replacement
baseline. Baselines retain original epoch, receipt identities and expiry.
Each remote Reader still obtains its own nonce proof before granting validity;
channel sharing alone does not remove repeated full-payload proof traffic.

A later same-user IPC daemon could extend sharing across applications, but it
needs its own reviewed local request contract, explicit source allowlist and
lease authorization. A remote host reached through the daemon stays remote in
the Reader; the localhost hop must never confer local clock/receipt authority.
Preserve the end-to-end proof RTT budget, original native receipts and per-reader
ReadGuard scope. Do not present a fleet daemon as today's host-local `serve`.

Catalog replacement invalidates affected pool keys and terminates attached reads
with the existing visible catalog-change behavior. One failed host cannot revoke
healthy sibling-host leases. No reconnect replay, actions, collection scheduling,
terminal launch or picker-history ownership moves into the pool.

Acceptance before implementation/adoption:

1. Compare direct and pooled delivery with identical workload/lifetime, including
   multiple readers over SSH and measured owned process-tree CPU/RSS.
2. Prove independent cancellation/deadlines and cleanup when one or all leases
   close; prove catalog, route and publisher replacement revoke affected scopes.
3. Prove bounds under slow readers, saturation and reconnect bursts, including
   explicit queue high-water marks and 4096-handle channel rotation.
4. Prove original expiry, caller nonce correlation and conservative proof RTT
   survive both a process-local pool and any later daemon hop.
5. Keep direct mode selectable for rollback. Show useful connection/process
   savings before making pooling a default. Producer/UI acceptance stays separate.

## Next decisions

The measured small SSH case supports continuing the initial carrier. Large
full-payload reads/proofs warrant measuring native payload size and cadence before
choosing digest-proof optimization. Multi-reader IPC creates duplicate channels,
so pooling has a concrete target, but SSH pool savings are not yet measured.
WSS needs separate authentication, authorization and deployment acceptance;
these localhost samples do not establish a reason to switch carriers.

The next implementation scope should therefore be chosen from actual integration
costs: channel pooling for duplicate readers, or negotiated digest-proof for
repeated large native proofs. Neither change is required for current Observer
integration, and neither changes the already-frozen state contract implicitly.
