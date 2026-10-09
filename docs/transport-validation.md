# Transport design validation

## Evidence scope

This pass validates a design candidate, not an installed transport. Outer-frame
schemas and adversarial lifecycle models exercise poll, push, cancellation,
credit, epoch guards, compact proofs and state/event recovery. A disposable
carrier experiment uses synthetic payloads only; it never reads an Observer,
changes provider state, attaches tmux or edits operational SSH configuration.

The first-pass manifest is preserved in
[read baselines](evidence/read-design-baselines.json); frozen fixtures remain
unchanged. [Transport source review](evidence/transport-source-review.json)
records current heads and the Agent study paths seen during active development.
Agent's `8776cc6` state-push documentation checkpoint changes no production wire.

## Results and reproduction

Read/profile validation passes **117 checks**, including existing pure producer
validators against nine reconstructed owners per domain. Delivery validation
passes **161 checks** against four schemas and twenty-five examples. Together
the two suites cover fourteen schemas and forty-seven examples. Ruff passes.

```sh
rtk proxy uv venv .venv-design
rtk proxy uv pip install --python .venv-design/bin/python -r requirements-design.txt
rtk proxy .venv-design/bin/python scripts/check-design.py --check-sources --report docs/evidence/design-validation.json
rtk proxy .venv-design/bin/python scripts/check-delivery.py --report docs/evidence/delivery-validation.json
rtk proxy .venv-design/bin/python scripts/study-carriers.py
```

The [carrier result](evidence/carrier-study.json) passes four carriers: Unix IPC,
subprocess stdio, disposable loopback SSH, and WSS with explicit server-certificate
trust. Each uses the same strict outer protocol and scenario: two timer-driven
state subscriptions, interleaved request/reply, an 8 MiB response, cancellation
of one subscription while its sibling still publishes, and later request/reply.
WSS also rejects an untrusted certificate. Temporary keys/listeners/children
are owned and removed; operational configuration and providers are not used.

The SSH experiment uses a private temporary directory under the design venv so
OpenSSH StrictModes can validate its key path. An earlier `/tmp` key-path attempt
failed authentication; it supplied no positive transport result. The corrected
experiment retained StrictModes and isolated host/client keys. No operational
SSH configuration was relaxed to make the study pass.

Recorded request timings are one warm-channel sample per payload size. Python
encoding/validation and differing in-process/child scheduling contribute to
them. They establish successful carriage, not relative production performance.
No CPU/RSS, reconnect/suspend, real native passivity or source age proof was
measured by this carrier study. WSS client authorization and IPC peer credentials
remain separate runtime gates.

## Required scenarios

| Scenario | Acceptance at design level |
| --- | --- |
| Request during subscription traffic | Correlated result and ordered push on the same channel |
| First subscription publication | Acceptance/baseline barrier precedes data |
| Cancel one stream | Terminal barrier; siblings and requests continue |
| Late result after timeout or reconnect | Rejected or quarantined in its original handle/epoch |
| Unknown capability or event contract | Explicit unsupported outcome before pretending to stream |
| Repeated credit | Cannot multiply permitted frames or bytes |
| Slow state reader | Bounded replacement plus explicit gap/resync |
| Slow event reader | Explicit loss and cursor; no replacement-state repair |
| Event replay/live boundary | No omitted or duplicated admission within the accepted connection |
| Producer restart or expired event cursor | Typed restart/retention gap; never silent live continuation |
| Client filter hides records | Native progress still advances |
| Broker late join/different cursor | Separate replay barrier or distinct upstream subscription |
| Bridge cached frame with lost owner | Cannot issue successful compact proof |
| Wrong digest, nonce, incarnation or receipt | Reject proof; full replacement/failure required |
| Transport heartbeat only | No source lease, event age or activity renewal |
| Large Agent state frame | Fits explicit negotiated capacity or fails visibly |
| Stderr or control congestion | Bounded failure; no unbounded logging/queues |

## Implementation sequence

1. Freeze the pure delivery envelope, parser limits, fixed source descriptor and
   lifecycle guards. Preserve native and Mesh Read profile versions.
2. Implement IPC and persistent SSH backends using the same session engine.
   Prove controlled duplex operation and independent handle cancellation.
3. Extract Tmux behind its existing coordinator. Independently accept the Agent
   adapter against the current producer checkpoint. No old Agent Plus migration
   is required to accept the producer or transport.
4. Add optional digest proof only after adapter equivalence and source-fault
   cases pass. Retain full proof as the mandatory fallback.
5. Before onboarding several independent clients, measure embedded versus a
   local per-user service. Prove downstream expiry/credit and replay interests;
   select one upstream owner for each migration checkpoint.
6. Implement WSS if endpoint/client requirements or measured SSH costs justify
   it. Prove TLS plus client authorization and endpoint catalog versioning.
7. Accept ordered-event delivery after each producer exports its own exact
   event contract. Prove replay, retained floor and source status end to end.

## Native acceptance still required

Measure persistent versus cold setup, bytes and full-replacement rate, owned
SSH children/bridge processes, CPU/RSS and OS/library buffers. Compare one and
several clients; separate physical connections, logical subscriptions and
provider collection work. Use identical payloads and connection lifetime for
backend comparisons. These design models cannot prove an SSH or WSS savings
percentage.

Test real host/owner restart, authentication/host-key rejection, route change,
sleep/wake, slow consumers, cancellation under concurrent push, reconnect storms
and source expiry without publications. Verify actual native passivity and
rollback with disposable resources while preserving ordinary sessions/history.
An SSH Pong/keepalive and a successful TLS handshake are delivery evidence,
not current source state. No deployment or cross-host operational test is
implied by this design pass.
