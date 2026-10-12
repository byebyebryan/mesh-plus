# Mesh and Observer networking performance pass

2026-10-12. **Reviewed planning checkpoint; implementation and trial selection
have not started.** Tmux and Agent development are parked for this coordinated
pass. Mesh owns this plan and cross-project evidence; any eventual source change
belongs in its owning repository. Existing published artifacts remain immutable.

This supersedes the *execution ordering and baseline assumptions* of the earlier
[WSS trial plan](wss-fleet-trial-plan.md), not its dated inventory or acceptance.
The two Observer publisher factories are now deployed in the combined launcher.
We will evaluate compatible CPU/copy work and optional WSS separately before
recommending a transport selection. Ordinary consumers remain on IPC/SSH.

## Fixed starting point

| Role | Snap and Starship baseline |
| --- | --- |
| Mesh SDK/shared CLI | released 0.1.0a15; SDK 1, Read/Delivery 1, lock revision 2 |
| Tmux networking/owner | Observer 0.6.0a7; pure Tmux profile and owned cached publisher |
| Agent networking | Observer 0.5.0a20 reader/publisher; pure Agent profile and owned cached source |
| Agent collection | Observer 0.5.0a18, existing cadence/hints |
| Shared launcher | both static lazy owner factories; hash and source origins captured before execution |
| Normal remote carrier | SSH; local IPC |

Exact wheel SHA256 inputs:

- Mesh a15: `42b25045f8f89afda61e56525f443a189dcc6769637aee5bcab959f096527f0f`
- Tmux a7: `e73a88f89b38242631766dd45f6e669f43c54e36857e5716595c0a56321e5091`
- Agent a20: `8241cafc13dbfdfe43da0b092dbce99328ee6cc0b0b74faa04b428dfa54a9b1a`

