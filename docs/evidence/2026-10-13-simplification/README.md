# Admission simplification assessment

2026-10-13. **Keep per-operation fleet grouping and fixed control-schema reuse.**
No reusable admission/body cache, weaker validation, wire/API extension or live
selection. This follows the [reviewed plan](../../simplification-plan.md).
The accepted Agent timing extension (source `c4ec7ca`, a16 / SDK 1 / lock 3) is
preserved; published a15 and earlier studies remain separate historical inputs.

## What changed and why

Aggregate admission now classifies records once by host and uses those groups
for native reconstruction, projection equality and empty/warming checks. It
replaces repeated whole-fleet filtering with one grouping pass plus per-host
work. It retains schema, native facade, proof/digest, receipt, scope/identity/order,
clock and lease admission at every public boundary. Reconstruction receives a
fresh list so a callback cannot erase the comparison's grouped records.

ReadGuard reuses immutable packaged error/control schema validators. It still
checks each input, sequence, request/incarnation and lifetime; this is not a
cache of successful frames or validity. NativeState/view dictionaries remain
mutable, and current() continues fresh full admission and expiry evaluation.
No new consumer or Observer hook is required. The sole packaged runtime change
is `view.py`; [wheel/source parity](wheel-parity.json) binds the exact bytes.

## Inputs and validation

Baseline private a16 wheel is from source `c4ec7ca` plus plan-only commit
`0c1590c`; candidate runtime is `30af2aa`. Measurement harness was corrected and
frozen at `7320b08`. [Parity manifest](wheel-parity.json) records separate wheel
SHA256s and every packaged .py/.json hash. Neither is a published release.

Python 3.13.7; attrs 26.1.0, jsonschema 4.26.0,
jsonschema-specifications 2025.9.1, referencing 0.37.0, rpds-py 2026.9.1,
websockets 17.2 and ruff 0.16.10. Tmux a7's selected installed pure package was
copied read-only into private environments; [exact installed-copy manifest](tmux-installed-input.json)
is its provenance, not proof of a separately downloaded immutable Tmux wheel.
Agent profiles use independent frozen fixtures, including explicit v2; no active
Agent source/package/service was imported or changed.

[Validation](validation.json) and compressed check logs record:

- Canonical isolated source gate: 122 core tests, 34 WSS tests, 25 locked inputs,
  21 byte-identical packaged schemas and unchanged Read/Delivery oracles; no skips.
- Separate installed candidate wheel, no Observers: the same 122/34 tests,
  plus 35 external profile/network/owned SSH cases and negative-certification checks.
- Selected Tmux a7 copy: 15 pure networking/trace cases and actual owned Tmux
  factory snapshot, fresh nonce proof, push, rename, source-loss and disconnect.
  Remote-proof bindings in that actual-native check use private IPC; they are
  not normal SSH route or native network-performance acceptance.
- Independent regression cases for linear classification, Tmux/Agent v1/v2
  projection, destructive reconstruction-list mutation, caller/result/guard-view
  mutation, expiry, scope/order/owner-less rows and fixed-schema rejection.

## Decision measurements

[160 cases / 40 fresh ABBA blocks](summary.json) use separately installed
baseline/candidate wheels and the same Tmux a7 pure facade. Classification counts
are taken in one untimed operation; timed callbacks are unwrapped owner methods.
[Raw case archive](cases.json.gz) binds exact work, input/runtime/harness hashes,
CPU/wall time, resource scope and completed teardown. Original receipts do not
advance; expected host/session identities and current rows are independently
checked. Source acquisition counts match per block.

Positive percentages below mean lower candidate CPU. Admission includes public
validate_response plus current_sessions. Pipeline includes CachedPublisher,
Bridge/Client callback boundaries, Reader read/compose and consumer guard; it
has no actual carrier or source I/O. The small identity oracle is included.

| Workload | Hosts | Rows per host | Median CPU reduction |
| --- | ---: | ---: | ---: |
| Admission | 1 | 32 | -1.25% |
| Admission | 4 | 32 | 1.70% |
| Admission | 16 | 32 | 6.83% |
| Admission | 16 | 128 | 6.50% |
| Pipeline | 1 | 32 | -1.74% |
| Pipeline | 4 | 32 | 2.05% |
| Pipeline | 16 | 32 | 1.25% |
| Pipeline | 16 | 128 | 3.05% |
| Heartbeat admission | 1 | 1 | 38.63% |
| Terminal-error admission | 1 | 1 | 57.03% |

The short one-host pipeline had one 8.2% regression outlier. A
[longer repeat](single-repeat.json), 16 additional cases / four ABBA blocks with
128 operations per cell, showed 0.33–1.04% higher candidate CPU (median 0.67%).
The >5% regression was not reproduced. No material whole-pipeline performance
gain is established. Control/error improvements exceed 15% in all four blocks,
but are not a claim about ordinary fleet-watch throughput.

At sixteen hosts, admission's Mesh host-classification hooks decrease from
70 per record to four per record for validate_response + current_sessions;
full pipeline hooks decrease from 109 to ten per record. These counts exclude
classifications performed internally by the owner facade. They demonstrate
removed repeated work, not removal of native admission.

The first counter-instrumented 160-case matrix is discarded as decision timing:
per-call counting could amplify the baseline's cost. Its local directory and
logs are preserved as diagnostic attempts. Synthetic fixture setup errors were
corrected before acceptance; no rejected input was made admissible to pass tests.

RSS is process high-water including setup, not steady PSS or a memory decision
metric. Background host load remains uncontrolled. The measured pipeline is
synthetic, not actual native push, real LAN/tailnet or managed fleet acceptance.
Actual native correctness, installed wheel, source and CI are distinct evidence.
No physical suspend, Agent-native acceptance, operational credential selection,
release replacement or ordinary deployment was performed.

## Handoff

This removes redundant work inside existing boundaries. Public dictionaries,
profile callbacks, current() mutation checks, original receipts and independent
Observer work remain compatible. The larger private admitted-state/validate-once
idea is deferred: it needs explicit ownership and callback guarantees before
reuse across public calls can preserve the current mutation/failure behavior.
Do not turn this measurement into a downstream migration prerequisite.

[Reproduction](../../../studies/simplification/README.md) lists commands and
failure/resource scopes. Artifacts and fixtures stay private; no chezmoi files
or sibling checkouts were modified.
