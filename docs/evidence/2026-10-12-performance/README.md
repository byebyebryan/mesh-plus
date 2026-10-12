# Coordinated networking performance execution

2026-10-12. Active execution of the [accepted plan](../../performance-and-wss-plan.md).
Current disposition: **P0 complete; P1 publisher/reader attribution recorded; P2 native WSS functional/admission gates pass; unchanged-carrier measurement next.**
Ordinary clients remain on IPC/SSH; no collector, native source, shared launcher,
chezmoi selector or runtime package was changed by these diagnostics.

## Baseline

Both hosts select Mesh a15, Tmux a7, Agent a20 read/publication and a18 collection.
Installed runtime resource hashes, selected-control hashes and ordinary unit
PID/start identities are recorded in the two host ledgers. Cached source captures
use the installed owner factories, not reference adapters or provider queries.
Raw native frames stay in mode-0600 files under private mode-0700 trial storage
on their origin hosts; no native records or session contents are published here.

Fresh complete fleet snapshot/watch passes from both endpoints, with remote
nonce proofs, local IPC/remote SSH and zero retained connections. That sample
contained twelve Tmux rows and 485 Agent rows; counts are time-bounded cached
observations, not an independent native oracle or a fixed benchmark workload.
The read-only harness lives in `studies/performance/host.py` and is not packaged.

## Initial publisher attribution

Each origin host replays one captured native frame through twelve frozen-frame
proof acquisitions and the compulsory Bridge result-validation boundary. The
reports are instrumented cProfile diagnostics, not normal CPU/resource budgets.
Profile construction/native source acquisition are outside the timed body.

- Tmux, six local rows: 36 `inspect_state` / native service validations for twelve
  proofs plus Bridge validation, i.e. three native inspections per operation.
- Agent, 94 Snap rows / 391 Starship rows: 36 `inspect_state` and 60 native
  `validate_frame` calls, i.e. five full native validations per operation.
- Agent shape/type validation dominates cumulative diagnostic time. Deep copies,
  encoding/tree walks and generic envelope inspection also recur. Inclusive
  profile timings overlap and must not be summed as independent CPU costs.

This supports reviewing redundant work; it does **not** approve bypassing any
trust, nonce, clock, size, reconstruction, native semantics or mutation check.
The next checkpoints establish isolated WSS/native behavior and measure normal
reader/publisher/process costs before choosing compatible implementation changes.

## Reproduction and limits

Use an origin host's Python 3.14 installed selection with the trusted harness:
`host.py inventory`, `capture`, `fleet` or `diagnostic`, explicit canonical host,
private absolute output and frozen-frame path. Existing output is never overwritten.
The source helper owns its cached operations; the fleet diagnostic owns temporary
IPC/reader/authority objects and closes them before success. Constructors acquire
no native resources. Diagnostic replay requires the capturing host's clock domain.

These ledgers do not certify candidate bytes, live WSS, tailnet reachability,
capacity, improvement, physical suspend or operational selection. Subsequent
checkpoints add their own exact evidence and keep discarded attempts explicit.

## Real-host WSS baseline

Dedicated private CA and host/domain credentials, isolated Python 3.14 a15/wss
environments and four owned listeners serve the accepted native factories on
Snap/Starship tailnet IPs, ports 9443/9444. Both domains pass remote cached
snapshot/watch with exact WSS provenance, nonce proofs and owned reader cleanup
in both directions. Ordinary clients remain on SSH. These first functional
samples do not establish performance, fault/revocation or default suitability.

Initial connections were explicitly unavailable because the host firewalls
rejected the trial ports. A dedicated runtime-only rich rule on each host admits
only the other peer /32 to its own tailnet /32 on TCP 9443-9444. Snap uses the
existing tailscale zone; Starship its existing public fallback. Rules expire
after six hours and have explicit owned removal receipts in private trial
storage. Permanent policy, SSH access and normal units are unchanged. The
reviewed helpers in `studies/performance/material.py` and `firewall.py` prepare
private credentials and reversible trial rules; no secret material is published.

P2 baseline measurements and later candidate/fault/resource/rollback gates remain
active. The listeners are owned foreground processes, not enabled deployment
units. Final acceptance must retire them and remove both owned runtime rules.

## Reviewed cost and correctness checkpoint

[Hypothesis review](hypothesis-review.md) separates repeated validation from
standalone callback, reconstruction and mutation admission. No runtime candidate
or API change is selected. Four reader replays complement the publisher reports.
The two-host accounting harness checks PID births and sampled own CPU, excludes
reaped-child double counting and reports unavailable root SSH-session PSS as null.
Short pilots establish plumbing only; discarded attempts remain private.

[Regression gates](gates.json) pass 113 standalone /151 owned native-SSH and
43 native WSS cases without skips, using Python 3.13 and the historical reviewed
Tmux a5/Agent a16 inputs. Exact current sibling HEAD parity fails at the expected
`source_head_changed:tmux-observer` guard; no frozen reference is rewritten.
Current installed a7/a20 owner checks have separate real-tailnet receipts: both
domains/directions admit four active channels, reject the fifth and missing or
other-domain credentials, retain healthy proof delivery, and close twelve fresh
poll/push channels per listener. These are cached-source probes, not provider
classification or certificate-provisioning acceptance.
