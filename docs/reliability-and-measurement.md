# Reliability and measured transport efficiency

Updated 2026-10-10. Mesh a10 is released and selected across the coordinated
Tmux and Agent read delivery cohort. The frozen state and Delivery inputs are
unchanged. The [adoption record](evidence/2026-10-10-fleet-adoption/README.md)
separates a8 measurements from final a9 acceptance.

The next [operational hardening record](evidence/2026-10-10-operational-hardening/README.md)
binds the a10 subscription-admission fix, Tmux control-binding source fix,
bounded Tmux bridge retirement headroom, and Agent pure text-validator improvement.
These changes are selected in the new paired cohort. Matched private cached-input watch/poll and independent-process
reports support retaining IPC/SSH and prioritizing compatible validation work;
they do not accept pooling, digest-proof or WSS.
The [published artifact checkpoint](evidence/2026-10-10-hardening-artifacts/README.md)
adds exact new package gates and refresh attribution. Sustained Agent coverage
now passes; [a10 live adoption](evidence/2026-10-10-hardening-adoption/README.md)
passes scoped selection, recovery, paired rollback/reselection, final cached
resources and installed SSH/Tmux lifecycle. Agent Plus migration remains separate.

## Baseline and ownership

The a7 catalog descriptor/read race is closed. Tmux Observer 0.6.0a2 / Plus
0.12.0a2 / Mesh a7 have their own accepted two-host rollout, resources, headless
and rollback evidence. Agent already adapted to the frozen profile; its a15
Claude collector optimization changes producer cost, not Mesh transport cost.
The Agent sealing-constant portability finding belongs to that producer's
runtime/packaging gate. This coordinated pass includes Observer delivery integration and managed selection;
collector performance and provider semantics remain producer-owned.

## Updated sequence

| Phase | Scope | Acceptance and disposition |
| --- | --- | --- |
| R0 | Baseline/doc sync | Catalog fix and Tmux adaptation accepted; Agent collector savings and independent transport selections recorded separately. |
| R1 | Core channel lifetime | Released a8/a9: proactive admission boundary and Reader rotation, visible revocation/resync, original receipt/proof semantics, independent healthy hosts, owned cleanup. |
| R2 | Transport measurements | Released a8/a9: cumulative Reader/Client/channel counters and owned native-profile IPC/SSH matrix. Operational and synthetic large-payload measurements are recorded in the adoption evidence. |
| R3 | Select optimization | Matched watch/poll and independent-process reports support retaining IPC/SSH. Agent's compatible validator refinement reduces pure validation CPU by 31.2% in its matched ABBA study; it does not establish whole-fleet savings. Pooling, digest-proof and WSS remain deferred. |
| R4 | Artifact adoption | A9 has its accepted exact deployment record. A10 and paired Observer/picker artifacts are published with isolated package gates and committed pins. Sustained Agent coverage, a10 live selection, recovery/rollback/reselection, final cached resources and scoped installed SSH/Tmux consumer gates pass. Agent Plus migration remains separate. |

Keep direct IPC/SSH as the default. WSS authorization/deployment, shared daemon
leases and ordered event replay remain separately reviewed work. Rotation is
core reliability work and no longer depends on the optional pool proposal.

## Rotation behavior

Client retains the Delivery validator's tombstones and never reuses a handle.
At 4,080 handles it stops new request/subscription admission under the send lock.
Existing requests, subscription credit/cancel and channel close remain usable.
Direct Client owners receive the local `channel_rotation_required` error and
must drain/cancel their work, close the old Client and connect a new one. Client
does not own a connection factory or transparently replay requests.

Reader owns its watch connections and checks that boundary before another
cached read/proof. It retires the old channel, publishes an unavailable host
outcome with that code and waits until the consumer receives the revoked view.
It then reconnects immediately, increments the existing delivery epoch and emits
resync after a fresh cached read/proof. A paused downstream cannot have the
revocation silently overwritten by replacement state. Remote push remains a
candidate until nonce-bound proof; original producer receipt times are preserved.

No schema or lock changed. This uses the existing local error code space,
unavailable host outcome, delivery epoch and resync mechanisms. Other hosts
retain their existing connections and validity. Adapters wrapping Client must
forward `rotation_due()` as well as request/subscribe/close to receive proactive
rotation; a direct Client still enforces the admission boundary if a wrapper
omits that method. Custom implementations lacking both behaviors need their own
bounded lifetime policy. A future pooled lease must preserve this ownership rule.

A9 owned sends and closes retire through repeated caller cancellation and observe
late transport exceptions without abandoned shield futures. Watch retirement uses
cancellation-safe owned cleanup. Cancellation crossing
pending-frame cleanup cannot skip closing the client. Planned rotation does not
count as a connection failure or trigger outage backoff.

## Measurement interface and limits

`Reader.inspect()` returns `mesh-plus.reader-metrics.v1`, a local diagnostic
summary. It includes active/retired connection totals, rotations, failed setup,
cleanup failures, catalog checks/time, completed framed bytes by direction/kind,
snapshot/proof admissions and result bytes, timeouts/cancellations and queue
high-water marks. Historical clients are reduced to bounded numeric totals;
their payloads and objects are not retained.
Inspect on the owning event-loop thread; callers on another thread must schedule
that inspection there.