The prior [Tmux owner acceptance](https://github.com/byebyebryan/tmux-observer/blob/25d5a170834406b848cda47b7316a090d5fc028e/docs/evidence/2026-10-12-publisher-integration/README.md)
records 4.580%/2.751% combined normal CPU and about 84/83 MiB fleet+bridge RSS,
with ceilings of 5% CPU and 96 MiB (owner 64 MiB). The
[Agent owner acceptance](https://github.com/byebyebryan/agent-observer/blob/1113d52c3ff4822b9c6a5b3bfab19a6007de8b72/docs/evidence/2026-10-11-mesh-publisher/REPORT.md)
records 10.534%/8.211% CPU for one fleet reader plus local SSH children, excluding
remote server/bridge work. Those are different accounting scopes; do not add,
rank or compare them as equivalent budgets. Fresh matched windows establish this
pass's baseline. Current inventory sizes and native activity are variable.

Refresh read-only preflight on both hosts. Earlier tailnet IPs are Snap
100.70.82.105 and Starship 100.84.31.64; ports 9443/9444 were unoccupied. LAN
addresses were on different subnets. Start with an explicitly verified tailnet
path; direct LAN is a separate conditional experiment. Record direct/relay path
per measurement block. No endpoint/firewall/certificate is selected by this plan.

## Scope and invariants

Potential edits are limited to Mesh delivery/validation/copy internals, optional
networking sources/profiles and equivalent pure validation hot paths in the two
Observers. Do not change collectors, cadence, provider queries/semantics, desktop
policy, actions, UI, native identity or schema/wire bytes. Source text in these
repositories may advance independently of the pinned installed baseline.

Keep every compulsory check at the relevant trust/mutation boundary: authenticated
host/source/profile, JSON/type/size/depth admission, native shape/semantics,
lossless reconstruction, exact nonce/digest, clocks, original receipts and expiry,
ordering, restart/gap/revocation, ownership and cancellation. Cached object presence
and equal row counts do not certify equivalence. No unchecked fast path, parser
leniency, identity shortcut, arbitrary plugin loader, longer deadline or reduced
proof/collection cadence may manufacture the gain.

No schema/lock regeneration, SDK v2, digest-proof, pooling/broker, partial-frame
protocol, event/replay or alternate TCP/gRPC transport belongs in this pass.
A finding requiring such a change becomes a separately reviewed proposal.

## Questions and concrete attribution

1. How much cost is native cached acquisition, pure validation, generic Mesh
   admission/tree/schema work, projection/reconstruction, copying, digest/JSON
   encoding, consumer guards and channel/process overhead?
2. Which validations/copies repeat over the *same owned admitted frame*? Which
   recheck data after a mutation, new receipt/proof or different trust boundary?
3. Does WSS reduce total attributable CPU/PSS/processes or delivery latency with
   the same accepted publisher/profile/workload, and what operations does it add?
4. Does any candidate preserve current/failure behavior under normal, capacity
   and recovery loads, not merely improve a small successful snapshot?

Inspection already identifies hypotheses, **not approved removals**:

- Agent `AgentCodec.validate_bridge` and `inspect_native` both call native
  `validate_frame`; its source guard also validates acquisition.
- Mesh `CachedPublisher.watch`, `wrap` and `validate_bridge` inspect the native
  state at different points; Bridge/Reader/consumer admission add their own work.
- `inspect_state` encodes for capacity, checks native projection/reconstruction,
  and reads receipts. Reader composition copies outcomes, fingerprints them and
  validates the resulting view. Tmux's pure profile also owns copies.
- Protocol `tree`, JSON schema/type checks and full-frame serialization recur.

Count actual invocations and bytes/allocations per snapshot, proof and pushed
replacement. Profile separate processes/roles; cProfile and tracemalloc change
absolute cost and are diagnostic runs, not performance acceptance. A retained
internal validated state is a possible implementation choice only after proving
its frame/binding ownership and invalidation; there is no global identity cache
or raw native-object memoization in the approved plan.

## Measurement harness review

Reuse owner tooling as evidence and bounded primitives, not as interchangeable
benchmarks:

- Mesh `measure-reader.py` / `compare-reader-profiles.py` use old reference-adapter
  fixtures and IPC/SSH. They do not currently certify current owner publishers or
  WSS. `profile-fleet.py` has a native reference bridge path and separate CPU scope.
- Agent `measure-mesh-publisher` measures sequential old/new local windows and
  attributes reader/publisher trees; extend a reviewed harness with balanced
  ordering for this pass. Its `native-rounds` option queries provider metadata;
  do not invoke that inside clean timed windows.
- Tmux normal/capacity tools own native fixtures and declare their accounting.
  `measure-owner-pipeline` instruments costs; old prototype scripts must be
  checked for actual supported publisher/profile use before reuse.

Create one reviewed Mesh-owned coordinator/measurement adapter layer using exact
installed public owner factories/profiles. Do not copy native guards, private CLI
code or provider collection into Mesh. Pin harness and runtime digests separately;
retain complete case accounting, including rejected/discarded windows. Include
PID+birth identities, attributable remote bridge/SSH children and owned teardown.
No whole shared sshd, unrelated user sessions or desktop services may be counted
as trial descendants. Never double-count reaped child CPU and sampled descendants.

## Ordered checkpoints

| Gate | Work | Exit criterion |
| --- | --- | --- |
| P0 — freeze and baseline | Capture exact installed artifacts/dependencies/controls, role PID+birth identities, source roots, route/cadence and collector preservation. Refresh complete cached poll/watch/proof from both hosts for both domains. | All hosts ready, correct bindings and native receipts; actual baseline understood; rollback inventory concrete. |
| P1 — profile on IPC/SSH | Fresh-process frozen-input profiles plus ordinary cached samples; attribute each stage and repeated call/copy. Measure sampler overhead. | Cost map and ranked hypotheses; distinguish native-source work, publisher, reader/consumer and process cost. |
| P2 — isolated WSS baseline | Implement/review bounded harness and private credentials/listeners under the prior trial plan. Verify both current owner factories over WSS; run baseline SSH/WSS pairs. | Real tailnet correctness and original-receipt semantics, explicit setup/capacity/dependency limits; no ordinary client switch. |
| P3 — compatible candidate | Choose the smallest evidence-supported change, in its owning repo, preserving all boundaries. Use isolated checkouts where needed and successor immutable wheels. | Meaningful differential/adversarial tests, frozen schema parity, owner conformance and installed mixed baseline/candidate acceptance. A no-change conclusion is valid if gains are weak. |
| P4 — factorial measurement | Compare baseline/candidate on IPC, SSH and WSS with identical payload/cadence and balanced fresh windows. Repeat both direction/host roles. | Repeatable attributable gains beyond run variation; latency/resource/noise/cleanup tradeoffs reported without mixed-source claims. |
| P5 — full acceptance | Exact candidate source/installed/native/capacity/normal resources, recovery/rotation and WSS credential/loss/restart/rollback. Test partial/stale/empty/unknown and healthy siblings. | No semantic regression or leak; no worse accepted owner budgets; exact artifacts and limitations bound every result. |
| P6 — decision and handoff | Record retain-SSH, optional-WSS or recommended per-domain switch; release recommendations and concrete managed selection/rollback diff. | Reviewable decision based on baseline and final bytes. Ordinary deployment requires a separately authorized selection checkpoint. |

Before P3 edits, record which call is redundant, where equivalent admission
remains, what immutable data is reused, and which invalidation/adversarial tests
prove it. Review one hypothesis at a time; do not combine a transport change,
validation optimization and cadence change into one un-attributable result.

## Workloads and comparison matrix

The four key cells are **baseline SSH, baseline WSS, candidate SSH, candidate WSS**.
Local IPC is the control for validation/copy cost. If no compatible candidate is
selected, explicitly omit candidate cells; do not invent a code change for symmetry.

| Tier | Workload | Purpose |
| --- | --- | --- |
| Micro/profile | Fixed successful and adversarial native frames; empty/warming/partial/stale; explicit proof and state update | Call counts, allocation, admission cost and semantic equivalence |
| Primary real fleet | Ordinary cached snapshot/watch, one additional reader, both host directions | Decision-driving actual inventory/cadence and total attributable cost |
| Fanout | Two and four readers; push at fixed fixture cadence; same payload/receipt trace | Process/topology sharing, contention, deadlines and backpressure |
| Capacity | Tmux's declared owner/reader limits; Agent's 1512-row controlled case; near frame limits | Complete records, rejection, resource retirement and budget margins |
| Fault | Publisher/listener/reader restart, connection loss, slow reader, authority/registry/credential change | Revocation, isolation, reproof/resync and rollback correctness |

Do not run a full Cartesian product of all capacity/fault cases as lengthy CPU
soaks. First use profiles/pilot windows to select representative expensive cases.
The primary comparisons are baseline-vs-candidate on SSH, SSH-vs-WSS at baseline,
and SSH-vs-WSS at candidate. Use four ABBA blocks per selected pair/domain, fresh
processes, 15 seconds warmup and 120 seconds measured. The primary two-domain
three-pair matrix is about 3.6 hours of sequential windows before fanout, capacity
and correctness gates; record a narrower matrix if no candidate is justified.
Repeat a 600-second final normal gate per accepted owner/host. Collect at least
20 cold acquisitions/carrier/domain, reporting descriptive median/p95 and raw
values without tail-distribution claims.

Tmux retains its accepted proof cadence (normally 3 seconds); Agent normally
10 seconds. Capture actual reader/publisher/consumer settings rather than assuming
those defaults. No cadence reduction belongs in candidate or WSS benefit numbers.
Use frozen synthetic traces for exact pairs; bracketing ordinary cached windows
remain descriptive when real inventory/activity changes. Preserve receipt aging:
only new source evidence advances receipts, never transport heartbeat/proof itself.

The primary attributable total is owned reader/consumer work, associated
publishers and attributable SSH children **summed across both hosts**. Track
ordinary native owner/collector CPU separately with its unchanged cadence and
report any incremental cached-encoding impact; do not silently omit it from the
end-to-end assessment or attribute the whole resident service to one reader.
Preserve the original scope when checking Tmux's existing combined budget.

Record CPU percent of one core per role and attributable two-host total, PSS/RSS,
FD/process peaks, acquisition/update latency, frame/byte counts, drops/gaps,
current-row validity and cleanup. Exact JSON message/line scopes differ; neither
is TLS/NIC traffic. Sample at 500 ms and separately account sampler work. Reject
pairs with artifact/incarnation/cadence changes, unexpected load, collector
restart, inventory changes invalidating comparability, or tailnet direct/relay
switch. Keep exclusions and failed attempts rather than hiding inconvenient data.

WSS's four active/pending TLS admissions are a **per-listener** bound, not Tmux's
32 downstream prepared-reader capacity. Test fanout behind the existing prepared
service separately from four raw upstream clients. Reconnect must retire prior
channels; fifth admission rejects without source dispatch. Architecture/fanout
benefits must be labeled separately from carrier/validation gains.

## Decision rules and operational gates

Correctness, source receipt authority, cleanup and accepted budgets are hard gates.
Tmux normal CPU remains <=5% with existing memory/deadline limits; capacity receipts
remain separate. Agent currently has measured costs rather than an equivalent 5%
budget: require no unexplained regression in its matched role/total costs, RSS/FDs
or proof latency and retain its declared-capacity acceptance. Do not invent a
cross-domain target by comparing unlike accounting scopes.

Planning thresholds for a **worthwhile** change are either >=15% reduction in the
primary attributable CPU total, or >=20% PSS reduction, repeated in at least three
of four paired blocks on the affected endpoint, with no >5% reproducible primary
CPU/PSS regression on the other endpoint. These are decision heuristics to freeze
before clean measurements, not claims of statistical significance or permission
to relax existing hard budgets. Latency-only wins need a concrete user-visible
benefit; cold setup alone is insufficient to select WSS for long-lived watches.
If variation is too large, gather longer/repeated windows or report inconclusive.

WSS promotion additionally requires native poll/push equivalence, loss/restart/
authority isolation, mTLS wrong/missing/expired/revoked credentials, client/server/
CA rotation, channel cleanup, sustained reconnect and explicit rollback. Physical
suspend remains a separately coordinated real-host gate before an unconditional
fleet-default recommendation. Expiry under simulated clocks is not that evidence.
Document listener ownership, certificate provisioning/renewal and startup dependency
cost; a process-count win alone does not settle operational suitability.

Outcomes may differ by domain: keep SSH; retain optional WSS; or recommend a scoped
WSS selection. Default switch is not required for this pass to succeed. A WSS
source remains unavailable on failure; never hide it through automatic SSH fallback.

## Artifacts, preservation and next authorization

Deliver: current baseline/input ledger; reviewed reproducible harness; attributed
profiles; hypothesis/review record; exact candidate(s) if justified; balanced raw
and summarized measurements; conformance/native/fault/resource receipts; a final
per-domain decision and concrete selection/rollback proposal. Keep redacted docs,
scripts and evidence in the owning repos. Private native fixture bodies and all
credentials stay in private local trial storage; no prompts/tool/session contents
enter public reports. Chezmoi is only for a later necessary managed selection.

The combined shared launcher, collector/service cadence, provider settings,
ordinary sessions and unrelated worktrees stay protected. Published baseline
assets are never overwritten. Tag/source, private wheel, public release and live
selection remain distinct. Any API/schema/authority change reopens its normative
review rather than being smuggled into a performance fix.

A following goal loop can authorize P0–P6 investigation, compatible source work
across the three repos and **isolated** real-host WSS trials, committing checkpoints.
It stops before ordinary transport/deployment selection unless that concrete action
is separately authorized. Physical suspend requires a coordinated window because
other work and ordinary sessions may still be active even when the two agents
are parked.
