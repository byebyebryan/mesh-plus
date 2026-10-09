# Mesh Plus design review

## Candidate disposition

The candidate establishes a common mesh-aware read shape with unchanged domain
records, attributable owner metadata and independent transport/source validity.
Local and fleet consumers use the same pure facade. Existing published local
interfaces remain intact until an explicit profile migration.

The review is primary-led. Structural, frozen-source and adversarial results are
recorded in [validation evidence](evidence/design-validation.json). Native,
graphical, resource and operational acceptance belong to implementation stages.

## Resolved design findings

| Finding | Resolution |
| --- | --- |
| A wrapper around arbitrary local results changes client shape substantially | Use one versioned domain profile with existing flat session records and common mesh metadata |
| Existing singular-host envelopes cannot gain fleet support invisibly | Preserve old interfaces and negotiate the new profile explicitly |
| Agent Plus is behind its active producer | Freeze current Agent read contracts independently; defer Plus migration |
| Agent advanced with event research, then a state-push refinement | Recheck unchanged state wires; prioritize complete-view subscriptions and keep ordered native events deferred |
| Agent service 2 has no nonce probe | A fixed-source bridge reads the cached local service after the nonce and uses original source leases |
| Source BOOTTIME origins differ | Translate only remaining validity through measured local RTT with margin |
| A waking service with null snapshot still has useful source/incarnation information | Retain its service header with null snapshot metadata; distinguish complete-empty |
| Missing history receipts could bypass conservative expiry | Require the full component receipt map before a source view is accepted |
| Full heartbeats repeatedly transmit large Agent inventories | Small controls carry liveness/gap; only views and resyncs carry records |
| Agent receipts do not expose full field dependencies | Conservative per-provider expiry; no runtime refresh of history/activity |
| Mesh downgrading an expired active receipt could hide its provider dependency | Compare against original native positive components; revoke affected provider claims while preserving healthy siblings |
| Unsaved retirement deadlines are not fully public | Omit historical unsaved rows conservatively; exact retention parity needs a future receipt |
| Tmux fleet contains desktop and refresh authority | Keep that coordinator and compatibility projection separate from reusable transport |
| A common default payload limit could truncate Agent data | Profile owner limits plus an explicit aggregate cap; no silent roster truncation |
| Route health and SSH usage have different reachability meanings | Keep authenticated background markers separate from picker history rules |
| Config migration can create two authorities | Stage extraction with one selected source and writer; directory relocation is optional |
| Push was implicit in an SSH read bridge | Specify request/reply and subscription lifecycle independently of the backend |
| Client subscriptions mistaken for publisher-initiated connections | Client-opened duplex channels deliver publications; reverse relay topology is separate |
| State watch confused with ordered native events | Separate products and native validators; never repair events with a state resync |
| Slow downstream readers could stall a shared source | Cumulative credits, bounded queues, control reserve and independent failure |
| Cancel/reconnect can deliver late frames | Quarantine in-flight cancelled frames, require terminal barriers and reject old epochs |
| Shared event tails could skip a late reader's cursor | Independent replay barriers/channels before live-tail sharing |
| Full proof repeats large pushed inventories | Negotiate exact digest-bound proof with cached-read equivalence; full replacement/failure on drift |
| Allowed Agent frame already includes 16 KiB overhead | Add a separate 64 KiB Mesh wrapping reserve to the delivery message limit |
| Alternatives require different deployment/auth authority | Keep backend endpoint registry versioned and distinct from SSH-specific Host Mesh v1 |

## Implementation decisions still requiring measured proof

Package API names and final Observer profile version allocation are settled by
each producer checkpoint. The three-second Tmux and ten-second Agent proof
cadences, 16 MiB aggregate and 96 MiB reader byte budget are initial bounds to
measure, not accepted host costs. A local per-user Mesh service is a supported
topology with independent acceptance before multi-client adoption. SSH master
sharing remains optional. The compact-proof extension now has a schema and
adversarial oracle; its real adapter equivalence and native resource gate remain.
New source receipts can still require full replacement, so no traffic reduction
percentage is claimed. WSS is an evaluated alternative, not a selected fleet endpoint.

These do not prevent a contract-first implementation. They prevent calling the
design a selected operational runtime. No compatibility converter to old Agent
Plus or obsolete Observer state classifiers is part of the plan.

## Design validation result

The second pass retains the original read projection and adds backend-independent
delivery. Current read validation passes 117 checks against ten schemas and
twenty-two examples, including WSS projection parity. The existing pure producer
validators accept nine reconstructed owners each for Tmux and Agent. Delivery
validation adds 161 checks against four schemas and twenty-five examples. Ruff
passes for the six design/study scripts.

The owned carrier experiment passes Unix IPC, subprocess stdio, actual loopback
SSH and WSS: timer push, simultaneous requests, an 8 MiB response and independent
cancellation. WSS rejects an untrusted server certificate; client authorization
and IPC peer-credential policy were not tested. All sources are synthetic.
See [delivery evidence](evidence/delivery-validation.json),
[carrier evidence](evidence/carrier-study.json) and
[transport gates](transport-validation.md).

The optional current-checkout source validation command is:

```sh
rtk proxy .venv-design/bin/python scripts/check-design.py \
  --check-sources --report docs/evidence/design-validation.json
```

The result records schema/host-catalog framing checks, exact reconstruction of
both frozen owner snapshots, the same local/fleet selectors, proof and stream
oracles, and hostile scope/lease/nonce/version/capacity inputs. Existing pure
Tmux and Agent public semantic validators accept the reconstructed owners and
service frames, with no collector or provider adapter imports. Source hashes
and heads are rechecked separately from the frozen fixture copies.

These checks establish feasibility and consistency of the proposed contract,
including its conservative fallbacks. They do not establish production bridge
security, live SSH passivity, host costs or final API release compatibility.

The second pass's source review is in
[transport source review](evidence/transport-source-review.json). The first
manifest is preserved as [read design baselines](evidence/read-design-baselines.json).
Agent `8776cc6` changed documentation/study scope, not the accepted production
API 2/snapshot 4/service 2 code or frozen reference fixtures. No producer source edits, deployment, ordinary provider actions or live fleet
acceptance are part of this Mesh design pass. Publication commits only the Mesh
design package and its validation tooling.

Publication review replaced sibling-checkout links with hashed, frozen source
documents. The default checks must pass from an isolated checkout; only the
explicit `--check-sources` gate requires the producer repositories.
