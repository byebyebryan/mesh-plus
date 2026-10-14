# Prepared consumer ownership review

2026-10-13. **Prepare an explicit opt-in API proposal; retain the accepted
runtime and legacy guard.** [Proposed surface and guarantees](../../prepared-consumer-proposal.md)
are ready for review. They are not SDK acceptance or a production capability.

The preceding simplification checkpoint is `cd4acc5`; accepted shared main is
`c4ec7ca` with the reviewed Agent timing extension, SDK 1 / lock 3. No packaged
runtime, schema, authority, lock or version bytes changed in this study.
[Inputs](inputs.json) bind the private simplification wheel, installed-copy Tmux
a7 provenance and study hashes. Existing Observer integration proceeds unchanged.

## Correctness and incompatibility

Nine study checks pass, including Tmux/Agent v1/v2 static golden equivalence,
input/export/result mutation isolation, immutable rule facts, expiry and clock,
invalid proof/receipt/scope admission, gap/resync/heartbeat/disconnect, and failed
replacement retirement. Three expected witnesses demonstrate why this must not
silently replace the accepted path:

- Mutating legacy guard.view is observed by its later admission; a copied sealed
  snapshot export cannot mutate the retained prepared generation.
- A profile callback rejecting on a later call is observed by legacy validation;
  a prepared value has no such callback invocation on later queries.
- Changing native eligibility after compilation changes legacy current rows but
  leaves the prepared rule unchanged until retirement/new admission.

These witnesses do not prove every dynamic callback is a valid pure owner
implementation. They prove that automatic legacy equivalence was not established
and that static preparation/later-rejection behavior needs an explicit contract.
NativeState shallow freezing and the word “pure” are insufficient opt-in signals.
No active Agent package was imported; its fixtures prove generic shape only.

## Complete consumer-lifetime measurements

[96 trials / 24 matched ABBA blocks](summary.json), fresh processes, 32 rows
per host, eight publications per process. Accept, full preparation, queries,
owned output and retirement are inside process CPU timing. The candidate
performs duplicate admission in preparation, so the result does not hide setup.
[Case archive](cases.json.gz) contains exact matched admission/query/identity work
and hashes. Inputs/source I/O and transport are outside this consumer-only study.

| Hosts | Queries per publication | Median CPU reduction |
| --- | ---: | ---: |
| 1 | 1 | -25.36% |
| 1 | 4 | 41.60% |
| 1 | 16 | 71.59% |
| 4 | 1 | -20.93% |
| 4 | 4 | 42.71% |
| 4 | 16 | 72.13% |

Positive means lower prepared CPU. One-read lifetimes are slower in all four
blocks; do not select this model for ordinary one-read-per-update consumers.
Repeated query work is materially cheaper in this static study. That does not
establish full publisher/Reader pipeline, native prepared-owner or real-network
performance. Single-admission integration might reduce setup, but that improvement
was not implemented or measured. The identity oracle remains inside timing.

Steady/peak memory is unqualified. The model retains snapshot bytes, row bytes
and a legacy guard view, so duplicates storage. Owner code/descriptor invalidation,
resource budgets, hostile rule compiler, high churn, partial/unknown-source
coverage and native owner rollout remain explicit production gates. The study
retirement model is not proof of every transport revocation race or hard realtime
cross-thread behavior. It is not a new trusted-wire shortcut or compact proof.

## Validation and next gate

Source canonical gate passes 122 core / 34 WSS tests, 25 locked inputs and 21
identical packaged schemas, with no skips; study checks are separate. Check logs
are preserved in [study log](check.log.gz) and [source gate](source-gate.log.gz).
Historical installed/native acceptance of unchanged bytes remains historical;
this study creates no new wheel or native API acceptance claim.

The next decision is explicit review of the opt-in surface and owner static-rule
promise. Then implement private single-admission ownership, verify bounds and
independent owner rules, and compare complete lifetimes at observed read counts.
Existing ReadGuard remains the default; no downstream migration is required.
Any future selection must be justified by read-heavy use, not query-only timing.
All docs and scripts stay in Mesh; no dotfiles, sibling source or live service
changes. The proposal precedes normative promotion as required by AGENTS.md.
