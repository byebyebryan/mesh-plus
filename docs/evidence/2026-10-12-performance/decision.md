# Networking performance decision

This pass retains **SSH for both Tmux and Agent**. Mesh stays at released a15,
SDK interface 1 and the frozen Read/Delivery 1 boundary. WSS remains an optional
supported backend; these trials do not recommend an ordinary fleet switch.
Agent's equivalent shape-dispatch candidate stays on its reviewed branch and in
private immutable wheel storage. It is not released, merged or selected.

## Matched observations

[Window metadata](matched-windows.json.gz) and the [summary](matched-summary.json)
retain all 128 final windows: 124 passed individual input guards, four were
excluded, and none failed delivery. Of 32 ABBA comparisons, 23 are excluded for
inventory or unmatched frame/byte/proof counts. The remaining nine are descriptive:
ordinary native contents were not frozen. A passed window is not a comparable
pair or a performance acceptance.

Each primary window has 15 seconds warmup and 120 seconds measurement. Accounting
includes owned reader/consumer, publisher and attributable SSH client/server
session CPU across both hosts. Native services and samplers are separate. Root
SSH session PSS/FDs are unavailable; reported accessible PSS is a lower bound.
Sampler transport overhead is incompletely attributed. Background CPU varied
substantially. There is no statistical significance or causal fleet-gain claim.

Tmux baseline SSH costs about 0.92–1.00% of a core in this endpoint-watch scope;
WSS costs about 1.29–1.42%. Seven traffic-qualified descriptive blocks show WSS
CPU increases of roughly 34–49%, with no meaningful accessible-PSS saving.
Agent transport comparisons are excluded for traffic or inventory differences.
They establish no steady-state WSS advantage.

The [cold acquisitions](cold.json) favor WSS descriptively: median SSH/WSS is
463/189 ms and 473/164 ms for Tmux, and 1378/1127 ms and 723/377 ms for Agent,
on Snap and Starship respectively. Twenty acquisitions per cell exclude imports,
profile/selection construction and provisioning. These are not tail-distribution
claims or evidence of a user-visible benefit for long-lived watches.

Agent a21 removes allocations in pure shape/type dispatch while preserving all
validation calls and native checks. The exact wheel is recorded in
[its build ledger](agent-candidate-build.json); all seven native schemas retain
their bytes. Source acceptance passes 379 tests; each origin frame passes 936
exact differential outcomes. Fixed-frame validation CPU improves about 20% on
Snap. Ordinary SSH pipeline block reductions range from 2.43% to 12.11%; only two
Starship comparisons remain descriptive after traffic qualification. This does
not meet the frozen >=15% CPU or >=20% PSS improvement in three of four blocks.
There is no candidate promotion recommendation.

## Acceptance and boundaries

The fresh [Tmux 600-second normal gate](tmux-normal.json) preserves its original
headless cached-delivery budget scope: Snap/Starship CPU 4.339%/2.456%, fleet plus
associated bridge RSS 83.29/82.12 MiB, owner RSS 22.74/23.77 MiB. Both endpoints
pass the existing 5% CPU, 96 MiB fleet and 64 MiB owner limits with owned cleanup.
This is the unchanged a7/a15 tuple, not WSS budget acceptance.

The [Agent candidate normal endpoint watches](agent-normal.json) each run 600
seconds, pass input guards and close with no retained channels or cleanup errors.
Two-host attributed CPU is 8.508% from Snap and 2.243% from Starship. This is one
remote endpoint plus the full consumer guard, not the earlier full-fleet scope
or a paired improvement claim. The [installed native capacity check](agent-capacity.json)
parses 4096 rows near the native frame ceiling and bounds sixteen attempted
distinct retained bodies with zero provider invocations; it does not certify
maximum WSS Mesh-frame capacity.

Current installed owner factories pass real-tailnet WSS poll/push and nonce
proofs in both directions. Each listener admits four channels, rejects a fifth
and missing/wrong-domain credentials, and retires twelve poll/push reconnects.
Candidate installed IPC/fixed SSH, mixed-version fleet and short WSS probes pass
separately. [Regression gates](gates.json) cover native/SSH and WSS fault,
credential, restart, expiry, sibling isolation and recovery with the exact
historically reviewed producer test inputs. They are not a current real-host
certificate lifecycle or physical-suspend acceptance.

The pass does not certify a production WSS selection: fixed-trace two/four-reader
resource comparisons, current-owner WSS maximum-domain capacity, real-host
authority/credential rotation and coordinated physical suspend remain promotion
gates. The prior Tmux 32 prepared-reader and Agent 1512-row acceptances retain
their dated scopes; four raw TLS admissions do not replace them. No full IPC
resource matrix was run; IPC supplies attribution and correctness controls.
These omissions bound the decision to retaining the accepted SSH configuration.

## Next work and handoff

1. Resume independent Observer work against SDK interface 1; no new Mesh API,
   factory or release prerequisite arose from this pass.
2. If further Agent CPU work is worthwhile, use balanced fixed native receipt
   traces through the full reader/publisher pipeline before another promotion
   proposal. Review repeated admission/copy work one boundary at a time.
3. If WSS is needed for a concrete deployment or cold-start use case, complete
   its remaining operational and resource gates, then use the explicit
   [owner selection wiring](../../wss-owner-selection.md). Never add silent SSH
   fallback or equate transport readiness with positive native state.

The selection/rollback diff for this decision is empty. Ordinary IPC/SSH,
collectors, service cadence, shared launcher and chezmoi pins remain unchanged.
Temporary listeners, runtime firewall rules and private credentials are retired
in the [final preservation checkpoint](preservation.json). No alternate TCP/gRPC/UDP protocol is
needed to act on this evidence.
