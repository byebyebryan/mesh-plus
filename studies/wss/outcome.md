# WSS study outcome

2026-10-11. **Feasible opt-in candidate; defer supported runtime promotion.**
Request/reply and pushed replacement state share the existing Delivery channel.
Both native profiles retain their full nonce proof, original receipts, expiry,
restart/resync and conservative current-row semantics. The frozen runtime still
supports IPC and SSH only. No Observer, Plus, Host Mesh authority or deployment
was changed.

## Acceptance and exact scope

- 31 study tests passed on Python 3.11.10, 3.13.7 and 3.14.8 without skips;
  23 carrier cases were refreshed after strengthening the wrong-client-CA case.
  The eight state tests' source and carrier implementation remained identical.
  Real 4,080-handle rotation, broadcast subscribers, slow-consumer gap/resync,
  source restart, TLS/listener loss, healthy sibling and expiry are included.
- mTLS server trust/hostname and client-chain validation precede explicit DER
  principal authorization. Unknown/expired/missing/wrong-CA credentials, wrong
  source/profile/host, Origin, path, subprotocol and redirects fail closed.
  Policy and credential replacement revoke existing channels. Captured bytes
  survive caller path replacement without reopening a changed private key.
- Exact 64 KiB client controls, large fragmented UTF-8 results up to 8 MiB +
  80 KiB, malformed JSON, binary, partial/stalled/excessive fragments, repeated
  setup/write/close cancellation, late decoding and simulated BOOTTIME resume
  are exercised. Graceful WebSocket close precedes bounded abort. Generic Mesh
  JSON has byte/depth bounds, not a separate global node-count admission rule;
  Read metadata/native profile bounds remain independent. Do not claim otherwise.
- The ordinary source gate passed 141 native/SSH tests; the installed a13 kit
  passed 35 cases. The private package isolation check found all 49 runtime,
  schema and resource members identical to released a13, unchanged dependencies
  and no study code in the wheel. This candidate is not a release or deployment.

The [decision JSON](results/decision.json) links hashes of all evidence. Initial
measurement code is reproducible at `1b73295`; [input hashes](measurement-inputs.json)
bind its carrier, fixtures and exact Mesh/Observer wheels. Final refinement
hashes are in [its report](results/refinement-measurement.json). Dated initial
acceptance is retained; it is not attributed to the refined carrier bytes.

## Matched measurements

32 original SSH/WSS ABBA runs cover both domains, idle, four independent readers,
256-row updates and observed revoke/recovery, with 30 seconds per fresh worker.
Ten cold acquisitions per remote carrier/domain add 40 samples. Eight refined
four-reader ABBA runs separately measure sampler CPU at a 500 ms interval.
Two further IPC runs use genuinely local Read binding. Original IPC extras
emulate remote nonce proofs and have the legacy Reader's SSH label; they are
retained as emulation evidence, not ordinary local IPC acceptance.

Both remote carriers use one persistent separate cached publisher/Bridge process
per Reader. SSH additionally owns ssh/sshd descendants and a forced raw socat
relay. Source updates broadcast and never refresh receipts. IPC uses a local
clock and snapshot path; it is not a like-for-like remote proof comparison.

| Observation | SSH | WSS |
| --- | ---: | ---: |
| Tmux cold snapshot median | 125 ms | 52 ms |
| Agent cold snapshot median | 159 ms | 57 ms |
| Tmux four-reader peak tree RSS, mean of two refined runs | 304 MiB | 186 MiB |
| Agent four-reader peak tree RSS, mean of two refined runs | 308 MiB | 188 MiB |
| Four-reader sampled peak processes | 25 | 5 |

These are fixture observations, not deployment budgets or tail distributions.
The original 20 ms sampler materially contributes process-count-dependent CPU.
After subtracting measured sampler work in the refinement, consumer worker CPU
is similar: Tmux SSH/WSS about 1.02/1.10 seconds and Agent about 1.76/1.80 seconds
per 30-second window. Tmux refined runs overlapped cross-Python gates; clocks,
frequency and unrelated host load were not pinned. **No consumer validation CPU
reduction is established.** Fewer remote processes and lower RSS are a topology
benefit; no broker, pooling or compact proof is justified by this study alone.

Completed JSON bytes have distinct line/message scopes. Some released Client
operation counters add an LF estimator; use Channel/byKind for exact JSON totals.
Refinement raw WebSocket counters describe queued framing before TLS, not encrypted
or NIC traffic. Neither WAN nor physical suspend is accepted.

## Resource stress and remaining work

A separate fresh synthetic transport worker held two complete maximum messages,
closed on overload, and recorded 147 MiB sampled / 149 MiB process-peak RSS for
the combined TLS client/server fixture. A declared 4 GiB frame closed before any
payload assembly. Eight offered TCP peers admitted only four pending TLS sessions,
with no source dispatch. All owned listeners, channels and pending sessions retired.
OS backlog, JSON copies, TLS/OS buffers and decoded objects remain outside any
global memory guarantee. See [stress evidence](results/resources.json).

Promotion requires the [concrete proposal](promotion-proposal.md): reviewed WSS
authority/revision/token addendum, opt-in factory and mixed-backend provenance,
operation-counter correction, a bounded configuration IO boundary under blocked
filesystems, aggregate setup/send budget review, immutable packaging and later
owner-selected real-fleet acceptance. The prototype's TLS/header/authorization
phases have separate budgets; send encoding/schema validation precedes its write
timer. Existing SDK acquisition deadlines still apply. No three-second total
opening or standalone send-validation SLA is claimed.
Captured local-file reads use threads in this study; timing out their async wait
does not promise interruption of an arbitrarily blocked filesystem call.

SSH Plus remains the existing canonical Host Mesh authority connection. WSS
registry entries reference those IDs and never write SSH route health or picker
history. WSS-only host authority, browser authentication, relays, native events,
replay, pooling and digest-proof remain separate tracks. Observer development can
continue independently against unchanged SDK v1; no Plus client migration is
part of this work.