`read --metrics` and `watch --metrics` print the final summary to stderr. Read
stdout remains one frozen profile response; watch stdout remains frozen stream
frames. Watch Ctrl-C cancels and cleans up before printing its summary. SIGKILL
or default SIGTERM cannot promise final measurements. Embedders can sample
`inspect()` without stopping their Reader.

Byte totals count completed JSON lines including LF, not encrypted NIC traffic,
partial writes or failed setup exchanges. Result bytes include the result
envelope and full payload; they are attributed to an operation while its caller
remains registered. Late unclaimed results use `otherResultBytes`.
`unprocessedResultBytes` counts decoded result lines rejected by
the codec/protocol or crossed by task cancellation before Client attribution.
Together the attributed and unprocessed result bytes account for channel result
bytes. Request admissions are counted after protocol validation, before the
write; a failed write can be
an admitted request without a completed outgoing frame. Queue peaks are per
Client/subscription maxima, not simultaneous aggregate fleet peaks. Failed
setup or uninstrumented adapters set `partial`; zeros in partial reports do not
establish zero traffic. Counters expose no producer records, route destinations,
configuration paths or arbitrary exception text.

Run the owned native-profile matrix with the supported pure Observer facades
installed and Linux/OpenSSH tools available:

```sh
rtk proxy .venv-design/bin/python scripts/measure-reader.py --carrier ipc --seconds 10 --report /tmp/reader-ipc.json
rtk proxy .venv-design/bin/python scripts/measure-reader.py --carrier ssh --seconds 10 --report /tmp/reader-ssh.json
```

Each matrix has Tmux/Agent, one/four readers and idle/one-second pushed
replacements. Every case runs in a fresh worker. Both carriers exercise the same
remote proof semantics and one-second proof cadence. SSH uses independent
channels to one disposable localhost daemon, StrictModes and forced commands.
Fixtures use frozen native envelopes and current pure validators, not provider
collection. Publication changes preserve receipt times. CPU includes the
measurement consumer; process-tree sampling is descriptive and can miss short
processes/peaks. Reports bind runtime/harness bytes and make these exclusions
explicit. They do not establish real-fleet latency, large-Agent cost, native
collection truth, graphical behavior or physical suspend acceptance.

## Acceptance and next decision

The production-budget test admits 4,079 real requests alongside one live
subscription, then proves typed rejection with push/cancel still usable.
Low-threshold tests force repeated real incarnations for both domains, healthy
sibling preservation, paused-consumer revocation and cancellation during
retirement. Owned SSH covers repeated reconnect and reaped children. CLI tests
verify unchanged stdout and final counters on read and interrupted watch.

See the [dated candidate evidence](evidence/2026-10-10-reliability/README.md)
for exact source/wheel checks and matrix reports. Counts and observations certify
only those inputs. The newer coordinated adoption record carries a8 and a9
operational evidence with their exact runtime and harness bytes.

Before choosing R3, capture identical ordinary workloads and full owned process
trees for current Agent and Tmux consumers: idle, normal updates, multi-reader,
large native snapshots, and outage/recovery. Current fixtures can expose repeated
proof/push bytes and channel multiplication, but cannot rank their production
cost. Pooling must demonstrate useful process/connection savings without losing
per-reader nonces, deadlines, credit and cancellation. Digest-proof requires
explicit capability negotiation and proof/receipt equivalence review; a reserved
schema does not grant that capability. No source optimization is made default
without its own exact artifact/consumer acceptance and rollback.

## Operational profiling

`scripts/profile-fleet.py` adds cached-only consumers to an explicitly selected
native fleet. Run it with installed Mesh and the pure domain facade, using
`--domain agent --source agent --socket /run/user/1000/mesh-plus-agent/read.sock`
or `--domain tmux --source tmux_default --socket /run/user/1000/tmux-observer/owner.sock --native-socket`.
Select `--seconds 600 --report /tmp/profile.json`; the Tmux switch owns a private
local bridge around the native cache. It does not alter collection or route health.
The report includes runtime and harness digests, frame/status counters, final
cleanup metrics and sampled owned resource totals, with no native records.
For a lifetime gate, set `--minimum-host-rotations 2 --stop-after-rotations`.
`--seconds` remains a hard maximum; the tool stops early only after every
selected host has the required observed revocations and matching fresh resyncs.
Reaching the maximum without that coverage fails the gate, even with clean
connection counters. This stress profile does not establish normal-cadence
resource acceptance. Per-host delivery-transition counts distinguish observed
gap recovery from rotation without retaining native records.

`measure-reader.py --rows 256` scales synthetic native envelopes for the IPC/SSH
matrix. This measures serialization/proof amplification, not real native large
inventories. Process-local pooling cannot share connections between independent
CLI processes. Digest-proof requires explicit negotiation and receipt-equivalence
review. Neither optimization is enabled from these descriptive measurements.
